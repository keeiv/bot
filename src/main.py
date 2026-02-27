import asyncio
import os
import signal
import sys

from dotenv import load_dotenv

from .bot import Bot
from .utils.api_optimizer import init_api_optimizer
from .utils.config_manager import ensure_data_dir
from .utils.config_optimizer import init_config_manager
from .utils.database_manager import get_database_manager
from .utils.database_manager import init_database_manager
from .utils.network_optimizer import init_network_optimizer
from .utils.network_optimizer import NetworkConfig

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")


def signal_handler(signum, frame):
    """處理信號終止"""
    print(f"[Info] 收到信號 {signum}，正在優雅關閉...")
    sys.exit(0)


async def initialize_optimizations():
    """初始化所有優化模組"""
    print("[Init] 初始化數據庫管理器...")
    init_database_manager()

    print("[Init] 初始化配置優化器...")
    init_config_manager()

    print("[Init] 初始化網路優化器...")
    network_config = NetworkConfig(
        max_connections=100,
        connect_timeout=10.0,
        read_timeout=30.0,
        use_http2=True,
        dns_cache_ttl=300,
    )
    init_network_optimizer(network_config)

    print("[Init] 啟動數據庫清理任務...")
    db_manager = get_database_manager()
    await db_manager.start_cleanup_task(interval=300)

    print("[Init] 所有優化模組初始化完成")


def main():
    """機器人主進入點"""
    if not TOKEN:
        print("錯誤：未設置 DISCORD_TOKEN 環境變數")
        exit(1)

    # 設置信號處理器用於優雅關閉
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 檢查機器人實例是否已在運行
    lock_file = "bot.lock"
    if os.path.exists(lock_file):
        print("[警告] 檢測到鎖定文件，機器人實例可能已在運行")
        try:
            with open(lock_file, "r") as f:
                old_pid = f.read().strip()
            print(f"[警告] 舊實例 PID: {old_pid}")
            # 檢查進程是否仍在運行
            try:
                os.kill(int(old_pid), 0)  # 檢查進程是否存在
                print("[錯誤] 機器人已在運行，請先停止舊實例")
                exit(1)
            except OSError:
                print("[信息] 舊實例已停止，繼續啟動")
        except Exception as e:
            print(f"[警告] 鎖定文件檢查失敗: {e}")

    # 建立鎖定文件
    with open(lock_file, "w") as f:
        f.write(str(os.getpid()))

    # 初始化數據目錄
    ensure_data_dir()

    # 建立並運行機器人
    bot = Bot()

    # 初始化所有優化
    async def on_ready():
        await initialize_optimizations()
        print("[信息] 機器人和優化模組已就緒")

    bot.add_listener(on_ready, "on_ready")

    # 初始化 API 優化器
    init_api_optimizer(bot)

    try:
        print("[信息] 啟動機器人，應用全面優化...")
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("[信息] 用戶請求機器人關閉")
    except Exception as e:
        print(f"[錯誤] 機器人啟動失敗: {e}")
    finally:
        # 清理資源
        try:
            from .utils.network_optimizer import get_network_optimizer

            network_opt = get_network_optimizer()
            asyncio.create_task(network_opt.close())
        except Exception:
            pass

        # 清理鎖定文件
        if os.path.exists(lock_file):
            os.remove(lock_file)
        print("[Info] Bot shutdown complete")


if __name__ == "__main__":
    main()
