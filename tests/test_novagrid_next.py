"""Decode NovaGrid output independently and exercise bounded worker failures."""

import io
import json
import random
import struct
import zlib

from PIL import Image
from PIL import ImageChops
from PIL import ImageDraw
from PIL import ImageStat
from PIL import PngImagePlugin
import pytest

from src.services import novagrid
from src.services.file_tools import FileTools
from src.services.tool_worker import convert

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def texture(size, seed=7, mode="RGB"):
    """Smooth interpolated noise: cheap to compress lossily, costly to keep exact."""
    channels = Image.getmodebands(mode)
    raw = random.Random(seed).randbytes(16 * 12 * channels)
    return Image.frombytes(mode, (16, 12), raw).resize(size, Image.Resampling.BICUBIC)


def interface(size, mode="RGB"):
    """Flat graphics with a few exact colors and text."""
    image = Image.new(mode, size, "#0b1019")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((10, 10, size[0] - 10, size[1] // 2), 8, fill="#152438")
    draw.text((24, 24), "NovaGrid / service 01 / online 99.86%", fill="white")
    return image


def rgba_bytes(path_or_image):
    if isinstance(path_or_image, Image.Image):
        return path_or_image.convert("RGBA").tobytes()
    with Image.open(path_or_image) as decoded:
        return decoded.convert("RGBA").tobytes()


def read_chunks(encoded):
    assert encoded.startswith(PNG_SIGNATURE)
    offset, chunks = 8, []
    while offset < len(encoded):
        length = struct.unpack_from(">I", encoded, offset)[0]
        kind = encoded[offset + 4 : offset + 8]
        data = encoded[offset + 8 : offset + 8 + length]
        checksum = struct.unpack_from(">I", encoded, offset + 8 + length)[0]
        assert checksum == zlib.crc32(kind + data)
        chunks.append((kind, length))
        offset += length + 12
    assert offset == len(encoded)
    return chunks


@pytest.mark.parametrize("mode", ["L", "LA", "RGB", "RGBA"])
@pytest.mark.parametrize("size", [(1, 1), (1, 257), (37, 259), (512, 300)])
def test_png_roundtrip_pixels_and_chunk_checksums(mode, size, tmp_path):
    channels = Image.getmodebands(mode)
    raw = random.Random(42).randbytes(size[0] * size[1] * channels)
    image = Image.frombytes(mode, size, raw)
    destination = tmp_path / "grid.png"
    novagrid.encode_png(image, destination)
    with Image.open(destination) as decoded:
        assert decoded.format == "PNG"
        assert decoded.size == size and decoded.convert(mode).tobytes() == raw
    chunks = read_chunks(destination.read_bytes())
    kinds = [kind for kind, _ in chunks]
    assert kinds[0] == b"IHDR" and kinds[-1] == b"IEND"
    assert (
        {b"IHDR", b"IDAT", b"IEND"}
        <= set(kinds)
        <= {
            b"IHDR",
            b"PLTE",
            b"tRNS",
            b"IDAT",
            b"IEND",
        }
    )
    assert all(length <= 64 * 1024 for kind, length in chunks if kind == b"IDAT")


def test_png_drops_embedded_profiles_and_rejects_unsupported_input(
    monkeypatch, tmp_path
):
    image = Image.new("RGB", (8, 8), "red")
    image.info["icc_profile"] = b"not-a-real-profile"
    destination = tmp_path / "profile.png"
    novagrid.encode_png(image, destination)
    assert b"iCCP" not in destination.read_bytes()
    with pytest.raises(ValueError):
        novagrid.encode_png(Image.new("F", (1, 1)), destination)
    monkeypatch.setattr(novagrid, "MAX_PIXELS", 100)
    with pytest.raises(ValueError):
        novagrid.encode_png(Image.new("L", (11, 10)), destination)


@pytest.mark.parametrize("size", [(300, 160), (1000, 500)])
def test_graphics_are_lossless_including_hidden_rgb(size, tmp_path):
    image = Image.new("RGBA", size, (15, 24, 35, 190))
    draw = ImageDraw.Draw(image)
    # Nonzero RGB under zero alpha must survive: "lossless" means every byte.
    draw.rectangle((25, 30, 225, 120), fill=(100, 240, 255, 0))
    draw.text((30, 40), "NovaGrid 20x / screenshot", fill="white")
    destination = tmp_path / "out.webp"
    assert novagrid.compress(image, destination) == (".webp", "webp-lossless")
    assert rgba_bytes(destination) == rgba_bytes(image)


@pytest.mark.parametrize(("size", "sampled"), [((200, 150), False), ((640, 480), True)])
def test_texture_uses_lossy_webp_and_stays_close(size, sampled, tmp_path):
    image = texture(size)
    assert (novagrid._grid_sample(image) is not image) == sampled
    destination = tmp_path / "out.webp"
    assert novagrid.compress(image, destination) == (".webp", "webp-lossy")
    with Image.open(destination) as decoded:
        assert decoded.format == "WEBP" and decoded.size == size
        error = ImageStat.Stat(ImageChops.difference(decoded.convert("RGB"), image))
    assert max(error.mean) < 6
    assert destination.stat().st_size < size[0] * size[1] * 3 // 20


@pytest.mark.parametrize(
    ("size", "sampled"), [((200, 100), False), ((1000, 500), True)]
)
def test_flat_interface_uses_lossless_webp_whatever_the_size(size, sampled, tmp_path):
    image = interface(size)
    assert (novagrid._grid_sample(image) is not image) == sampled
    destination = tmp_path / "out.webp"
    assert novagrid.compress(image, destination) == (".webp", "webp-lossless")
    assert rgba_bytes(destination) == rgba_bytes(image)


def test_lossy_alpha_is_kept_exactly(tmp_path):
    image = texture((640, 480), mode="RGBA")
    image.putalpha(Image.linear_gradient("L").resize(image.size))
    destination = tmp_path / "out.webp"
    assert novagrid.compress(image, destination) == (".webp", "webp-lossy")
    with Image.open(destination) as decoded:
        assert decoded.mode == "RGBA"
        assert decoded.getchannel("A").tobytes() == image.getchannel("A").tobytes()


@pytest.mark.parametrize("mode", ["P", "L", "RGB"])
def test_palette_and_color_key_transparency_survive(mode, tmp_path):
    image = Image.new(mode, (80, 40))
    if mode == "P":
        image.putpalette([255, 0, 0, 0, 255, 0] + [0] * 762)
        image.paste(1, (40, 0, 80, 40))
        image.info["transparency"] = bytes((0, 128))
    elif mode == "L":
        image.paste(100, (40, 0, 80, 40))
        image.info["transparency"] = 0
    else:
        image.paste((255, 0, 0), (40, 0, 80, 40))
        image.info["transparency"] = (0, 0, 0)
    source, destination = tmp_path / "source.png", tmp_path / "result.bin"
    image.save(source, compress_level=0)
    expected = rgba_bytes(source)
    assert convert(source, destination, "compress") == (".webp", True)
    assert rgba_bytes(destination) == expected


@pytest.mark.parametrize(
    "palette_case", ["one-channel", "two-channel", "collision", "alpha"]
)
def test_close_colors_and_alpha_are_never_merged(palette_case, tmp_path):
    if palette_case == "one-channel":
        colors = [(i, 255 - i, (i * 13) % 256, 255) for i in range(256)]
    elif palette_case == "two-channel":
        colors = [(x, y, 60, 255) for x in range(16) for y in range(16)]
    elif palette_case == "collision":
        colors = [
            (r, g, b, a)
            for r in (0, 1)
            for g in (0, 1)
            for b in (0, 1)
            for a in (0, 128)
        ]
    else:
        colors = [(x, 0, 0, a) for x in range(16) for a in range(16)]
    raw = bytes(v for index in range(81 * 1031) for v in colors[index % len(colors)])
    image = Image.frombytes("RGBA", (81, 1031), raw)
    output = tmp_path / "palette.webp"
    novagrid.compress(image, output, quality=95)
    assert rgba_bytes(output) == raw


def test_flat_graphics_remove_metadata_and_shrink_through_the_worker(tmp_path):
    image = interface((600, 300), "RGBA")
    source, destination = tmp_path / "input.png", tmp_path / "output.bin"
    meta = PngImagePlugin.PngInfo()
    meta.add_text("private", "removed")
    image.save(source, compress_level=0, pnginfo=meta)
    assert convert(source, destination, "compress") == (".webp", True)
    assert destination.stat().st_size < source.stat().st_size // 20
    with Image.open(destination) as decoded:
        assert "private" not in decoded.info and not decoded.info.get("icc_profile")
        assert decoded.convert("RGBA").tobytes() == image.tobytes()


def test_jpeg_source_uses_optimized_tables_and_stays_decodable(tmp_path):
    image = texture((512, 512))
    destination = tmp_path / "result.jpg"
    assert novagrid.compress(image, destination, jpeg_source=True) == (
        ".jpg",
        "jpeg-optimized",
    )
    plain = io.BytesIO()
    image.save(plain, "JPEG", quality=78, optimize=False)
    assert destination.stat().st_size < plain.tell()
    with Image.open(destination) as decoded:
        assert decoded.format == "JPEG" and decoded.size == image.size


def test_exact_images_beyond_the_memory_budget_use_a_bounded_png(monkeypatch, tmp_path):
    monkeypatch.setattr(novagrid, "LOSSLESS_MAX_PIXELS", 1000)
    image = interface((1000, 500))
    destination = tmp_path / "large.png"
    assert novagrid.compress(image, destination) == (".png", "png-large")
    with Image.open(destination) as decoded:
        assert decoded.format == "PNG" and rgba_bytes(destination) == rgba_bytes(image)


@pytest.mark.parametrize("size", [(200, 150), (640, 480)])
def test_exact_pixels_that_do_not_shrink_may_trade_fidelity_once(
    size, monkeypatch, tmp_path
):
    # Force the exact family independently of the sampled density veto.
    monkeypatch.setattr(novagrid, "LOSSLESS_BUDGET", 1000)
    monkeypatch.setattr(novagrid, "LOSSLESS_MAX_BYTES_PER_PIXEL", 1000)
    image = texture(size)
    destination = tmp_path / "out.webp"
    assert novagrid.compress(image, destination, source_bytes=1025) == (
        ".webp",
        "webp-lossy-fallback",
    )
    lossy = novagrid._webp_bytes(image, **novagrid._lossy(78, size[0] * size[1]))
    assert destination.read_bytes() == lossy
    # Without a source size to beat, or with transparency, pixels stay exact.
    assert novagrid.compress(image, destination) == (".webp", "webp-lossless")
    translucent = image.convert("RGBA")
    translucent.putalpha(Image.linear_gradient("L").resize(size))
    assert novagrid.compress(translucent, destination, source_bytes=1025) == (
        ".webp",
        "webp-lossless",
    )
    assert rgba_bytes(destination) == rgba_bytes(translucent)


def test_invalid_parameters_and_limits(monkeypatch, tmp_path):
    image = texture((64, 48))
    destination = tmp_path / "result.webp"
    for quality in (39, 96, True, "78"):
        with pytest.raises(ValueError):
            novagrid.compress(image, destination, quality)
    monkeypatch.setattr(novagrid, "MAX_EDGE", 32)
    with pytest.raises(ValueError):
        novagrid.compress(image, destination)


def test_encoder_state_never_leaks_between_saves_of_one_image():
    image = texture((120, 90))
    fresh = novagrid._webp_bytes(image.copy(), **novagrid._lossy(78, 120 * 90))
    exact = novagrid._webp_bytes(image, **novagrid._lossless(0))
    assert novagrid._webp_bytes(image, **novagrid._lossy(78, 120 * 90)) == fresh
    assert len(fresh) < len(exact)


def test_grid_sample_covers_the_corners_and_survives_narrow_images():
    image = Image.frombytes(
        "RGB", (500, 400), random.Random(3).randbytes(500 * 400 * 3)
    )
    sample = novagrid._grid_sample(image)
    tile = novagrid.GRID_TILE
    assert sample.size == (novagrid.GRID_COLS * tile, novagrid.GRID_ROWS * tile)
    assert sample.crop((0, 0, tile, tile)).tobytes() == (
        image.crop((0, 0, tile, tile)).tobytes()
    )
    assert sample.crop((sample.width - tile, sample.height - tile, *sample.size)) == (
        image.crop((500 - tile, 400 - tile, 500, 400))
    )
    small = Image.new("RGB", (40, 40))
    assert novagrid._grid_sample(small) is small
    narrow = novagrid._grid_sample(Image.new("L", (20, 10000)))
    assert narrow.size == (20, novagrid.GRID_ROWS * novagrid.GRID_TILE)


def test_no_saving_passthrough_keeps_the_original(tmp_path):
    source, destination = tmp_path / "tiny.jpg", tmp_path / "result.bin"
    Image.new("RGB", (8, 8), (120, 130, 140)).save(source, quality=1, optimize=True)
    assert convert(source, destination, "compress") == (".jpg", False)
    assert destination.read_bytes() == source.read_bytes()


async def test_real_worker_novagrid_and_no_savings_are_not_billed(tmp_path):
    source = tmp_path / "tiny.jpg"
    Image.new("RGB", (8, 8), (120, 130, 140)).save(source, quality=1, optimize=True)
    engine = FileTools()
    await engine.start()
    try:
        job = await engine.submit(
            "101", [(source.name, source.read_bytes())], "compress"
        )
        await engine.tasks[job]
        result = engine.result("101", job)
        assert result["state"] == "done" and result["points"] == 0
        assert result["engine"] == novagrid.VERSION
        assert engine.download("101", job)[0].read_bytes() == source.read_bytes()
        assert engine.quota.snapshot("101")["reserved"] == 0
    finally:
        await engine.close()


def test_image_batch_archive_skips_recompressing_encoded_images(tmp_path):
    import zipfile

    from src.services.tool_worker import run

    for index in (0, 1):
        Image.new("RGB", (70, 30), (index * 50, 100, 200)).save(
            tmp_path / f"input-{index}.png", compress_level=0
        )
    (tmp_path / "request.json").write_text(
        json.dumps(
            {
                "files": [
                    {"stored": f"input-{i}.png", "name": f"image-{i}.png"}
                    for i in (0, 1)
                ],
                "operation": "compress",
                "quality": 78,
                "maxEdge": 4096,
            }
        ),
        encoding="utf-8",
    )
    run(tmp_path)
    with zipfile.ZipFile(tmp_path / "result.bin") as archive:
        assert archive.testzip() is None
        assert all(
            info.compress_type == zipfile.ZIP_STORED for info in archive.infolist()
        )
        for name in archive.namelist():
            with Image.open(io.BytesIO(archive.read(name))) as image:
                assert image.size == (70, 30)


def test_high_bit_depth_is_not_silently_reduced_by_compression(tmp_path):
    source = tmp_path / "16-bit.png"
    image = Image.frombytes("I;16", (10, 10), b"\x10\x80" * 100)
    image.save(source)
    with pytest.raises(ValueError, match="高精度"):
        convert(source, tmp_path / "output.bin", "compress")


@pytest.mark.parametrize("mode", ["L", "RGB", "P"])
def test_direct_compression_preserves_color_key_transparency(mode, tmp_path):
    image = Image.new(mode, (80, 40))
    if mode == "P":
        image.putpalette([0, 0, 0, 255, 0, 0] + [0] * 762)
        image.paste(1, (40, 0, 80, 40))
        image.info["transparency"] = bytes((0, 128))
    elif mode == "L":
        image.paste(200, (40, 0, 80, 40))
        image.info["transparency"] = 0
    else:
        image.paste((255, 0, 0), (40, 0, 80, 40))
        image.info["transparency"] = (0, 0, 0)
    expected = rgba_bytes(image)
    destination = tmp_path / "direct.webp"
    assert novagrid.compress(image, destination) == (".webp", "webp-lossless")
    assert rgba_bytes(destination) == expected
    assert rgba_bytes(image) == expected


@pytest.mark.parametrize("mode", ["I;16", "I", "F"])
@pytest.mark.parametrize("jpeg_source", [False, True])
def test_direct_compression_rejects_high_precision_pixels(mode, jpeg_source, tmp_path):
    image = Image.new(mode, (16, 16))
    with pytest.raises(ValueError, match="高精度"):
        novagrid.compress(image, tmp_path / "result.bin", jpeg_source=jpeg_source)


@pytest.mark.parametrize("mode", ["L", "RGB", "P"])
def test_resizing_color_key_images_interpolates_alpha_before_encoding(mode, tmp_path):
    image = Image.new(mode, (512, 512))
    if mode == "P":
        image.putpalette([0, 0, 0, 255, 0, 0] + [0] * 762)
        image.paste(1, (257, 0, 512, 512))
        image.info["transparency"] = bytes((0, 128))
    elif mode == "L":
        image.paste(200, (257, 0, 512, 512))
        image.info["transparency"] = 0
    else:
        image.paste((255, 0, 0), (257, 0, 512, 512))
        image.info["transparency"] = (0, 0, 0)
    source, destination = tmp_path / "source.png", tmp_path / "result.png"
    image.save(source)
    with Image.open(source) as decoded:
        with decoded.convert("RGBA") as expected:
            expected.thumbnail((256, 256), Image.Resampling.LANCZOS)
            expected_pixels = expected.tobytes()
    assert convert(source, destination, "png", max_edge=256) == (".png", True)
    assert rgba_bytes(destination) == expected_pixels


@pytest.mark.parametrize("size", [(20, 8192), (8192, 20)])
def test_strip_noise_uses_lossy_encoding_without_repeated_sample_tiles(size, tmp_path):
    image = Image.frombytes(
        "RGB", size, random.Random(9).randbytes(size[0] * size[1] * 3)
    )
    destination = tmp_path / "strip.webp"
    assert novagrid.compress(image, destination) == (".webp", "webp-lossy")
    with Image.open(destination) as decoded:
        assert decoded.format == "WEBP" and decoded.size == size


@pytest.mark.parametrize("size", [(40, 4096), (4096, 40), (20, 8192), (8192, 20)])
def test_rectangular_grid_samples_include_all_four_image_corners(size):
    with Image.new("RGB", size) as image:
        corners = [
            (0, 0),
            (size[0] - 1, 0),
            (0, size[1] - 1),
            (size[0] - 1, size[1] - 1),
        ]
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]
        for corner, color in zip(corners, colors):
            image.putpixel(corner, color)
        with novagrid._grid_sample(image) as sample:
            assert sample is not image
            assert sample.getpixel((0, 0)) == colors[0]
            assert sample.getpixel((sample.width - 1, 0)) == colors[1]
            assert sample.getpixel((0, sample.height - 1)) == colors[2]
            assert sample.getpixel((sample.width - 1, sample.height - 1)) == colors[3]


@pytest.mark.parametrize("mode", ["L", "RGB", "RGBA"])
def test_encoder_failure_preserves_the_caller_and_releases_converted_pixels(
    mode, monkeypatch, tmp_path
):
    image = Image.new(mode, (16, 16))
    original_pixels = image.tobytes()
    captured = []

    def fail_save(encoded, *args, **kwargs):
        captured.append(encoded)
        raise OSError("Encoder unavailable")

    monkeypatch.setattr(Image.Image, "save", fail_save)
    with pytest.raises(OSError, match="Encoder unavailable"):
        novagrid.compress(image, tmp_path / "result.webp")
    assert image.tobytes() == original_pixels
    for encoded in captured:
        if encoded is not image:
            with pytest.raises(ValueError, match="closed"):
                encoded.tobytes()


def test_worker_failure_closes_palette_conversion_and_preserves_input(
    monkeypatch, tmp_path
):
    source = tmp_path / "source.png"
    image = Image.new("P", (512, 512))
    image.putpalette([0, 0, 0, 255, 0, 0] + [0] * 762)
    image.info["transparency"] = bytes((0, 128))
    image.save(source)
    original_bytes = source.read_bytes()
    captured = []

    def fail_save(encoded, *args, **kwargs):
        captured.append(encoded)
        raise OSError("Encoder unavailable")

    monkeypatch.setattr(Image.Image, "save", fail_save)
    with pytest.raises(OSError, match="Encoder unavailable"):
        convert(source, tmp_path / "result.png", "png", max_edge=256)
    assert source.read_bytes() == original_bytes
    assert captured
    for encoded in captured:
        with pytest.raises(ValueError, match="closed"):
            encoded.tobytes()
