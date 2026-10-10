"""Small, database-independent contract for local and LAN file workers."""

import asyncio
import hashlib
import math
from pathlib import Path
import re

FORMATS = ("compress", "png", "jpg", "webp", "pdf", "csv", "tsv", "json")
MAX_TOTAL_BYTES = 64 * 1024 * 1024
REMOTE_SECONDS = 120
CHUNK_BYTES = 64 * 1024


def safe_name(name):
    return (
        re.sub(r"[^\w.() -]", "_", str(name).replace("\\", "/").split("/")[-1])[:100]
        or "file"
    )


def engine_digest():
    """Compare source contents, including changes within the same engine version."""
    digest = hashlib.sha256()
    for name in ("novagrid.py", "tool_worker.py"):
        digest.update(name.encode())
        digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


async def disk(function, *args, **kwargs):
    """Finish small disk operations before closing their streams on cancellation."""
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            break
    if cancelled:
        if not task.cancelled():
            task.exception()
        raise asyncio.CancelledError
    return task.result()


def validate_manifest(data):
    if not isinstance(data, dict) or set(data) != {
        "jobId",
        "files",
        "operation",
        "quality",
        "maxEdge",
        "timeout",
        "engineDigest",
    }:
        raise ValueError("處理請求格式無效")
    if not isinstance(data["jobId"], str) or not re.fullmatch(
        r"[a-zA-Z0-9_-]{1,64}", data["jobId"]
    ):
        raise ValueError("工作識別碼無效")
    if data["operation"] not in FORMATS:
        raise ValueError("輸出格式無效")
    for key, low, high in (
        ("quality", 40, 95),
        ("maxEdge", 256, 8192),
        ("timeout", 1, 60),
    ):
        if type(data[key]) is not int or not low <= data[key] <= high:
            raise ValueError("處理上限無效")
    files = data["files"]
    if not isinstance(files, list) or not 1 <= len(files) <= 16:
        raise ValueError("批次上限無效")
    total = 0
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"name", "bytes"}:
            raise ValueError("檔案資訊無效")
        if (
            not isinstance(entry["name"], str)
            or not entry["name"]
            or entry["name"] != safe_name(entry["name"])
            or type(entry["bytes"]) is not int
            or entry["bytes"] <= 0
        ):
            raise ValueError("檔名或檔案大小無效")
        total += entry["bytes"]
    if total > MAX_TOTAL_BYTES:
        raise ValueError("批次超過 64 MiB 上限")
    if not isinstance(data["engineDigest"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", data["engineDigest"]
    ):
        raise ValueError("引擎識別碼無效")
    return data


def validate_result(data, timeout):
    if not isinstance(data, dict) or set(data) != {
        "name",
        "bytes",
        "seconds",
        "changed",
        "engine",
        "sha256",
        "engineDigest",
    }:
        raise ValueError("處理結果資訊無效")
    engine = data["engine"]
    invalid_engine = engine is not None and (
        not isinstance(engine, str)
        or not re.fullmatch(r"NovaGrid/[A-Za-z0-9._-]{1,32}", engine)
    )
    if (
        not isinstance(data["name"], str)
        or not data["name"]
        or data["name"] != safe_name(data["name"])
        or type(data["changed"]) is not bool
        or type(data["bytes"]) is not int
        or not 0 < data["bytes"] <= MAX_TOTAL_BYTES
        or type(data["seconds"]) not in (int, float)
        or not math.isfinite(data["seconds"])
        or not 0 <= data["seconds"] <= timeout
        or invalid_engine
        or not isinstance(data["sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", data["sha256"])
        or data["engineDigest"] != engine_digest()
    ):
        raise ValueError("處理結果校驗失敗")
    return data
