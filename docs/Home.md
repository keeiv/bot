# Discord Bot - Feature-Rich Multi-Purpose Bot

A comprehensive Discord bot with advanced moderation, entertainment features, and external service integrations. Built with Python 3.8+ and discord.py 2.3.2.

## Table of Contents

- [Project Overview](#project-overview)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Documentation](#documentation)
- [Contributing](#contributing)

## Project Overview

This Discord bot provides a complete server management solution with:

- **Modular Architecture**: Clean separation of concerns with cogs-based structure
- **Comprehensive Features**: Moderation, games, achievements, osu! integration, GitHub monitoring
- **Security**: Built-in anti-spam, blacklist system, report system
- **Type Safety**: Type hints throughout the codebase

### Technical Stack

- **Language**: Python 3.8+
- **Framework**: discord.py 2.3.2
- **Testing**: pytest with asyncio support
- **Code Quality**: Black, flake8, isort
- **CI/CD**: GitHub Actions

## Key Features

### Core Administration
- **Message Management**: Bulk deletion, edit/delete logging
- **User Moderation**: Kick, ban, mute (timeout), warn commands
- **Audit Logging**: Member join/leave, voice, role, nickname, channel events
- **Blacklist System**: Global blacklist with appeal system (Modal + View)
- **Bot Appearance**: Per-guild avatar/banner with developer approval

### Security & Protection
- **7-Layer Anti-Spam**: Flood, duplicate, mention, link, emoji, newline, raid detection
- **Report System**: Right-click context menu reporting with mute/ban/warn modals
- **Auto Escalation**: Progressive punishment for repeat offenders
- **Raid Detection**: Mass-join detection with auto-lockdown

### User Engagement
- **Achievement System**: Chat, game, social, and special achievements
- **Giveaway System**: Button-based participation, auto-expiry
- **Welcome Messages**: Customizable messages with auto-role
- **Role/Emoji Management**: Assign/remove roles, upload emojis

### Entertainment
- **Deep Sea Oxygen**: 2-player cooperative game with shared oxygen
- **Russian Roulette**: 2-player competitive game with items and chips

### External Integrations
- **osu! Integration**: Player stats, bind, best plays, recent plays, scores
- **GitHub Monitoring**: Repository watch + keeiv/bot tracking
- **GitHub Diagnostics**: API status and rate limit checks

### System Monitoring
- **Performance Dashboard**: Cache stats, network status, API optimization
- **System Maintenance**: Cleanup, cache management
- **Network Diagnostics**: Connectivity testing

## Quick Start

### Prerequisites
- Python 3.8 or higher
- Discord Bot Token

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/keeiv/bot.git
cd bot
```

2. **Set up virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your Discord bot token
```

5. **Run the bot**
```bash
python -m src.main
```

### Basic Configuration

Create a `.env` file with the following required variables:

```env
DISCORD_TOKEN=your_bot_token_here
# Optional configurations
GITHUB_TOKEN=your_github_token
OSU_API_KEY=your_osu_api_key
```

## Architecture

### Project Structure

```
bot/
├── src/
│   ├── bot.py              # Main bot class and initialization
│   ├── main.py             # Application entry point
│   ├── cogs/               # Discord command modules
│   │   ├── core/          # Core functionality (admin, logging)
│   │   ├── features/      # Feature modules (achievements, integrations)
│   │   └── games/         # Entertainment games
│   ├── utils/             # Utility functions and helpers
│   └── bot_types/         # Type definitions
├── tests/                 # Test suite
├── docs/                  # Documentation
├── scripts/               # Development and utility scripts
├── data/                  # Runtime data storage
└── .github/workflows/      # CI/CD pipeline configuration
```

### Component Overview

**Bot Core (`src/bot.py`)**
- Main bot class inheriting from discord.ext.commands.Bot
- Cog loading and management
- Event handling setup

**Cogs System (`src/cogs/`)**
- Modular command organization
- Separation by functionality
- Independent feature development

**Utilities (`src/utils/`)**
- Shared helper functions
- Configuration management
- Common operations

**Type System (`src/bot_types/`)**
- Centralized type definitions
- Data structure specifications
- Interface contracts

## Development Standards

### Code Quality Requirements

This project enforces strict development standards through automated checks:

**English-First Policy**
- All code, comments, and documentation must be in English
- Variable names use descriptive English words
- User-facing strings must be English
- Docstrings follow Google style with English descriptions

**Formatting Standards**
- 4-space indentation for Python files
- 88-character line length limit
- Consistent import organization
- Type hints for all public APIs

**Quality Assurance**
- Automated testing with >80% coverage
- Static type checking with MyPy strict mode
- Security vulnerability scanning
- Code complexity analysis

### CI/CD Pipeline

**Continuous Integration**
- Multi-version Python testing (3.8-3.11)
- Automated code quality checks
- English standards compliance verification
- Security scanning and reporting

**Pre-commit Hooks**
- Automatic code formatting
- Import sorting
- Linting and style checking
- Type validation

## Documentation

### Available Documentation

- **[Installation Guide](Installation)**: Detailed setup instructions
- **[Configuration](Configuration)**: Environment variables and settings
- **[API Reference](API-Reference)**: Complete API documentation
- **[Development](Development)**: Development setup and guidelines
- **[Deployment](Deployment)**: Production deployment options
- **[Troubleshooting](Troubleshooting)**: Common issues and solutions

### Code Documentation

All public APIs include comprehensive docstrings following Google style:

```python
async def process_command(self, ctx: commands.Context, command_name: str) -> bool:
    """Process a user command and return execution status.

    Args:
        ctx: The command context containing user information.
        command_name: The name of command to process.

    Returns:
        True if command was executed successfully, False otherwise.

    Raises:
        ValueError: If command_name is empty or invalid.
        CommandError: If command execution fails.
    """
```

## Contributing

We welcome contributions from the community! Please review our [Contributing Guide](Contributing) before submitting pull requests.

### How to Contribute

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/your-feature`
3. **Follow coding standards**: English-only, properly formatted code
4. **Add tests**: Ensure >80% coverage for new features
5. **Submit pull request**: With clear description and testing

### Development Requirements

- All contributions must pass automated CI checks
- Code must follow English-only standards
- New features require comprehensive tests
- Documentation must be updated for API changes

### Getting Help

- **GitHub Issues**: Report bugs and request features
- **GitHub Discussions**: Ask questions and share ideas
- **Wiki**: Comprehensive documentation and guides
- **Code Review**: Maintainer review and feedback

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Support

For support and questions:

- **Documentation**: Check the [wiki](https://github.com/keeiv/bot/wiki)
- **Issues**: [Report bugs](https://github.com/keeiv/bot/issues)
- **Discussions**: [Community forum](https://github.com/keeiv/bot/discussions)

---

**Thank you for using our Discord bot!** We're committed to providing a high-quality, well-documented, and secure solution for Discord server management.
