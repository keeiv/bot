"""Deployment script for the Discord bot."""

import os
import subprocess
import sys

def run_command(command, description):
    """Run a command and handle errors."""
    print(f"\n{description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✓ {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def deploy():
    """Deploy the bot."""
    print("Starting deployment...")
    
    # Install dependencies
    if not run_command("pip install -r requirements.txt", "Installing dependencies"):
        return False
    
    # Run migration
    if not run_command("python scripts/migrate.py", "Running migration"):
        return False
    
    # Check environment variables
    required_vars = ["DISCORD_TOKEN"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"✗ Missing environment variables: {', '.join(missing_vars)}")
        return False
    
    print("✓ Environment variables check passed")
    
    # Start bot
    print("\nStarting bot...")
    os.system("python src/main.py")

if __name__ == "__main__":
    deploy()
