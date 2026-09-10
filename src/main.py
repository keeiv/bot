from typing import Any
import os
import signal
import sys

from dotenv import load_dotenv
import psutil  # type: ignore[import-untyped]  # upstream package has no typing metadata

from .bot import Bot
from .utils.api_optimizer import init_api_optimizer
from .utils.config_manager import ensure_data_dir
# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")


def signal_handler(signum: Any, frame: Any) -> None:
    """處理信號終止"""
    print(f"[Info] 收到信號 {signum}，正在優雅關閉...")
    sys.exit(0)


def main() -> None:
    """機器人主進入點"""
    if not TOKEN:
        print("錯誤：未設置 DISCORD_TOKEN 環境變數")
        sys.exit(1)

    # 設置信號處理器用於優雅關閉
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 檢查機器人實例是否已在運行
    lock_file = "bot.lock"
    if os.path.exists(lock_file):
        print("[警告] 檢測到鎖定文件，機器人實例可能已在運行")
        try:
            with open(lock_file, "r", encoding="utf-8") as f:
                old_pid = f.read().strip()
            print(f"[警告] 舊實例 PID: {old_pid}")
            # 檢查進程是否仍在運行
            try:
                if psutil.pid_exists(int(old_pid)):
                    print("[錯誤] 機器人已在運行，請先停止舊實例")
                    sys.exit(1)
            except OSError:
                print("[資訊] 舊實例已停止，繼續啟動")
        except Exception as e:
            print(f"[警告] 鎖定文件檢查失敗: {e}")

    # 建立鎖定文件
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))

    # 初始化數據目錄
    ensure_data_dir()

    # 建立並運行機器人
    bot = Bot()

    # 初始化 API 優化器
    init_api_optimizer(bot)

    try:
        print("[資訊] 啟動機器人")
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("[資訊] 用戶請求機器人關閉")
    except Exception as e:
        print(f"[錯誤] 機器人啟動失敗: {e}")
        raise
    finally:
        # 清理鎖定文件
        if os.path.exists(lock_file):
            os.remove(lock_file)
        print("[Info] Bot shutdown complete")


if __name__ == "__main__":
    main()
