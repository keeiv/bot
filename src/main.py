import os
import signal
import sys
from typing import Any

from dotenv import load_dotenv
import psutil  # type: ignore[import-untyped]  # upstream package has no typing metadata

from .bot import Bot
from .utils.api_optimizer import init_api_optimizer
from .utils.config_manager import ensure_data_dir
from .utils.mysql_runtime import prepare_storage
from .utils.runtime_logging import runtime_logging

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")


def signal_handler(signum: Any, frame: Any) -> None:
    """Handle a termination signal."""
    print(f"[Info] 收到信號 {signum}，正在優雅關閉...")
    sys.exit(0)


def main() -> None:
    """The bot's entry point."""
    if not TOKEN:
        print("錯誤：未設置 DISCORD_TOKEN 環境變數")
        sys.exit(1)

    # Install signal handlers for a clean shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Check whether an instance of the bot is already running
    lock_file = "bot.lock"
    if os.path.exists(lock_file):
        print("[警告] 檢測到鎖定文件，機器人實例可能已在運行")
        try:
            with open(lock_file, "r", encoding="utf-8") as f:
                old_pid = f.read().strip()
            print(f"[警告] 舊實例 PID: {old_pid}")
            # Check whether that process is still running
            try:
                if psutil.pid_exists(int(old_pid)):
                    print("[錯誤] 已有機器人實例運行，取消啟動")
                    sys.exit(1)
            except OSError:
                print("[資訊] 舊實例已停止，繼續啟動")
        except Exception as e:
            print(f"[警告] 鎖定文件檢查失敗: {e}")

    # Create the lock file
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))

    try:
        # Include all initialization in cleanup, even when MySQL is unavailable.
        ensure_data_dir()
        prepare_storage()
        bot = Bot()
        init_api_optimizer(bot)
        print("[資訊] 啟動機器人")
        with runtime_logging():
            bot.run(TOKEN, log_handler=None)
    except KeyboardInterrupt:
        print("[資訊] 用戶請求機器人關閉")
    except Exception as e:
        print(f"[錯誤] 機器人啟動失敗: {e}")
        raise
    finally:
        # Remove the lock file
        if os.path.exists(lock_file):
            os.remove(lock_file)
        print("[Info] Bot shutdown complete")


if __name__ == "__main__":
    main()
