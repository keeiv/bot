# Discord Bot - Feature-Rich Multi-Purpose Bot

A comprehensive Discord bot with advanced moderation, entertainment features, and external service integrations. Built with Python 3.8+ and following strict English-first coding standards.

## Table of Contents

- [Project Overview](#project-overview)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Development Standards](#development-standards)
- [Documentation](#documentation)
- [Contributing](#contributing)

## Project Overview

This Discord bot is designed to provide a complete server management solution with:

- **Professional Code Quality**: All code follows strict English-only standards with comprehensive CI/CD pipeline
- **Modular Architecture**: Clean separation of concerns with cogs-based structure
- **Comprehensive Testing**: Automated testing with coverage reporting
- **Security First**: Built-in security scanning and vulnerability detection
- **Type Safety**: Full type hints with MyPy strict mode

### Technical Stack

- **Language**: Python 3.8+
- **Framework**: discord.py 2.0+
- **Testing**: pytest with asyncio support
- **Code Quality**: Black, flake8, isort, MyPy
- **CI/CD**: GitHub Actions with multi-version testing
- **Security**: Bandit, Safety, pip-audit

## Key Features

### Core Administration
- **Message Management**: Bulk message deletion with configurable limits
- **User Moderation**: Kick, ban, mute, and timeout commands
- **Permission System**: Role-based access control
- **Audit Logging**: Comprehensive action tracking

### User Engagement
- **Achievement System**: Progressive achievements for user interactions
- **Message Logging**: Detailed message history and analytics
- **Anti-Spam Protection**: Intelligent spam detection and prevention
- **User Statistics**: Server activity and participation metrics

### Entertainment Features
- **Interactive Games**: Russian Roulette, Deep Sea Oxygen
- **Music Player**: Voice channel music streaming
- **Fun Commands**: Various entertainment and utility commands

### External Integrations
- **osu! Integration**: Player statistics and tracking
- **GitHub Monitoring**: Repository updates and notifications
- **Webhook Support**: External service integration

## Quick Start

### Prerequisites
- Python 3.8 or higher
- Discord Bot Token
- Git for cloning

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/finn001023-cpu/bot.git
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
# Edit .env with your Discord bot token and other settings
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

- **Documentation**: Check the [wiki](https://github.com/finn001023-cpu/bot/wiki)
- **Issues**: [Report bugs](https://github.com/finn001023-cpu/bot/issues)
- **Discussions**: [Community forum](https://github.com/finn001023-cpu/bot/discussions)

---

**Thank you for using our Discord bot!** We're committed to providing a high-quality, well-documented, and secure solution for Discord server management.
