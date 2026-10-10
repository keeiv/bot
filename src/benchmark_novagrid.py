"""Reproducible local comparison; no bot, database or network access.

Run: python -m src.benchmark_novagrid --output <report.json> --runs 3
Each measurement runs in a fresh subprocess. Timing excludes interpreter startup
and includes decoding, resizing, encoding and the unchanged-file size check.
"""

import argparse
import json
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import time

from PIL import __version__ as pillow_version
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFilter
from PIL import ImageFont
from PIL import ImageOps
import psutil

from src.services import novagrid
from src.services.tool_worker import convert


def legacy(source, destination):
    """The compression path immediately preceding NovaGrid, for comparison."""
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        image.thumbnail((4096, 4096), Image.Resampling.LANCZOS)
        jpeg = opened.format == "JPEG"
        if jpeg:
            background = Image.new("RGB", image.size, "white")
            rgba = image.convert("RGBA")
            background.paste(rgba, mask=rgba.getchannel("A"))
            image = background
        else:
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        image.info.clear()
        image.save(destination, "JPEG" if jpeg else "WEBP", quality=78)
    if destination.stat().st_size >= source.stat().st_size:
        destination.write_bytes(source.read_bytes())
        return source.suffix, False
    return ".jpg" if jpeg else ".webp", True


def screenshot(size):
    """Gradient, soft shadows and anti-aliased text: many colors, mostly flat."""
    image = Image.linear_gradient("L").resize(size).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(16)
    draw.rectangle((0, 0, size[0], 48), fill=(32, 36, 44))
    for index in range(30):
        x, y = 40 + index % 3 * 600, 90 + index // 3 * 95
        shadow = Image.new("RGBA", (560, 80))
        ImageDraw.Draw(shadow).rounded_rectangle(
            (8, 8, 552, 72), 10, fill=(0, 0, 0, 120)
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(6))
        image.paste(shadow, (x - 8, y - 8), shadow)
        draw.rounded_rectangle((x, y, x + 540, y + 64), 10, fill=(250, 251, 253))
        draw.text(
            (x + 16, y + 10),
            f"Task {index:02d}: compile service and publish artifacts",
            fill=(20, 28, 40),
            font=font,
        )
    return image


def corpus(root):
    """Deterministic graphics, alpha, noise and interpolated texture fixtures."""
    size = (1920, 1080)
    screenshot(size).save(root / "screenshot-png.png")
    ui = Image.new("RGB", size, "#0b1019")
    draw = ImageDraw.Draw(ui)
    for index in range(8):
        y = 35 + index * 127
        draw.rounded_rectangle((35, y, 1885, y + 100), 12, fill="#152438")
        draw.ellipse((65, y + 30, 103, y + 68), fill="#67e8f9")
        draw.text(
            (130, y + 36),
            f"NovaGrid / service {index:02d} / online 99.86%",
            fill="white",
        )
        draw.rectangle((1060, y + 40, 1815 - index * 70, y + 60), fill="#38bdf8")
    ui.save(root / "ui-png.png")
    ui.save(root / "ui-bmp.bmp")
    alpha = ui.convert("RGBA")
    alpha.putalpha(Image.linear_gradient("L").resize(size))
    alpha.save(root / "alpha-png.png")
    noise = Image.frombytes(
        "RGB", size, random.Random(42).randbytes(size[0] * size[1] * 3)
    )
    noise.save(root / "noise-png.png")
    small = Image.frombytes("RGB", (160, 90), random.Random(7).randbytes(160 * 90 * 3))
    texture = small.resize(size, Image.Resampling.BICUBIC)
    texture.save(root / "texture-png.png")
    texture.save(root / "texture-jpeg.jpg", quality=95)
    gradient = Image.linear_gradient("L").resize(size).convert("RGB")
    gradient.save(root / "gradient-png.png")
    return sorted(root.glob("*.*"))


def measure_worker(mode, source, destination):
    began, cpu = time.perf_counter(), time.process_time()
    if mode == "legacy":
        suffix, changed = legacy(source, destination)
    elif mode == "nova":
        suffix, changed = convert(source, destination, "compress")
    else:
        with Image.open(source) as image:
            image.load()
            if mode == "nova-lossless":
                suffix, strategy = novagrid.compress(image, destination)
                assert strategy == "webp-lossless", strategy
            else:
                image.save(destination, "PNG", compress_level=6)
                suffix = ".png"
        changed = True
    wall, cpu = time.perf_counter() - began, time.process_time() - cpu
    memory = psutil.Process().memory_info()
    print(
        json.dumps(
            {
                "wall": wall,
                "cpu": cpu,
                "peakBytes": getattr(memory, "peak_wset", memory.rss),
                "bytes": destination.stat().st_size,
                "suffix": suffix,
                "changed": changed,
            }
        )
    )


def measure(mode, source, root):
    output = root / "result.bin"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "src.benchmark_novagrid",
            "--worker",
            mode,
            "--source",
            str(source),
            "--destination",
            str(output),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    )
    tracked = psutil.Process(process.pid)
    peak = 0
    while process.poll() is None:
        try:
            peak = max(peak, tracked.memory_info().rss)
        except psutil.NoSuchProcess:
            break
        time.sleep(0.005)
    stdout, stderr = process.communicate()
    if process.returncode:
        raise RuntimeError(stderr.decode("utf-8", errors="replace"))
    result = json.loads(stdout)
    result["peakBytes"] = max(peak, result["peakBytes"])
    with Image.open(output) as decoded:
        decoded.load()
        assert decoded.size == (1920, 1080)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument(
        "--worker", choices=("legacy", "nova", "nova-lossless", "png-pillow")
    )
    parser.add_argument("--source", type=Path)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    if args.worker:
        measure_worker(args.worker, args.source, args.destination)
        return
    if not args.output or not 1 <= args.runs <= 7:
        parser.error("--output is required; --runs must be 1..7")
    rows = []
    with tempfile.TemporaryDirectory(prefix="novagrid-benchmark-") as directory:
        root = Path(directory)
        for source in corpus(root):
            row = {"case": source.stem, "inputBytes": source.stat().st_size}
            for mode in ("legacy", "nova"):
                samples = [measure(mode, source, root) for _ in range(args.runs)]
                row[mode] = {
                    key: statistics.median(s[key] for s in samples)
                    for key in ("wall", "cpu", "peakBytes", "bytes")
                }
                row[mode].update(
                    suffix=samples[-1]["suffix"], changed=samples[-1]["changed"]
                )
            rows.append(row)
        # A same-pixel lossless comparison prevents lossy/lossless conflation.
        for name in ("ui-png", "screenshot-png"):
            source = root / f"{name}.png"
            row = {"case": f"lossless-{name}", "inputBytes": source.stat().st_size}
            for mode in ("png-pillow", "nova-lossless"):
                samples = [measure(mode, source, root) for _ in range(args.runs)]
                row[mode] = {
                    key: statistics.median(s[key] for s in samples)
                    for key in ("wall", "cpu", "peakBytes", "bytes")
                }
            rows.append(row)
    report = {
        "engine": novagrid.VERSION,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "pillow": pillow_version,
        "runs": args.runs,
        "size": [1920, 1080],
        "method": "Fresh processes, sequential runs, medians; timing includes decode but excludes interpreter startup. Synthetic fixtures only; memory is full-process peak RSS/working set. Legacy and Nova may select different codecs; same quality number does not imply equal fidelity.",
        "results": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
