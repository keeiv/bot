import os
import asyncio
import discord
from dotenv import load_dotenv
import sys

from .bot import Bot
from .utils.config_manager import ensure_data_dir
from .utils.blacklist_manager import blacklist_manager

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

def main():
    """Main entry point for the bot."""
    if not TOKEN:
        print("Error: DISCORD_TOKEN environment variable not set")
        exit(1)
    
    # Check if bot instance is already running
    lock_file = "bot.lock"
    if os.path.exists(lock_file):
        print("[Warning] Lock file detected, bot instance may already be running")
        try:
            with open(lock_file, 'r') as f:
                old_pid = f.read().strip()
            print(f"[Warning] Old instance PID: {old_pid}")
            # Check if process is still running
            try:
                os.kill(int(old_pid), 0)  # Check if process exists
                print("[Error] Bot is already running, please stop the old instance first")
                exit(1)
            except OSError:
                print("[Info] Old instance has stopped, continuing startup")
        except:
            pass
    
    # Create lock file
    with open(lock_file, 'w') as f:
        f.write(str(os.getpid()))
    
    # Initialize data directory
    ensure_data_dir()
    
    # Create and run bot
    bot = Bot()
    
    try:
        bot.run(TOKEN)
    finally:
        # Clean up lock file
        if os.path.exists(lock_file):
            os.remove(lock_file)

if __name__ == "__main__":
    main()
