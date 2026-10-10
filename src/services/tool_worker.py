"""Bounded file conversion worker. Invoked in a disposable subprocess."""

from contextlib import ExitStack
import csv
import io
import json
from pathlib import Path
import shutil
import sys
import time
import warnings
import zipfile

from PIL import Image
from PIL import ImageOps

if __package__:
    from . import novagrid
else:
    # Also support the isolated worker's absolute-file subprocess entry point.
    import novagrid

Image.MAX_IMAGE_PIXELS = 16_000_000
warnings.simplefilter("error", Image.DecompressionBombWarning)
IMAGE_INPUTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}


def convert(source, destination, operation, quality=78, max_edge=4096):
    """Return output suffix and whether a billable transformation occurred."""
    if source.suffix.lower() in IMAGE_INPUTS:
        source_bytes = source.stat().st_size
        with Image.open(source) as opened, ExitStack() as images:
            if getattr(opened, "n_frames", 1) != 1:
                raise ValueError("目前僅支援靜態圖片")
            if operation not in {"compress", "png", "jpg", "webp", "pdf"}:
                raise ValueError("圖片不支援此輸出格式")
            input_format = opened.format
            if operation == "compress" and (
                opened.mode in {"I", "F"} or opened.mode.startswith("I;16")
            ):
                raise ValueError("圖片壓縮僅支援 8 位元色彩，避免高精度像素遺失")
            ImageOps.exif_transpose(opened, in_place=True)
            image = opened
            # Interpolate transparency as alpha rather than a color-key value.
            # Palette pixels also need a continuous mode for Lanczos resizing.
            if image.mode == "P" or "transparency" in image.info:
                image = novagrid.normalize(image)
                if image is not opened:
                    images.callback(image.close)
            image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
            fmt = (
                operation
                if operation != "compress"
                else ("jpg" if input_format == "JPEG" else "png")
            )
            before_conversion = image
            if fmt in {"jpg", "pdf"}:
                if "A" in image.getbands() or "transparency" in image.info:
                    background = Image.new("RGB", image.size, "white")
                    with image.convert("RGBA") as rgba:
                        with rgba.getchannel("A") as alpha:
                            background.paste(rgba, mask=alpha)
                    image = background
                elif image.mode != "RGB":
                    image = image.convert("RGB")
            else:
                image = novagrid.normalize(image)
            if image is not before_conversion:
                images.callback(image.close)
            # Do not carry embedded profiles, location or comments into outputs.
            image.info.clear()
            if operation == "compress":
                suffix, _ = novagrid.compress(
                    image,
                    destination,
                    quality,
                    input_format == "JPEG",
                    source_bytes,
                )
                fmt = suffix[1:]
            else:
                options = {"quality": quality} if fmt in {"jpg", "webp"} else {}
                image.save(
                    destination, format={"jpg": "JPEG"}.get(fmt, fmt.upper()), **options
                )
        if operation == "compress" and destination.stat().st_size >= source_bytes:
            shutil.copyfile(source, destination)
            return source.suffix.lower(), False
        return "." + fmt, True
    if source.suffix.lower() not in {".csv", ".tsv", ".json"} or operation not in {
        "csv",
        "tsv",
        "json",
    }:
        raise ValueError("支援靜態圖片及 CSV／TSV／JSON 表格轉換")
    if source.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("表格轉換上限為 8 MiB")
    text = source.read_text(encoding="utf-8-sig")
    fields = []
    if source.suffix.lower() == ".json":
        records = json.loads(text)
        if not isinstance(records, list) or any(
            not isinstance(r, dict) for r in records
        ):
            raise ValueError("JSON 必須為物件陣列")
    else:
        reader = csv.DictReader(
            io.StringIO(text),
            delimiter="\t" if source.suffix.lower() == ".tsv" else ",",
        )
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(
            reader.fieldnames
        ):
            raise ValueError("表格需要不重複的欄位名稱")
        fields = reader.fieldnames
        if len(fields) > 256:
            raise ValueError("表格上限為 256 欄")
        records = []
        for record in reader:
            if None in record or None in record.values():
                raise ValueError("表格欄位數不一致")
            records.append(record)
            if len(records) > 50000:
                raise ValueError("表格上限為 50,000 列")
    if len(records) > 50000:
        raise ValueError("表格上限為 50,000 列")
    if not fields:
        fields = list(dict.fromkeys(key for row in records for key in row))
    if len(fields) > 256:
        raise ValueError("表格上限為 256 欄")
    if operation == "json":
        destination.write_text(
            json.dumps(records, ensure_ascii=False, indent=2, allow_nan=False),
            encoding="utf-8",
        )
    else:
        if any(isinstance(v, (dict, list)) for r in records for v in r.values()):
            raise ValueError("巢狀 JSON 無法轉換為平面表格")
        with destination.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(
                stream, fields, delimiter="\t" if operation == "tsv" else ","
            )
            writer.writeheader()
            writer.writerows(records)
    return "." + operation, True


def run(root):
    manifest = json.loads((root / "request.json").read_text(encoding="utf-8"))
    began = time.monotonic()
    changed = False
    outputs = []
    for index, entry in enumerate(manifest["files"]):
        source = root / entry["stored"]
        destination = root / f"output-{index}"
        suffix, modified = convert(
            source,
            destination,
            manifest["operation"],
            manifest["quality"],
            manifest["maxEdge"],
        )
        changed = changed or modified
        name = f"{index + 1:02d}-{Path(entry['name']).stem[:70]}{suffix}"
        outputs.append((destination, name))
        if sum(path.stat().st_size for path, _ in outputs) > 64 * 1024 * 1024:
            raise ValueError("輸出超過 64 MiB 上限")
    if len(outputs) == 1:
        path, name = outputs[0]
        path.rename(root / "result.bin")
    else:
        name = "converted-files.zip"
        with zipfile.ZipFile(
            root / "result.bin",
            "w",
            compression=(
                zipfile.ZIP_STORED
                if manifest["operation"] in {"compress", "png", "jpg", "webp", "pdf"}
                else zipfile.ZIP_DEFLATED
            ),
        ) as archive:
            for path, filename in outputs:
                archive.write(path, filename)
                path.unlink()
    if (root / "result.bin").stat().st_size > 64 * 1024 * 1024:
        raise ValueError("輸出超過 64 MiB 上限")
    (root / "result.json").write_text(
        json.dumps(
            {
                "name": name,
                "changed": changed,
                "seconds": time.monotonic() - began,
                "bytes": (root / "result.bin").stat().st_size,
                "engine": (
                    novagrid.VERSION if manifest["operation"] == "compress" else None
                ),
            }
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    directory = Path(sys.argv[1])
    try:
        run(directory)
    except Exception:
        # File contents and decoder details must not become API error messages.
        (directory / "error.txt").write_text(
            "轉換失敗：格式、內容或處理上限不符合要求", encoding="utf-8"
        )
        sys.exit(1)
