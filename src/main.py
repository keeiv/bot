import asyncio
import os
import signal
import sys

import discord
from dotenv import load_dotenv

from .bot import Bot
from .utils.api_optimizer import connection_manager
from .utils.api_optimizer import init_api_optimizer
from .utils.api_optimizer import performance_monitor
from .utils.blacklist_manager import blacklist_manager
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
    print(f"Received signal {signum}, shutting down gracefully...")
    sys.exit(0)


async def initialize_optimizations():
    print("[Init] Initializing database manager...")
    init_database_manager()

    print("[Init] Initializing config optimizer...")
    init_config_manager()

    print("[Init] Initializing network optimizer...")
    network_config = NetworkConfig(
        max_connections=100,
        connect_timeout=10.0,
        read_timeout=30.0,
        use_http2=True,
        dns_cache_ttl=300,
    )
    init_network_optimizer(network_config)

    print("[Init] Starting database cleanup task...")
    db_manager = get_database_manager()
    await db_manager.start_cleanup_task(interval=300)

    print("[Init] All optimizations initialized successfully")


def main():
    """Main entry point for the bot."""
    if not TOKEN:
        print("Error: DISCORD_TOKEN environment variable not set")
        exit(1)

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Check if bot instance is already running
    lock_file = "bot.lock"
    if os.path.exists(lock_file):
        print("[Warning] Lock file detected, bot instance may already be running")
        try:
            with open(lock_file, "r") as f:
                old_pid = f.read().strip()
            print(f"[Warning] Old instance PID: {old_pid}")
            # Check if process is still running
            try:
                os.kill(int(old_pid), 0)  # Check if process exists
                print(
                    "[Error] Bot is already running, please stop the old instance first"
                )
                exit(1)
            except OSError:
                print("[Info] Old instance has stopped, continuing startup")
        except:
            pass

    # Create lock file
    with open(lock_file, "w") as f:
        f.write(str(os.getpid()))

    # Initialize data directory
    ensure_data_dir()

    # Create and run bot with optimizations
    bot = Bot()

    # Initialize all optimizations
    async def on_ready():
        await initialize_optimizations()
        print("[Info] Bot and optimizations ready")

    bot.add_listener(on_ready, "on_ready")

    # Initialize API optimizer
    init_api_optimizer(bot)

    try:
        print("[Info] Starting bot with comprehensive optimizations...")
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("[Info] Bot shutdown requested by user")
    except Exception as e:
        print(f"[Error] Bot startup failed: {e}")
    finally:
        # Clean up resources
        try:
            from .utils.network_optimizer import get_network_optimizer

            network_opt = get_network_optimizer()
            asyncio.create_task(network_opt.close())
        except:
            pass

        # Clean up lock file
        if os.path.exists(lock_file):
            os.remove(lock_file)
        print("[Info] Bot shutdown complete")


if __name__ == "__main__":
    main()
