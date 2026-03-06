"""部署腳本：安裝相依、遷移資料並啟動機器人。"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Sequence


def run_command(command: str, description: str) -> bool:
    """執行 shell 命令並回傳是否成功。"""
    print(f"\n{description}...")
    try:
        subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"{description} 完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"{description} 失敗: {e}")
        if e.stderr:
            print(f"Error output: {e.stderr}")
        return False


def deploy() -> None:
    """部署程序：依序安裝套件、執行遷移、檢查環境變數，最後啟動 bot。"""
    print("開始部署...")

    if not run_command("pip install -r requirements.txt", "安裝相依套件"):
        sys.exit(1)

    if not run_command("python scripts/migrate.py", "執行遷移腳本"):
        sys.exit(1)

    required_vars: Sequence[str] = ["DISCORD_TOKEN"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"缺少環境變數: {', '.join(missing_vars)}")
        sys.exit(1)

    print("環境變數檢查通過")

    print("\n啟動 bot...")
    os.execvp(sys.executable, [sys.executable, "src/main.py"])  # 使用 exec 取代 os.system 以替換進程


if __name__ == "__main__":
    deploy()
