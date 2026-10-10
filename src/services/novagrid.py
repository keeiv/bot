"""NovaGrid/3: grid-sampled codec choice with size-scaled, lossless-first encoding.

A bounded mosaic stands in for the whole image. Lossless and lossy WebP are
trialled on that mosaic at a fixed, fast setting, so the verdict never depends on
how hard the final encode works. The winner is then encoded; small images try a
stronger setting and keep it only if it is smaller. At most one full-size lossy
fallback follows.
Pillow supplies decoding and the PNG/JPEG/WebP encoders (zlib-ng, libjpeg-turbo,
libwebp). The sampling policy, effort schedule and fallbacks are the engine; this
is not a new entropy codec.
"""

from collections.abc import Iterator
from contextlib import closing
from contextlib import contextmanager
from contextlib import suppress
import io
from pathlib import Path
import shutil
import tempfile
from typing import cast, IO, TypedDict

from PIL import Image
from PIL import ImageChops

VERSION = "NovaGrid/3"
MAX_PIXELS = 16_000_000
MAX_EDGE = 8192
# libwebp's lossless encoder needs roughly 25 bytes of working memory per pixel.
LOSSLESS_MAX_PIXELS = 8 * 1024 * 1024
# Smooth shading can cost ~0.3 s per megapixel at full effort; larger images drop
# to the fastest setting so a slow worker still finishes inside its job timeout.
LOSSLESS_FULL_EFFORT_PIXELS = 4 * 1024 * 1024
# Lossy method 4 averaged 5-7% fewer bytes than method 2 on real images at +36 ms
# or less up to this size; above it the extra time is not worth it.
LOSSY_STRONG_PIXELS = 512 * 1024
# Sampled graphics land near 0.2-3 and photos or smooth art near 5-10, so exact
# pixels are kept unless the sample costs over four times the lossy encoding.
LOSSLESS_BUDGET = 4.0
# Noise and film grain make both codecs expensive, so the ratio alone looks fair;
# exact pixels that cost over six bits each use the lossy path. Tiny whole images
# are mostly headers and skip this check; grid mosaics still check their density.
LOSSLESS_MAX_BYTES_PER_PIXEL = 0.75
DENSITY_MIN_PIXELS = 4096
# Exact pixels must come in under this share of the source to be worth keeping; a
# result within 2% of the source is a rounding error, not a saving, and a slightly
# stronger encoder must not flip an image between lossless and lossy.
EXACT_KEEP_RATIO = 0.98
GRID_TILE, GRID_COLS, GRID_ROWS = 32, 8, 6
# Up to this size the whole image is trialled instead of a mosaic.
WHOLE_PIXELS = 2 * GRID_COLS * GRID_ROWS * GRID_TILE * GRID_TILE


class _WebPOptions(TypedDict):
    lossless: bool
    quality: int
    method: int


def _trial_lossy(quality: int) -> _WebPOptions:
    return {"lossless": False, "quality": quality, "method": 2}


def _lossless(pixels: int) -> _WebPOptions:
    quality = 75 if pixels <= LOSSLESS_FULL_EFFORT_PIXELS else 0
    return {"lossless": True, "quality": quality, "method": 1}


def _lossless_strong() -> _WebPOptions:
    """Slower lossless setting; libwebp does not guarantee it is smaller.

    On real images it was up to 3.8% larger than method 1, and on a full-frame alpha
    gradient 2.4 times larger, so callers must compare against method 1.
    """
    return {"lossless": True, "quality": 75, "method": 4}


def _lossy(quality: int, pixels: int) -> _WebPOptions:
    method = 4 if pixels <= LOSSY_STRONG_PIXELS else 2
    return {"lossless": False, "quality": quality, "method": method}


def _expand(image: Image.Image, mode: str) -> Image.Image:
    """Convert to RGB/RGBA; Pillow cannot convert premultiplied ``La`` directly."""
    if image.mode == "La":
        with closing(image.convert("LA")) as straight:
            return straight.convert(mode)
    return image.convert(mode)


def normalize(image: Image.Image) -> Image.Image:
    """Preserve palette/color-key transparency, without needless full copies."""
    if image.mode in {"L", "LA", "RGB", "RGBA"} and "transparency" not in image.info:
        return image
    return _expand(image, "RGBA" if image.has_transparency_data else "RGB")


def _validate(image: Image.Image) -> None:
    width, height = image.size
    if (
        width <= 0
        or height <= 0
        or width * height > MAX_PIXELS
        or max(width, height) > MAX_EDGE
    ):
        raise ValueError("圖片最多 1,600 萬像素")


def _webp_ready(image: Image.Image) -> Image.Image:
    if image.mode in {"RGB", "RGBA"} and "transparency" not in image.info:
        return image
    return _expand(image, "RGBA" if image.has_transparency_data else "RGB")


def _opaque(image: Image.Image) -> bool:
    if image.mode == "RGB":
        return True
    with closing(image.getchannel("A")) as alpha:
        return bool(alpha.getextrema()[0] == 255)


def _same_band(red: Image.Image, image: Image.Image, index: int) -> bool:
    # Pillow's ``with image`` does not close it; closing() releases the pixels now.
    with closing(image.getchannel(index)) as other:
        with closing(ImageChops.difference(red, other)) as delta:
            return delta.getbbox() is None


def _probably_gray(image: Image.Image) -> bool:
    """Cheap reject: a coarse nearest-neighbour probe of the three color bands."""
    step = 16
    size = (max(1, image.width // step), max(1, image.height // step))
    with closing(image.resize(size, Image.Resampling.NEAREST)) as probe:
        with closing(probe.getchannel(0)) as red:
            return _same_band(red, probe, 1) and _same_band(red, probe, 2)


def _png_reduced(image: Image.Image) -> Image.Image:
    """Drop channels that cannot change any pixel before the PNG encoder runs.

    Fully opaque alpha and equal red/green/blue bands cost PNG filter and DEFLATE
    work for nothing. The result is pixel-identical when decoded back to RGBA, and
    the caller owns it unless it is the argument itself. Bands are handled one at
    a time so the peak stays near the size of the image itself.
    """
    if image.mode not in {"RGB", "RGBA"}:
        return image
    alpha = red = None
    try:
        if image.mode == "RGBA":
            alpha = image.getchannel("A")
            if alpha.getextrema()[0] == 255:
                alpha.close()
                alpha = None
        if _probably_gray(image):
            red = image.getchannel(0)
            if _same_band(red, image, 1) and _same_band(red, image, 2):
                if alpha is None:
                    gray, red = red, None
                    return gray
                return Image.merge("LA", (red, alpha))
        if image.mode == "RGBA" and alpha is None:
            return image.convert("RGB")
        return image
    finally:
        if red is not None:
            red.close()
        if alpha is not None:
            alpha.close()


def _webp(
    image: Image.Image,
    target: str | Path | IO[bytes],
    lossless: bool,
    quality: int,
    method: int,
) -> None:
    # Every option is explicit so state from an earlier save can never leak in.
    image.save(
        target,
        "WEBP",
        lossless=lossless,
        exact=lossless,
        quality=quality,
        method=method,
        alpha_quality=100,
    )


def _webp_bytes(
    image: Image.Image, *, lossless: bool, quality: int, method: int
) -> bytes:
    with io.BytesIO() as buffer:
        _webp(image, buffer, lossless, quality, method)
        return buffer.getvalue()


def _grid_sample(image: Image.Image) -> Image.Image:
    """Return a mosaic of evenly spread tiles, or the image itself if small."""
    width, height = image.size
    if width * height <= WHOLE_PIXELS:
        return image
    tile_width, tile_height = min(GRID_TILE, width), min(GRID_TILE, height)
    columns = min(GRID_COLS, (width + tile_width - 1) // tile_width)
    rows = min(GRID_ROWS, (height + tile_height - 1) // tile_height)
    sample = Image.new(image.mode, (columns * tile_width, rows * tile_height))
    try:
        for row in range(rows):
            top = row * (height - tile_height) // max(1, rows - 1)
            for col in range(columns):
                left = col * (width - tile_width) // max(1, columns - 1)
                box = (left, top, left + tile_width, top + tile_height)
                with closing(image.crop(box)) as piece:
                    sample.paste(piece, (col * tile_width, row * tile_height))
    except BaseException:
        sample.close()
        raise
    return sample


def _trial(image: Image.Image, quality: int) -> tuple[bool, bytes, bytes, bool]:
    """Encode the grid sample both ways at the fixed trial effort.

    Returns (whole, lossless, lossy, exact) where exact is the sampled verdict.
    """
    sample = _grid_sample(image)
    try:
        whole = sample is image
        pixels = sample.width * sample.height
        lossless = _webp_bytes(sample, **_lossless(0))
        lossy = _webp_bytes(sample, **_trial_lossy(quality))
    finally:
        if sample is not image:
            sample.close()
    dense = (not whole or pixels >= DENSITY_MIN_PIXELS) and len(
        lossless
    ) > LOSSLESS_MAX_BYTES_PER_PIXEL * pixels
    exact = not dense and len(lossless) <= LOSSLESS_BUDGET * len(lossy)
    return whole, lossless, lossy, exact


def _can_trade_fidelity(
    image: Image.Image, size: int, source_bytes: int | None
) -> bool:
    """Opaque images whose exact pixels barely shrink may try lossy once."""
    return (
        source_bytes is not None
        and source_bytes > 1024
        and size >= source_bytes * EXACT_KEEP_RATIO
        and _opaque(image)
    )


def encode_png(image: Image.Image, destination: str | Path | IO[bytes]) -> None:
    """Write a PNG without metadata, filtered per row by Pillow.

    Channels are 8 bits; indexed images may use a smaller index depth.
    """
    if image.mode not in {"L", "LA", "RGB", "RGBA", "P"}:
        raise ValueError(
            "NovaGrid PNG requires 8-bit L, LA, RGB, RGBA or indexed pixels"
        )
    _validate(image)
    image.save(destination, "PNG", compress_level=6, optimize=False, icc_profile=None)


def _compress_sampled(
    image: Image.Image, destination: Path, quality: int, source_bytes: int | None
) -> tuple[str, str]:
    """Choose a sampled codec, with at most one full-size lossy fallback."""
    whole, trial, _, exact = _trial(image, quality)
    pixels = image.width * image.height
    if whole:
        if not exact:
            _webp(image, destination, **_lossy(quality, pixels))
            return ".webp", "webp-lossy"
        # The trial already encoded the whole image at the baseline setting, so
        # the stronger one is free to try and can never make the file larger.
        data, name = _webp_bytes(image, **_lossless_strong()), "webp-lossless"
        if len(trial) <= len(data):
            data = trial
        if _can_trade_fidelity(image, len(data), source_bytes):
            lossy = _webp_bytes(image, **_lossy(quality, pixels))
            if len(lossy) < len(data):
                data, name = lossy, "webp-lossy-fallback"
        destination.write_bytes(data)
        return ".webp", name
    if not exact:
        _webp(image, destination, **_lossy(quality, pixels))
        return ".webp", "webp-lossy"
    if pixels > LOSSLESS_MAX_PIXELS:
        reduced = _png_reduced(image)
        try:
            encode_png(reduced, destination)
        finally:
            if reduced is not image:
                reduced.close()
        suffix, name = ".png", "png-large"
    else:
        _webp(image, destination, **_lossless(pixels))
        suffix, name = ".webp", "webp-lossless"
    size = destination.stat().st_size
    if _can_trade_fidelity(image, size, source_bytes):
        # A disk-backed retry avoids an extra full-size BytesIO payload copy.
        with tempfile.TemporaryFile() as retry:
            _webp(image, cast(IO[bytes], retry), **_lossy(quality, pixels))
            if retry.tell() < size:
                retry.seek(0)
                with destination.open("wb") as output:
                    shutil.copyfileobj(retry, output, length=64 * 1024)
                return ".webp", "webp-lossy-fallback"
    return suffix, name


@contextmanager
def _own_encoder_options(image: Image.Image) -> Iterator[None]:
    """Hide ``image.encoderinfo``; Pillow lets it override the options we pass."""
    stale = vars(image).pop("encoderinfo", None)
    try:
        yield
    finally:
        if stale is not None:
            image.encoderinfo = stale


def compress(
    image: Image.Image,
    destination: str | Path,
    quality: int = 78,
    jpeg_source: bool = False,
    source_bytes: int | None = None,
) -> tuple[str, str]:
    """Compress 8-bit pixels while preserving the caller's pixels and ownership.

    Once validation passes, a failure removes any partly written destination, so a
    caller never finds a truncated file left behind by an encoder or disk error.
    """
    if type(quality) is not int or not 40 <= quality <= 95:
        raise ValueError("品質範圍為 40 至 95")
    _validate(image)
    if image.mode in {"I", "F"} or image.mode.startswith("I;16"):
        raise ValueError("圖片壓縮僅支援 8 位元色彩，避免高精度像素遺失")
    try:
        with _own_encoder_options(image):
            if jpeg_source:
                # An empty comment stops Pillow copying ``info["comment"]`` through.
                image.save(
                    destination,
                    "JPEG",
                    quality=quality,
                    optimize=True,
                    progressive=False,
                    comment=b"",
                )
                return ".jpg", "jpeg-optimized"
            prepared = _webp_ready(image)
            try:
                return _compress_sampled(
                    prepared, Path(destination), quality, source_bytes
                )
            finally:
                if prepared is not image:
                    prepared.close()
    except BaseException:
        with suppress(OSError):
            Path(destination).unlink(missing_ok=True)
        raise
