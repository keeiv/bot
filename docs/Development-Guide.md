# Development Guide

This guide covers setting up a development environment, coding standards, testing practices, and contribution workflow.

## Table of Contents

- [Development Environment Setup](#development-environment-setup)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Code Review Process](#code-review-process)
- [Debugging](#debugging)
- [Performance Optimization](#performance-optimization)
- [Documentation](#documentation)

## Development Environment Setup

### Prerequisites

- **Python**: 3.8 or higher (3.11+ recommended)
- **Git**: Latest version
- **IDE**: VS Code, PyCharm, or similar
- **Discord Account**: For bot testing

### Initial Setup

1. **Fork and Clone Repository**
```bash
# Fork the repository on GitHub
git clone https://github.com/YOUR_USERNAME/bot.git
cd bot

# Add upstream remote
git remote add upstream https://github.com/finn001023-cpu/bot.git
```

2. **Create Virtual Environment**
```bash
# Create virtual environment
python -m venv .venv

# Activate (Unix/macOS)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate
```

3. **Install Development Dependencies**
```bash
# Upgrade pip
python -m pip install --upgrade pip

# Install development requirements
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### IDE Configuration

#### VS Code Setup

1. **Install Extensions**
```
- Python (Microsoft)
- Python Docstring Generator (Nils Werner)
- Black Formatter (Microsoft)
- isort (Microsoft)
- MyPy (Microsoft)
- GitLens (GitKraken)
```

2. **Workspace Settings (`.vscode/settings.json`)**
```json
{
  "python.defaultInterpreterPath": "./.venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.sortImports.args": ["--profile", "google"],
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests"],
  "python.testing.unittestEnabled": false
}
```

#### PyCharm Setup

1. **Configure Project Interpreter**
   - File → Settings → Project → Python Interpreter
   - Add `.venv/bin/python` as project interpreter

2. **Enable Code Quality Tools**
   - Settings → Tools → External Tools
   - Configure Black, isort, and MyPy

3. **Configure Testing**
   - Settings → Tools → Python Integrated Tools
   - Set pytest as default test runner

### Environment Configuration

1. **Development Environment File**
```bash
cp .env.example .env.development
```

2. **Development Variables**
```env
# Development settings
DEBUG=true
LOG_LEVEL=DEBUG
RELOAD_ON_CHANGE=true

# Test Discord token (create separate test bot)
DISCORD_TOKEN=your_test_bot_token

# Development database
DATABASE_PATH=data/dev_bot.db
```

3. **Git Ignore Development Files**
```gitignore
# Development files
.env.development
data/dev_*
logs/dev_*
*.pyc
__pycache__/
.pytest_cache/
.coverage
htmlcov/
```

## Coding Standards

### English-First Policy

All code must follow strict English standards:

#### Variable and Function Names
```python
# Good - descriptive English names
user_message_count = 0
async def send_welcome_message(self, user: discord.Member) -> None:
    pass

# Bad - non-English or unclear
msg_cnt = 0
async def send_msg(self, user) -> None:
    pass
```

#### Class Names
```python
# Good - PascalCase English nouns
class MessageLogger(commands.Cog):
    pass

class AchievementManager:
    pass

# Bad - non-English or unclear
class MsgLogger(commands.Cog):
    pass
```

#### Constants
```python
# Good - UPPER_CASE English
MAX_MESSAGE_LENGTH = 2000
DEFAULT_TIMEOUT_DURATION = 300

# Bad - unclear or non-English
MAX_LEN = 2000
TIMEOUT = 300
```

### Code Formatting

#### Black Formatting
```bash
# Format all Python files
black src/ tests/

# Check formatting without changing files
black --check src/ tests/

# Format specific file
black src/bot.py
```

#### Import Sorting with isort
```bash
# Sort all imports
isort src/ tests/

# Check import sorting
isort --check-only src/ tests/

# Sort specific file
isort src/bot.py
```

#### Type Hints
```python
# All public functions must have type hints
async def process_command(
    self, 
    ctx: commands.Context, 
    command_name: str
) -> bool:
    """Process a user command."""
    return True

# Class methods should include self type
class MessageHandler:
    async def handle_message(self, message: discord.Message) -> None:
        pass
```

### Documentation Standards

#### Docstring Format (Google Style)
```python
def calculate_user_stats(user_id: int, guild_id: int) -> Dict[str, Any]:
    """Calculate comprehensive user statistics.
    
    This function aggregates user activity data across multiple dimensions
    including message count, achievement progress, and participation metrics.
    
    Args:
        user_id: The Discord user ID to calculate stats for.
        guild_id: The guild ID to scope the statistics to.
        
    Returns:
        A dictionary containing:
        - message_count: Total messages sent
        - achievement_count: Number of unlocked achievements
        - join_date: When the user joined the guild
        - last_active: Last activity timestamp
        
    Raises:
        ValueError: If user_id or guild_id is invalid.
        DataError: If statistical data cannot be retrieved.
    """
    # Implementation here
    pass
```

#### Inline Comments
```python
# Check user permissions before processing command
if not ctx.author.guild_permissions.administrator:
    await ctx.send("You need administrator permissions.")
    return

# Calculate timeout duration in seconds
timeout_seconds = duration * 60
await user.timeout(timeout_seconds, reason=reason)
```

## Testing Guidelines

### Test Structure

```
tests/
├── unit/                 # Unit tests for individual functions
│   ├── test_bot.py
│   ├── test_cogs/
│   └── test_utils/
├── integration/          # Integration tests for component interaction
│   ├── test_admin_commands.py
│   └── test_achievement_system.py
├── fixtures/            # Test data and mock objects
│   ├── mock_discord_objects.py
│   └── test_data.json
└── conftest.py         # Pytest configuration and fixtures
```

### Unit Testing

#### Test File Structure
```python
import pytest
from unittest.mock import Mock, AsyncMock
from src.cogs.core.admin import Admin

class TestAdmin:
    @pytest.fixture
    def admin_cog(self):
        """Create Admin cog instance for testing."""
        bot = Mock()
        return Admin(bot)
    
    @pytest.fixture
    def mock_ctx(self):
        """Create mock command context."""
        ctx = AsyncMock()
        ctx.author.guild_permissions.manage_messages = True
        ctx.channel.purge = AsyncMock(return_value=[])
        ctx.followup.send = AsyncMock()
        return ctx
    
    @pytest.mark.asyncio
    async def test_clear_command_success(self, admin_cog, mock_ctx):
        """Test clear command with valid parameters."""
        # Arrange
        amount = 10
        mock_ctx.channel.purge.return_value = [Mock() for _ in range(amount)]
        
        # Act
        await admin_cog.clear(mock_ctx, amount)
        
        # Assert
        mock_ctx.channel.purge.assert_called_once_with(limit=amount)
        mock_ctx.followup.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_clear_command_insufficient_permissions(self, admin_cog, mock_ctx):
        """Test clear command without permissions."""
        # Arrange
        mock_ctx.author.guild_permissions.manage_messages = False
        
        # Act & Assert
        with pytest.raises(commands.MissingPermissions):
            await admin_cog.clear(mock_ctx, 10)
```

#### Test Categories

**Unit Tests**: Test individual functions and methods
```python
def test_format_duration_seconds():
    """Test duration formatting function."""
    assert format_duration(60) == "1 minute"
    assert format_duration(3600) == "1 hour"
    assert format_duration(3661) == "1 hour, 1 minute, 1 second"
```

**Integration Tests**: Test component interactions
```python
@pytest.mark.asyncio
async def test_achievement_system_integration():
    """Test achievement system with message logging."""
    # Test that achievements are unlocked when conditions are met
    pass
```

### Running Tests

#### Local Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_bot.py

# Run with verbose output
pytest -v

# Run specific test
pytest tests/unit/test_admin.py::TestAdmin::test_clear_command_success
```

#### Continuous Integration Testing
```bash
# Run tests with all Python versions
tox

# Run performance tests
pytest tests/performance/ --benchmark-only
```

### Test Coverage

#### Coverage Requirements
- **Overall Coverage**: >80%
- **Critical Paths**: 100%
- **New Features**: >90%

#### Coverage Commands
```bash
# Generate coverage report
pytest --cov=src --cov-report=html

# Check coverage threshold
pytest --cov=src --cov-fail-under=80

# View coverage in browser
open htmlcov/index.html
```

## Code Review Process

### Pull Request Requirements

#### Before Submitting PR

1. **Code Quality Checks**
```bash
# Run all quality checks
pre-commit run --all-files

# Manual checks
black --check src/
isort --check-only src/
flake8 src/
mypy src/
python scripts/check_english_standards.py
```

2. **Testing Requirements**
```bash
# Ensure all tests pass
pytest

# Check coverage
pytest --cov=src --cov-fail-under=80
```

3. **Documentation Updates**
   - Update docstrings for new functions
   - Add API documentation for new endpoints
   - Update README if user-facing changes

#### Pull Request Template

```markdown
## Description
Brief description of changes and their purpose.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code quality improvement

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed
- [ ] Coverage >80%

## Code Quality
- [ ] English standards compliance
- [ ] Type hints complete
- [ ] Docstrings updated
- [ ] Pre-commit hooks pass

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests added for new functionality
- [ ] All tests passing
```

### Review Guidelines

#### Code Review Checklist

**Functionality**
- [ ] Code works as intended
- [ ] Edge cases handled
- [ ] Error handling appropriate
- [ ] Performance acceptable

**Code Quality**
- [ ] English-only code and comments
- [ ] Type hints complete and correct
- [ ] Code follows style guidelines
- [ ] No hardcoded values
- [ ] Proper error messages

**Testing**
- [ ] Tests cover new functionality
- [ ] Tests are well-written
- [ ] Edge cases tested
- [ ] Mock objects used appropriately

**Documentation**
- [ ] Docstrings follow Google style
- [ ] API documentation updated
- [ ] README updated if needed
- [ ] Comments explain complex logic
```

## Debugging

### Debug Configuration

#### Logging Setup
```python
import logging

# Enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Discord.py debug logging
discord.utils.setup_logging(level=logging.DEBUG)
```

#### Debug Mode
```env
# Enable debug features
DEBUG=true
LOG_LEVEL=DEBUG
ENABLE_PROFILING=true
```

### Debugging Tools

#### VS Code Debugger
```json
// .vscode/launch.json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Discord Bot",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/src/main.py",
            "console": "integratedTerminal",
            "cwd": "${workspaceFolder}",
            "env": {
                "PYTHONPATH": "${workspaceFolder}/src"
            }
        }
    ]
}
```

#### PyCharm Debugger
1. Create run configuration
2. Script: `src/main.py`
3. Working directory: project root
4. Environment variables: load from `.env.development`

### Common Debugging Scenarios

#### Bot Not Responding
```python
# Add debug logging to command handler
async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
    logging.error(f"Command error in {ctx.command}: {error}")
    # Handle error
```

#### Database Issues
```python
# Add database operation logging
async def save_user_data(user_id: int, data: Dict[str, Any]) -> None:
    try:
        # Database operation
        logging.debug(f"Saving data for user {user_id}: {data}")
    except Exception as e:
        logging.error(f"Database error for user {user_id}: {e}")
        raise
```

#### Discord API Issues
```python
# Add Discord API logging
@bot.event
async def on_ready():
    logging.info(f"Bot connected as {bot.user}")
    logging.info(f"Connected to {len(bot.guilds)} guilds")
```

## Performance Optimization

### Profiling

#### Enable Profiling
```python
import cProfile
import pstats

# Profile specific function
def profile_function(func):
    def wrapper(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        result = func(*args, **kwargs)
        pr.disable()
        
        stats = pstats.Stats(pr)
        stats.sort_stats('cumulative')
        stats.print_stats(10)
        return result
    return wrapper

@profile_function
async def expensive_operation():
    # Expensive operation here
    pass
```

#### Memory Profiling
```python
import tracemalloc

# Start memory tracing
tracemalloc.start()

# Take memory snapshot
snapshot1 = tracemalloc.take_snapshot()

# Run operation
await process_large_dataset()

# Compare snapshots
snapshot2 = tracemalloc.take_snapshot()
top_stats = snapshot2.compare_to(snapshot1, 'lineno')
for stat in top_stats[:10]:
    print(stat)
```

### Optimization Techniques

#### Async/Await Best Practices
```python
# Good - concurrent operations
async def process_multiple_users(user_ids: List[int]) -> None:
    tasks = [process_user(user_id) for user_id in user_ids]
    await asyncio.gather(*tasks)

# Bad - sequential operations
async def process_multiple_users_bad(user_ids: List[int]) -> None:
    for user_id in user_ids:
        await process_user(user_id)  # Blocks each iteration
```

#### Caching Strategies
```python
from functools import lru_cache
import discord

@lru_cache(maxsize=128)
def get_user_permission_level(user_id: int) -> str:
    """Cache permission lookups."""
    # Expensive permission calculation
    return calculate_permission_level(user_id)

# Discord object caching
class GuildCache:
    def __init__(self):
        self._cache = {}
    
    async def get_guild(self, guild_id: int) -> discord.Guild:
        if guild_id not in self._cache:
            self._cache[guild_id] = await bot.fetch_guild(guild_id)
        return self._cache[guild_id]
```

#### Database Optimization
```python
# Batch operations
async def update_multiple_users(user_updates: List[Tuple[int, Dict]]) -> None:
    """Update multiple users in single transaction."""
    async with database.transaction():
        for user_id, data in user_updates:
            await database.execute(
                "UPDATE users SET data = ? WHERE user_id = ?",
                (json.dumps(data), user_id)
            )

# Connection pooling
database = await aiosqlite.connect(
    "bot.db",
    check_same_thread=False,
    timeout=30.0
)
```

## Documentation

### Documentation Standards

#### Code Documentation
- All public APIs must have docstrings
- Use Google style format
- Include type hints
- Document parameters and return values
- Document exceptions

#### API Documentation
- Keep API Reference up to date
- Include usage examples
- Document all parameters
- Provide error handling examples

#### README Updates
- Update installation instructions
- Add new feature descriptions
- Update configuration examples
- Include troubleshooting information

### Documentation Tools

#### Sphinx Setup
```bash
# Install Sphinx
pip install sphinx sphinx-rtd-theme

# Generate documentation
cd docs/
make html

# Serve documentation
python -m http.server 8000
```

#### Docstring Generation
```python
# Use docstring generator
"""Process user command and return execution status.

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

---

**Development setup complete!** You now have a comprehensive development environment with all necessary tools and guidelines for contributing to the Discord bot project.
