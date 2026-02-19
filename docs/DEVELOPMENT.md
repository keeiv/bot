# Development Guide

## Project Structure

```
discord-bot/
├── src/                    # Main source code
│   ├── bot.py             # Core bot class
│   ├── main.py            # Entry point
│   ├── cogs/              # Bot modules
│   │   ├── core/          # Essential functionality
│   │   ├── features/      # Additional features
│   │   └── games/         # Game modules
│   ├── utils/             # Utility functions
│   └── types/             # Type definitions
├── data/                  # Runtime data
│   ├── config/            # Configuration files
│   ├── storage/           # Persistent data
│   └── logs/              # Log files
├── services/              # External service integrations
├── scripts/               # Utility scripts
├── tests/                 # Test suite
└── docs/                  # Documentation
```

## Adding New Features

### 1. Create a New Cog
```python
# src/cogs/features/new_feature.py
import discord
from discord.ext import commands

class NewFeature(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command()
    async def new_command(self, ctx):
        await ctx.send("Hello from new feature!")

async def setup(bot):
    await bot.add_cog(NewFeature(bot))
```

### 2. Register the Cog
Add to `src/bot.py` in the `load_cogs` method:
```python
cogs = [
    # ... existing cogs
    'src.cogs.features.new_feature',
]
```

### 3. Add Tests
Create test file in `tests/test_cogs/test_new_feature.py`

## Code Style

- Use type hints where possible
- Follow PEP 8 formatting
- Add docstrings to all functions and classes
- Use f-strings for string formatting
- Handle exceptions gracefully

## Environment Variables

Required variables:
- `DISCORD_TOKEN`: Bot token (required)
- `OSU_CLIENT_ID`: osu! API client ID (optional)
- `OSU_CLIENT_SECRET`: osu! API client secret (optional)
- `GITHUB_TOKEN`: GitHub personal access token (optional)

## Testing

Run tests with:
```bash
python -m pytest tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## Database Schema

### Achievement System
- User achievements stored in `data/storage/achievements.json`
- Achievement definitions in cog file

### User Links
- osu! account links in `data/storage/osu_links.json`
- Format: `{discord_id: osu_username}`

### Configuration
- Guild settings in `data/config/bot.json`
- Per-guild channel configurations
