# Contributing to Discord Bot

Thank you for your interest in contributing to this Discord bot project. This guide will help you understand our development standards and workflow.

## Table of Contents

- [Code Standards](#code-standards)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Review Process](#code-review-process)
- [Project Structure](#project-structure)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)

## Code Standards

### English-First Policy

All code, comments, documentation, and user-facing strings must be written in English. This ensures:

- International accessibility
- Consistent codebase readability
- Professional maintenance standards

### Naming Conventions

**Variables and Functions:**
```python
# Use descriptive snake_case with English words
user_message_count = 0
async def send_welcome_message(self, user: discord.Member):
    pass
```

**Classes:**
```python
# Use PascalCase with English nouns
class MessageLogger(commands.Cog):
    pass

class AchievementManager:
    pass
```

**Constants:**
```python
# Use UPPER_CASE with English names
MAX_MESSAGE_LENGTH = 2000
DEFAULT_TIMEOUT_DURATION = 60
```

### Documentation Standards

All functions and classes must have Google-style docstrings in English:

```python
async def process_user_command(self, ctx: commands.Context, command_name: str) -> bool:
    """Process a user command and return execution status.

    Args:
        ctx: The command context containing user information.
        command_name: The name of the command to process.

    Returns:
        True if command was executed successfully, False otherwise.

    Raises:
        ValueError: If command_name is empty or invalid.
        CommandError: If command execution fails.
    """
    pass
```

### Code Formatting

This project enforces strict formatting rules through:

- **EditorConfig**: Consistent indentation and line endings
- **Black**: Code formatting with 88-character line limit
- **isort**: Import organization following Google style
- **flake8**: Code quality and style checking
- **MyPy**: Static type checking with strict mode

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Git
- GitHub account

### Initial Setup

1. Fork the repository on GitHub
2. Clone your fork locally:
```bash
git clone https://github.com/YOUR_USERNAME/bot.git
cd bot
```

3. Add the original repository as upstream:
```bash
git remote add upstream https://github.com/finn001023-cpu/bot.git
```

4. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

5. Install dependencies:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

6. Install pre-commit hooks:
```bash
pre-commit install
```

### Environment Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Fill in your Discord bot token and other required variables in `.env`

## Development Workflow

### Branch Strategy

- `main`: Stable production branch
- `develop`: Integration branch for new features
- `feature/feature-name`: Feature development branches
- `bugfix/bug-description`: Bug fix branches
- `hotfix/critical-fix`: Urgent fixes

### Creating a Feature Branch

1. Ensure your main branch is up to date:
```bash
git checkout main
git pull upstream main
```

2. Create a new feature branch:
```bash
git checkout -b feature/your-feature-name
```

### Making Changes

1. Write your code following the established standards
2. Add tests for new functionality
3. Update documentation as needed
4. Run pre-commit hooks automatically:
```bash
pre-commit run --all-files
```

### Commit Messages

Follow Conventional Commits format:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code formatting changes
- `refactor`: Code refactoring
- `test`: Test additions or changes
- `chore`: Maintenance tasks

Examples:
```
feat(admin): add timeout command for member moderation

Implement the timeout command that allows moderators to temporarily
mute members for a specified duration.

Closes #123
```

```
fix(auth): resolve token validation error

Fixes issue where bot tokens with special characters were not
properly validated during startup.
```

## Code Review Process

### Pull Request Requirements

Before submitting a pull request:

1. **Code Quality**: All automated checks must pass
2. **Tests**: New features must include tests with >80% coverage
3. **Documentation**: Updated docstrings and README sections
4. **English Standards**: All text must be in English
5. **Formatting**: Code must pass Black, isort, and flake8 checks

### Pull Request Template

```markdown
## Description
Brief description of changes made.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] All tests passing
```

### Review Process

1. Automated checks run automatically
2. Maintainer review focuses on:
   - Code quality and architecture
   - English documentation standards
   - Test coverage and quality
   - Security considerations
3. Address all review comments
4. Maintain approval required for merge

## Project Structure

```
bot/
├── src/
│   ├── bot.py              # Main bot class
│   ├── main.py             # Entry point
│   ├── cogs/               # Bot modules
│   │   ├── core/          # Core functionality
│   │   ├── features/      # Feature modules
│   │   └── games/         # Game modules
│   ├── utils/             # Utility functions
│   └── bot_types/         # Type definitions
├── tests/                 # Test files
├── docs/                  # Documentation
├── data/                  # Runtime data
├── scripts/               # Utility scripts
└── services/              # External service configs
```

### Module Organization

**Core Modules** (`src/cogs/core/`):
- Essential bot functionality
- Administrative commands
- System utilities

**Feature Modules** (`src/cogs/features/`):
- User-facing features
- External integrations
- Specialized functionality

**Game Modules** (`src/cogs/games/`):
- Interactive games
- Entertainment features

**Utilities** (`src/utils/`):
- Helper functions
- Shared utilities
- Configuration management

## Testing Guidelines

### Test Structure

```python
import pytest
from unittest.mock import Mock, AsyncMock
from src.cogs.core.admin import Admin

class TestAdmin:
    @pytest.fixture
    def admin_cog(self):
        bot = Mock()
        return Admin(bot)
    
    @pytest.fixture
    def mock_ctx(self):
        ctx = AsyncMock()
        ctx.author.guild_permissions.manage_messages = True
        return ctx
    
    @pytest.mark.asyncio
    async def test_clear_command_success(self, admin_cog, mock_ctx):
        """Test clear command with valid parameters."""
        # Arrange
        amount = 10
        
        # Act
        await admin_cog.clear(mock_ctx, amount)
        
        # Assert
        mock_ctx.channel.purge.assert_called_once_with(limit=amount)
        mock_ctx.followup.send.assert_called_once()
```

### Test Requirements

1. **Unit Tests**: Test individual functions and methods
2. **Integration Tests**: Test module interactions
3. **Coverage**: Maintain >80% test coverage
4. **English Standards**: Test names and docstrings in English

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_admin.py

# Run with verbose output
pytest -v
```

## Documentation

### Code Documentation

- All public functions must have docstrings
- Complex logic requires inline comments
- Use type hints consistently
- Follow Google style for docstrings

### README Documentation

Keep README.md updated with:
- Installation instructions
- Usage examples
- Configuration options
- Contributing guidelines link

### API Documentation

For complex modules, maintain separate documentation in `docs/` directory:
- API reference
- Architecture diagrams
- Integration guides

## Getting Help

If you need help with contributing:

1. Check existing issues and discussions
2. Review the codebase for similar implementations
3. Ask questions in GitHub Discussions
4. Contact maintainers for guidance

## License

By contributing to this project, you agree that your contributions will be licensed under the same MIT license as the project.

---

Thank you for following these guidelines and helping improve this Discord bot project!
