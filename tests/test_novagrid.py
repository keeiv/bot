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


@pytest.mark.parametrize(
    ("size", "mode"),
    [((200, 150), "RGB"), ((640, 480), "RGB"), ((640, 480), "RGBA"), ((640, 480), "L")],
)
def test_noise_is_never_kept_exact(size, mode, tmp_path):
    raw = random.Random(5).randbytes(size[0] * size[1] * Image.getmodebands(mode))
    noise = Image.frombytes(mode, size, raw)
    destination = tmp_path / "noise.webp"
    assert novagrid.compress(noise, destination) == (".webp", "webp-lossy")


def test_tiny_images_skip_the_density_check(tmp_path):
    # 32 x 32 random colors cost many bits per pixel yet are mostly container.
    raw = random.Random(9).randbytes(32 * 32 * 3)
    icon = Image.frombytes("RGB", (32, 32), raw)
    destination = tmp_path / "icon.webp"
    assert novagrid.compress(icon, destination) == (".webp", "webp-lossless")
    assert rgba_bytes(destination) == rgba_bytes(icon)


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


def test_large_exact_images_use_the_fastest_lossless_setting(monkeypatch, tmp_path):
    assert novagrid._lossless(1)["quality"] == 75
    assert novagrid._lossless(novagrid.LOSSLESS_FULL_EFFORT_PIXELS + 1)["quality"] == 0
    monkeypatch.setattr(novagrid, "LOSSLESS_FULL_EFFORT_PIXELS", 1000)
    image = interface((1000, 500))
    destination = tmp_path / "fast.webp"
    assert novagrid.compress(image, destination) == (".webp", "webp-lossless")
    fast = novagrid._webp_bytes(image, **novagrid._lossless(10**6))
    assert destination.read_bytes() == fast
    assert len(fast) > len(novagrid._webp_bytes(image, **novagrid._lossless(0)))
    assert rgba_bytes(destination) == rgba_bytes(image)


@pytest.mark.parametrize("size", [(200, 150), (640, 480)])
def test_exact_pixels_that_do_not_shrink_may_trade_fidelity_once(
    size, monkeypatch, tmp_path
):
    # Huge limits force the exact family, as for a graphic with soft shading.
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
