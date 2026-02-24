# Installation Guide

This guide will help you install and set up the Discord bot on your system.

## Table of Contents

- [System Requirements](#system-requirements)
- [Installation Methods](#installation-methods)
- [Environment Setup](#environment-setup)
- [Initial Configuration](#initial-configuration)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

## System Requirements

### Minimum Requirements
- **Python**: 3.8 or higher
- **Operating System**: Windows 10+, macOS 10.14+, or Linux (Ubuntu 18.04+)
- **Memory**: 512MB RAM minimum
- **Storage**: 100MB free space
- **Network**: Stable internet connection

### Recommended Requirements
- **Python**: 3.11 (latest stable)
- **Memory**: 1GB RAM or more
- **Storage**: 500MB free space

### Discord Bot Requirements
- **Discord Account**: Bot account with application created
- **Bot Token**: Valid bot token from Discord Developer Portal
- **Permissions**: Appropriate bot permissions for intended features

## Installation Methods

### Method 1: Clone from GitHub (Recommended)

1. **Clone the repository**
```bash
git clone https://github.com/finn001023-cpu/bot.git
cd bot
```

2. **Verify Python version**
```bash
python --version
# Should show Python 3.8.x or higher
```

### Method 2: Download Release

1. **Download latest release**
   - Visit [Releases page](https://github.com/finn001023-cpu/bot/releases)
   - Download the latest `.zip` file
   - Extract to your desired location

2. **Navigate to project directory**
```bash
cd bot
```

### Method 3: Using Docker (Advanced)

1. **Pull the Docker image**
```bash
docker pull ghcr.io/finn001023-cpu/bot:latest
```

2. **Run the container**
```bash
docker run -d --name discord-bot \
  -v $(pwd)/data:/app/data \
  -e DISCORD_TOKEN=your_token_here \
  ghcr.io/finn001023-cpu/bot:latest
```

## Environment Setup

### Virtual Environment (Recommended)

1. **Create virtual environment**
```bash
# On Unix/macOS
python3 -m venv .venv

# On Windows
python -m venv .venv
```

2. **Activate virtual environment**
```bash
# On Unix/macOS
source .venv/bin/activate

# On Windows
.venv\Scripts\activate
```

3. **Verify activation**
```bash
which python
# Should show path to .venv/bin/python
```

### Install Dependencies

1. **Upgrade pip**
```bash
python -m pip install --upgrade pip
```

2. **Install production dependencies**
```bash
pip install -r requirements.txt
```

3. **Install development dependencies (optional)**
```bash
pip install -r requirements-dev.txt
```

### Verify Installation

1. **Check installed packages**
```bash
pip list
# Verify key packages: discord.py, aiohttp, python-dotenv
```

2. **Test import**
```bash
python -c "import discord; print('discord.py installed successfully')"
```

## Initial Configuration

### Environment Variables

1. **Create environment file**
```bash
cp .env.example .env
```

2. **Edit configuration file**
```bash
nano .env  # or use your preferred editor
```

3. **Required variables**
```env
DISCORD_TOKEN=your_bot_token_here
```

4. **Optional variables**
```env
# GitHub Integration
GITHUB_TOKEN=your_github_token

# osu! Integration
OSU_API_KEY=your_osu_api_key

# Logging Level
LOG_LEVEL=INFO

# Data Directory
DATA_DIR=./data
```

### Directory Structure Setup

1. **Create necessary directories**
```bash
mkdir -p data/config
mkdir -p data/storage
mkdir -p data/logs/messages
```

2. **Verify permissions**
```bash
ls -la data/
# Ensure directories are writable
```

### Discord Bot Setup

1. **Create Discord Application**
   - Visit [Discord Developer Portal](https://discord.com/developers/applications)
   - Click "New Application"
   - Enter application name and description

2. **Create Bot User**
   - Go to "Bot" tab
   - Click "Add Bot"
   - Copy bot token

3. **Configure Bot Permissions**
   - Enable "Message Content Intent"
   - Enable "Server Members Intent"
   - Enable "Guilds Intent"

4. **Invite Bot to Server**
   - Go to "OAuth2" → "URL Generator"
   - Select appropriate scopes and permissions
   - Copy generated URL and invite to your server

## Verification

### Test Local Installation

1. **Run the bot**
```bash
python -m src.main
```

2. **Check console output**
```
[INFO] discord.client logging in using static token
[INFO] discord.gateway Shard ID None has connected to Gateway
YourBot#1234 has connected to Discord!
Bot is in 1 guilds
```

3. **Test basic commands**
   - Type `!help` in your Discord server
   - Verify bot responds correctly

### Verify Functionality

1. **Core Features**
```bash
# Test admin commands (if you have permissions)
!clear 5
!ping
```

2. **Feature Modules**
```bash
# Test achievements
!achievements

# Test other features based on your configuration
```

## Troubleshooting

### Common Installation Issues

**Python Version Error**
```
Error: This package requires Python 3.8 or higher
```
**Solution**: Install Python 3.8+ from [python.org](https://python.org)

**Permission Denied**
```
Error: Permission denied: '.env'
```
**Solution**: Check file permissions and ownership

**Module Not Found**
```
ModuleNotFoundError: No module named 'discord'
```
**Solution**: Activate virtual environment and reinstall dependencies

**Token Invalid**
```
Error: Improper token has been passed
```
**Solution**: Verify Discord bot token in `.env` file

### Runtime Issues

**Bot Not Responding**
- Check bot is online in Discord
- Verify bot has message permissions
- Check console for error messages

**Commands Not Working**
- Verify command prefix is correct
- Check bot has required permissions
- Ensure commands are enabled in server

**Memory Issues**
- Increase available RAM
- Check for memory leaks in custom code
- Monitor system resources

### Getting Help

If you encounter issues not covered here:

1. **Check the [Troubleshooting Guide](Troubleshooting)**
2. **Search [GitHub Issues](https://github.com/finn001023-cpu/bot/issues)**
3. **Create a new issue** with:
   - System information
   - Error messages
   - Steps to reproduce
   - Expected vs actual behavior

## Next Steps

After successful installation:

1. **Review [Configuration Guide](Configuration)** for advanced settings
2. **Explore [API Reference](API-Reference)** for customization
3. **Check [Development Guide](Development)** for contribution
4. **Monitor bot performance** and adjust settings as needed

---

**Installation complete!** Your Discord bot should now be running and ready for configuration.
