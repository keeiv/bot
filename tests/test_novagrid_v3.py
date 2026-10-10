"""NovaGrid/3: lossless channel reduction and size-scaled encoder effort."""

import random

from PIL import Image
from PIL import ImageDraw
import pytest

from src.services import novagrid


def rgba_bytes(path_or_image):
    if isinstance(path_or_image, Image.Image):
        return path_or_image.convert("RGBA").tobytes()
    with Image.open(path_or_image) as decoded:
        return decoded.convert("RGBA").tobytes()


def gradient(size, mode):
    """Gray ramps with text: compressible, and every band holds the same values."""
    base = Image.linear_gradient("L").resize(size)
    ImageDraw.Draw(base).text((6, 6), "NovaGrid", fill=255)
    return base.convert(mode)


@pytest.mark.parametrize(
    ("mode", "alpha", "expected"),
    [
        ("RGB", None, "L"),
        ("RGBA", 255, "L"),
        ("RGBA", 90, "LA"),
    ],
)
def test_gray_images_shed_redundant_bands_without_changing_pixels(
    mode, alpha, expected
):
    image = gradient((64, 48), mode)
    if alpha is not None:
        image.putalpha(alpha)
    with novagrid._png_reduced(image) as reduced:
        assert reduced is not image and reduced.mode == expected
        assert rgba_bytes(reduced) == rgba_bytes(image)


def test_opaque_color_images_drop_only_the_alpha_band():
    raw = random.Random(3).randbytes(32 * 24 * 4)
    image = Image.frombytes("RGBA", (32, 24), raw)
    image.putalpha(255)
    with novagrid._png_reduced(image) as reduced:
        assert reduced.mode == "RGB"
        assert rgba_bytes(reduced) == rgba_bytes(image)


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L", "LA"])
def test_images_with_nothing_to_shed_are_returned_as_is(mode):
    raw = random.Random(4).randbytes(16 * 16 * Image.getmodebands(mode))
    image = Image.frombytes(mode, (16, 16), raw)
    if mode == "RGBA":
        image.putalpha(Image.frombytes("L", (16, 16), random.Random(5).randbytes(256)))
    assert novagrid._png_reduced(image) is image


def test_one_off_gray_pixel_keeps_all_color_bands():
    image = gradient((64, 48), "RGB")
    image.putpixel((10, 10), (1, 2, 3))
    assert novagrid._png_reduced(image) is image


def test_large_exact_gray_images_are_stored_as_smaller_pngs(monkeypatch, tmp_path):
    monkeypatch.setattr(novagrid, "LOSSLESS_MAX_PIXELS", 20 * 20)
    image = gradient((400, 300), "RGBA")
    destination = tmp_path / "out.png"
    assert novagrid.compress(image, destination) == (".png", "png-large")
    with Image.open(destination) as decoded:
        assert decoded.mode in {"L", "LA"}
    assert rgba_bytes(destination) == rgba_bytes(image)


def interface(size, mode="RGB"):
    image = Image.new(mode, size, "#0b1019")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((10, 10, size[0] - 10, size[1] // 2), 8, fill="#152438")
    draw.text((24, 24), "NovaGrid / service 01 / online 99.86%", fill="white")
    return image


def texture(size, seed=7):
    raw = random.Random(seed).randbytes(16 * 12 * 3)
    return Image.frombytes("RGB", (16, 12), raw).resize(size, Image.Resampling.BICUBIC)


def test_effort_schedule():
    full, lossy_limit = (
        novagrid.LOSSLESS_FULL_EFFORT_PIXELS,
        novagrid.LOSSY_STRONG_PIXELS,
    )
    assert novagrid.WHOLE_PIXELS < lossy_limit < full
    # Only the small-image comparison uses the slower lossless method.
    for pixels in (1, novagrid.WHOLE_PIXELS, full):
        assert novagrid._lossless(pixels) == {
            "lossless": True,
            "quality": 75,
            "method": 1,
        }
    assert novagrid._lossless(full + 1)["quality"] == 0
    assert novagrid._lossless_strong()["method"] == 4
    assert novagrid._lossy(78, lossy_limit)["method"] == 4
    assert novagrid._lossy(78, lossy_limit + 1)["method"] == 2
    for pixels in (1, lossy_limit, lossy_limit + 1, full + 1):
        assert novagrid._lossy(61, pixels)["quality"] == 61
    assert novagrid._trial_lossy(61) == {"lossless": False, "quality": 61, "method": 2}


def test_the_verdict_never_depends_on_the_final_effort(monkeypatch):
    sizes = ((400, 300), (1600, 900))
    before = [
        (novagrid._trial(interface(s), 78)[3], novagrid._trial(texture(s), 78)[3])
        for s in sizes
    ]
    assert before == [(True, False)] * len(sizes)
    # Whatever the final settings become, the trial settings stay put.
    monkeypatch.setattr(
        novagrid,
        "_lossless_strong",
        lambda: {"lossless": True, "quality": 0, "method": 0},
    )
    monkeypatch.setattr(novagrid, "LOSSY_STRONG_PIXELS", 1)
    after = [
        (novagrid._trial(interface(s), 78)[3], novagrid._trial(texture(s), 78)[3])
        for s in sizes
    ]
    assert after == before


@pytest.mark.parametrize("size", [(200, 100), (320, 300)])
def test_small_exact_images_keep_the_smaller_of_two_encodes(size, tmp_path):
    image = interface(size)
    assert size[0] * size[1] <= novagrid.WHOLE_PIXELS
    baseline = novagrid._webp_bytes(image, **novagrid._lossless(size[0] * size[1]))
    strong = novagrid._webp_bytes(image, **novagrid._lossless_strong())
    destination = tmp_path / "out.webp"
    assert novagrid.compress(image, destination) == (".webp", "webp-lossless")
    assert destination.read_bytes() == min(baseline, strong, key=len)
    assert rgba_bytes(destination) == rgba_bytes(image)


def test_a_stronger_encode_that_comes_out_larger_is_discarded(monkeypatch, tmp_path):
    # libwebp methods are not monotone (real images: up to +3.8%, a full-frame alpha
    # gradient: 2.4x), so the baseline must win whenever it is smaller.
    image = interface((200, 100))
    baseline = novagrid._webp_bytes(image, **novagrid._lossless(200 * 100))
    monkeypatch.setattr(
        novagrid,
        "_lossless_strong",
        lambda: {"lossless": True, "quality": 0, "method": 0},
    )
    worse = novagrid._webp_bytes(image, **novagrid._lossless_strong())
    assert len(worse) > len(baseline)
    destination = tmp_path / "out.webp"
    assert novagrid.compress(image, destination) == (".webp", "webp-lossless")
    assert destination.read_bytes() == baseline


@pytest.mark.parametrize("size", [(640, 480), (900, 700)])
def test_larger_exact_images_use_the_baseline_setting(size, tmp_path):
    image = interface(size)
    destination = tmp_path / "out.webp"
    assert novagrid.compress(image, destination) == (".webp", "webp-lossless")
    assert destination.read_bytes() == novagrid._webp_bytes(
        image, **novagrid._lossless(size[0] * size[1])
    )
    assert rgba_bytes(destination) == rgba_bytes(image)


@pytest.mark.parametrize("size", [(200, 150), (640, 480), (900, 700)])
def test_lossy_output_uses_the_scaled_effort(size, tmp_path):
    image = texture(size)
    destination = tmp_path / "out.webp"
    assert novagrid.compress(image, destination) == (".webp", "webp-lossy")
    assert destination.read_bytes() == novagrid._webp_bytes(
        image, **novagrid._lossy(78, size[0] * size[1])
    )


def test_small_graphics_with_hidden_rgb_stay_bit_exact(tmp_path):
    image = interface((320, 200), "RGBA")
    image.putpixel((3, 3), (200, 10, 30, 0))
    destination = tmp_path / "out.webp"
    assert novagrid.compress(image, destination) == (".webp", "webp-lossless")
    assert rgba_bytes(destination) == rgba_bytes(image)


def test_whole_image_fidelity_trade_picks_the_smaller_result(monkeypatch, tmp_path):
    monkeypatch.setattr(novagrid, "LOSSLESS_BUDGET", 1000)
    monkeypatch.setattr(novagrid, "LOSSLESS_MAX_BYTES_PER_PIXEL", 1000)
    image = texture((200, 150))
    destination = tmp_path / "out.webp"
    # An exact encode that beats the source stays exact.
    assert novagrid.compress(image, destination, source_bytes=10**7) == (
        ".webp",
        "webp-lossless",
    )
    exact = destination.read_bytes()
    # One that does not shrink the source may switch to the smaller lossy encode.
    assert novagrid.compress(image, destination, source_bytes=2048) == (
        ".webp",
        "webp-lossy-fallback",
    )
    assert destination.stat().st_size < len(exact)


@pytest.mark.parametrize(
    ("share", "expected"),
    [(0.5, False), (0.97, False), (0.99, True), (1.0, True), (1.5, True)],
)
def test_exact_pixels_must_save_a_little_to_stay_exact(share, expected):
    image = Image.new("RGB", (8, 8))
    size = 10_000
    assert novagrid._can_trade_fidelity(image, size, int(size / share)) is expected
    # Tiny sources, unknown sources and transparency never trade.
    assert not novagrid._can_trade_fidelity(image, size, None)
    assert not novagrid._can_trade_fidelity(image, 2000, 1024)
    assert not novagrid._can_trade_fidelity(
        Image.new("RGBA", (8, 8), (1, 2, 3, 4)), size, size
    )


@pytest.mark.parametrize("size", [(200, 150), (640, 480)])
def test_a_borderline_saving_trades_fidelity_but_a_real_one_does_not(
    size, monkeypatch, tmp_path
):
    # Force the exact family, as for a graphic whose full encode proves photo-like.
    monkeypatch.setattr(novagrid, "LOSSLESS_BUDGET", 1000)
    monkeypatch.setattr(novagrid, "LOSSLESS_MAX_BYTES_PER_PIXEL", 1000)
    image = texture(size)
    pixels = size[0] * size[1]
    exact = len(novagrid._webp_bytes(image, **novagrid._lossless(pixels)))
    if pixels <= novagrid.WHOLE_PIXELS:
        strong = novagrid._webp_bytes(image, **novagrid._lossless_strong())
        exact = min(exact, len(strong))
    lossy = len(novagrid._webp_bytes(image, **novagrid._lossy(78, pixels)))
    assert lossy < exact
    destination = tmp_path / "out.webp"
    # The exact encode beats the source by only 0.5%: not worth the exactness.
    borderline = int(exact * 1.005)
    assert borderline > 1024 and exact >= borderline * novagrid.EXACT_KEEP_RATIO
    assert novagrid.compress(image, destination, source_bytes=borderline) == (
        ".webp",
        "webp-lossy-fallback",
    )
    assert destination.stat().st_size == lossy
    # A source 30% larger than the exact encode is a real saving: stay exact.
    assert novagrid.compress(image, destination, source_bytes=int(exact * 1.3)) == (
        ".webp",
        "webp-lossless",
    )
    assert rgba_bytes(destination) == rgba_bytes(image)


@pytest.fixture
def created_images(monkeypatch):
    """Every Pillow image constructed while a test body runs."""
    created = []
    original = Image.Image.__init__

    def tracking(self, *args, **kwargs):
        original(self, *args, **kwargs)
        created.append(self)

    monkeypatch.setattr(Image.Image, "__init__", tracking)
    return created


def closed(image):
    """True once the pixels are released (or were never allocated)."""
    return image._im is None or type(image._im).__name__ == "DeferredError"


def test_png_reduction_releases_every_intermediate_image(created_images):
    image = gradient((64, 48), "RGBA")
    image.putalpha(90)
    start = len(created_images)
    with novagrid._png_reduced(image) as reduced:
        extras = [i for i in created_images[start:] if i is not reduced]
        assert extras and all(closed(i) for i in extras)
        assert not closed(reduced) and not closed(image)


def test_png_reduction_releases_images_when_a_step_fails(monkeypatch, created_images):
    image = gradient((64, 48), "RGBA")
    image.putalpha(90)
    reached = []
    real = novagrid.ImageChops.difference

    def flaky(first, second):
        # The 1/16 probe is tiny; fail only on a comparison of full-size bands.
        if first.size == image.size:
            reached.append(first.size)
            raise RuntimeError("boom")
        return real(first, second)

    monkeypatch.setattr(novagrid.ImageChops, "difference", flaky)
    start = len(created_images)
    with pytest.raises(RuntimeError):
        novagrid._png_reduced(image)
    assert reached == [image.size]
    # The full-size red band and the alpha band were both live when it failed.
    assert len(created_images[start:]) >= 2
    assert all(closed(i) for i in created_images[start:])
    assert not closed(image)


def test_grid_sampling_releases_its_mosaic_when_a_tile_fails(
    monkeypatch, created_images
):
    image = Image.new("RGB", (640, 480), "#102030")
    pastes = []
    real = Image.Image.paste

    def flaky(self, *args, **kwargs):
        pastes.append(1)
        if len(pastes) == 3:
            raise RuntimeError("boom")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "paste", flaky)
    start = len(created_images)
    with pytest.raises(RuntimeError):
        novagrid._grid_sample(image)
    assert all(closed(i) for i in created_images[start:])
    assert not closed(image)


@pytest.mark.parametrize("size", [(1, 1), (15, 15), (16, 1), (1, 40), (31, 17)])
def test_png_reduction_handles_images_smaller_than_the_probe_step(size):
    for mode, expected in (("RGB", "L"), ("RGBA", "L")):
        image = Image.new(mode, size, (90, 90, 90, 255)[: len(mode)])
        with novagrid._png_reduced(image) as reduced:
            assert reduced.mode == expected
            assert rgba_bytes(reduced) == rgba_bytes(image)


def test_a_hidden_non_gray_pixel_under_transparency_is_never_flattened():
    image = gradient((64, 48), "RGBA")
    image.putalpha(255)
    image.putpixel((10, 20), (10, 20, 30, 0))
    reduced = novagrid._png_reduced(image)
    # The all-opaque shortcut does not apply (one pixel is transparent) and the
    # colors differ there, so the image must come back untouched.
    assert reduced is image
    assert image.getpixel((10, 20)) == (10, 20, 30, 0)


def test_a_non_gray_pixel_missed_by_the_probe_is_found_by_the_full_comparison():
    image = gradient((640, 480), "RGBA")
    image.putalpha(120)
    # The 1/16 probe samples pixels near multiples of 16; (17, 17) is not one.
    image.putpixel((17, 17), (1, 2, 3, 120))
    assert novagrid._probably_gray(image) is True
    assert novagrid._png_reduced(image) is image


def test_rgba_palette_transparency_survives_compression(tmp_path):
    palette = Image.new("P", (200, 100))
    palette.putpalette([0, 0, 0, 255, 0, 0, 0, 255, 0])
    ImageDraw.Draw(palette).rectangle((20, 20, 120, 70), fill=1)
    ImageDraw.Draw(palette).rectangle((60, 40, 180, 90), fill=2)
    palette.info["transparency"] = 2
    palette.apply_transparency()
    assert "transparency" not in palette.info and palette.palette.mode == "RGBA"
    expected = palette.convert("RGBA")
    assert expected.getchannel("A").getextrema() == (0, 255)
    for converted in (novagrid.normalize(palette), novagrid._webp_ready(palette)):
        assert converted.mode == "RGBA"
        assert converted.tobytes() == expected.tobytes()
    destination = tmp_path / "out.webp"
    novagrid.compress(palette, destination)
    with Image.open(destination) as decoded:
        assert decoded.mode == "RGBA"
        assert decoded.getchannel("A").tobytes() == expected.getchannel("A").tobytes()


def test_the_verdict_and_baseline_of_small_images_ignore_the_strong_setting(
    monkeypatch, tmp_path
):
    for image in (interface((200, 100)), texture((200, 150))):
        pixels = image.width * image.height
        assert pixels <= novagrid.WHOLE_PIXELS
        whole, baseline, _, verdict = novagrid._trial(image, 78)
        assert whole and baseline == novagrid._webp_bytes(
            image, **novagrid._lossless(pixels)
        )
        monkeypatch.setattr(
            novagrid,
            "_lossless_strong",
            lambda: {"lossless": True, "quality": 0, "method": 0},
        )
        assert novagrid._trial(image, 78)[1:] == (
            baseline,
            novagrid._trial(image, 78)[2],
            verdict,
        )
        assert novagrid._trial(image, 78)[3] is verdict
        monkeypatch.undo()


def test_the_exact_keep_boundary_is_inclusive():
    image = Image.new("RGB", (8, 8))
    assert novagrid.EXACT_KEEP_RATIO == 0.98
    assert novagrid._can_trade_fidelity(image, 9800, 10_000) is True
    assert novagrid._can_trade_fidelity(image, 9799, 10_000) is False


def test_the_jpeg_branch_never_carries_comments_through(tmp_path):
    image = Image.new("RGB", (64, 48), (9, 9, 9))
    image.info["comment"] = b"private comment"
    image.info["icc_profile"] = b"not-a-profile"
    image.info["exif"] = b"Exif\x00\x00private"
    destination = tmp_path / "out.jpg"
    assert novagrid.compress(image, destination, jpeg_source=True)[0] == ".jpg"
    data = destination.read_bytes()
    for secret in (b"private", b"not-a-profile"):
        assert secret not in data
    with Image.open(destination) as decoded:
        assert decoded.info.get("comment") is None


@pytest.mark.parametrize("alpha", [200, 255])
def test_premultiplied_gray_with_alpha_is_accepted(alpha, tmp_path):
    image = Image.new("La", (40, 30), (100, alpha))
    expected = image.convert("LA").convert("RGBA").tobytes()
    for converted in (novagrid.normalize(image), novagrid._webp_ready(image)):
        assert converted.mode == "RGBA"
        # Color as well as alpha: zeroed RGB with a correct alpha must not pass.
        assert converted.tobytes() == expected
        assert converted.getpixel((0, 0))[:3] != (0, 0, 0)
    destination = tmp_path / "out.webp"
    assert novagrid.compress(image, destination)[0] == ".webp"
    with Image.open(destination) as decoded:
        assert decoded.convert("RGBA").getpixel((0, 0))[3] == alpha


@pytest.mark.parametrize("size", [(200, 150), (900, 700)])
def test_trial_encodes_at_fixed_literal_settings(size):
    """Compare with literal options, not with the engine's own helpers."""
    for image in (interface(size), texture(size)):
        sample = novagrid._grid_sample(image)
        whole, lossless, lossy, _ = novagrid._trial(image, 78)
        assert whole == (sample is image)
        assert lossless == novagrid._webp_bytes(
            sample, lossless=True, quality=75, method=1
        )
        assert lossy == novagrid._webp_bytes(
            sample, lossless=False, quality=78, method=2
        )


STALE = {"lossless": False, "quality": 40, "method": 0, "exact": False}


def test_options_preset_on_the_image_cannot_override_the_engine(tmp_path):
    image = Image.new("RGB", (64, 48), (10, 20, 30))
    image.encoderinfo = dict(STALE)
    destination = tmp_path / "out.webp"
    assert novagrid.compress(image, destination) == (".webp", "webp-lossless")
    assert rgba_bytes(destination) == rgba_bytes(image)
    # The caller's own settings are handed back untouched.
    assert image.encoderinfo == STALE


def test_preset_options_are_restored_even_when_encoding_fails(monkeypatch, tmp_path):
    image = Image.new("RGB", (64, 48), (10, 20, 30))
    image.encoderinfo = dict(STALE)

    def fail(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(novagrid, "_compress_sampled", fail)
    with pytest.raises(RuntimeError):
        novagrid.compress(image, tmp_path / "out.webp")
    assert image.encoderinfo == STALE


def test_the_jpeg_branch_ignores_preset_comment_quality_and_exif(tmp_path):
    image = Image.new("RGB", (64, 48), (9, 9, 9))
    image.encoderinfo = {"comment": b"private comment", "quality": 1, "exif": b"Exif"}
    destination = tmp_path / "out.jpg"
    novagrid.compress(image, destination, jpeg_source=True)
    assert b"private comment" not in destination.read_bytes()
    with Image.open(destination) as decoded:
        assert decoded.info.get("comment") is None
        assert "exif" not in decoded.info


def test_a_failed_compress_leaves_no_partial_file(monkeypatch, tmp_path):
    monkeypatch.setattr(novagrid, "LOSSLESS_BUDGET", 1000)
    monkeypatch.setattr(novagrid, "LOSSLESS_MAX_BYTES_PER_PIXEL", 1000)
    image = texture((640, 480))
    destination = tmp_path / "out.webp"

    def break_copy(source, target, length=0):
        target.write(b"partial")
        raise OSError("disk full")

    # A sampled image that exact pixels do not shrink streams its lossy retry in.
    monkeypatch.setattr(novagrid.shutil, "copyfileobj", break_copy)
    with pytest.raises(OSError):
        novagrid.compress(image, destination, source_bytes=1025)
    assert not destination.exists()


def test_a_rejected_request_does_not_touch_an_existing_file(tmp_path):
    destination = tmp_path / "existing.webp"
    destination.write_bytes(b"keep me")
    image = Image.new("RGB", (8, 8))
    for kwargs in ({"quality": 39}, {"quality": "78"}):
        with pytest.raises(ValueError):
            novagrid.compress(image, destination, **kwargs)
    with pytest.raises(ValueError):
        novagrid.compress(Image.new("F", (8, 8)), destination)
    assert destination.read_bytes() == b"keep me"
