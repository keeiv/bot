"""Read-only, bounded storage health observations for the public status page."""

import asyncio
import copy
from datetime import datetime
from datetime import timezone
import os
from pathlib import Path
import time

import pymysql

from src.utils.document_store import connect_mysql
from src.utils.document_store import using_mysql
from src.utils.storage_worker import run_blocking


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def check_storage() -> dict:
    backend = "mysql" if using_mysql() else "json"
    try:
        if backend == "mysql":
            with connect_mysql() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    online = cursor.fetchone() == (1,)
        else:
            root = Path(os.getenv("STORAGE_ROOT", str(Path.cwd())))
            with os.scandir(root):
                online = True
    except (OSError, RuntimeError, pymysql.MySQLError):
        online = False
    return {"online": online, "backend": backend, "checkedAt": timestamp()}


class StorageHealth:
    """Share a short-lived observation without blocking the Discord event loop."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._snapshot = None
        self._observed_at = 0.0

    async def read(self) -> dict:
        async with self._lock:
            if self._snapshot is None or time.monotonic() - self._observed_at >= 30:
                self._snapshot = await run_blocking(check_storage)
                self._observed_at = time.monotonic()
            return copy.deepcopy(self._snapshot)
