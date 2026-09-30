"""Start the configured local Oracle instance before checking migration."""

import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from .document_store import require_migration
from .document_store import StorageError
from .document_store import using_mysql


def _listening(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def prepare_storage() -> None:
    """Start a configured local MySQL instance and validate storage readiness."""
    if not using_mysql():
        return
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = int(os.getenv("MYSQL_PORT", "3307"))
    launcher = Path(os.getenv("LOCALAPPDATA", "")) / "NewBotMySQL/start-mysql.ps1"
    if (
        sys.platform == "win32"
        and host in {"127.0.0.1", "localhost"}
        and port == 3307
        and launcher.is_file()
        and not _listening(host, port)
    ):
        print("[資訊] MySQL 未就緒，正在啟動本機資料庫程序")
        try:
            subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(launcher),
                ],
                check=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise StorageError("本機 MySQL 啟動失敗；詳情見資料庫啟動日誌") from exc
        deadline = time.monotonic() + 30
        while not _listening(host, port):
            if time.monotonic() >= deadline:
                raise StorageError("MySQL 啟動逾時；日誌：NewBotMySQL/mysql-error.log")
            time.sleep(0.5)
    require_migration()
