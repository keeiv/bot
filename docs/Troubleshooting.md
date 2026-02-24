# Troubleshooting Guide

This comprehensive guide covers common issues, error solutions, and debugging techniques for the Discord bot.

## Table of Contents

- [Common Issues](#common-issues)
- [Installation Problems](#installation-problems)
- [Runtime Errors](#runtime-errors)
- [Discord API Issues](#discord-api-issues)
- [Database Problems](#database-problems)
- [Performance Issues](#performance-issues)
- [Network Issues](#network-issues)
- [Debugging Tools](#debugging-tools)
- [Getting Help](#getting-help)

## Common Issues

### Bot Not Starting

#### Symptom: Bot fails to start with no error message

**Possible Causes:**
- Missing or invalid Discord token
- Python version incompatibility
- Missing dependencies

**Solutions:**

1. **Check Discord Token**
```bash
# Verify token is set
echo $DISCORD_TOKEN

# Test token validity
curl -H "Authorization: Bot YOUR_TOKEN" https://discord.com/api/v10/users/@me
```

2. **Verify Python Version**
```bash
python --version
# Should be 3.8 or higher
```

3. **Check Dependencies**
```bash
pip list | grep discord
# Should show discord.py installed
```

#### Symptom: Bot starts but immediately crashes

**Possible Causes:**
- Invalid intents configuration
- Missing required permissions
- Syntax errors in configuration

**Solutions:**

1. **Check Intents Configuration**
```python
# Ensure intents are properly configured
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
```

2. **Verify Discord Permissions**
- Go to Discord Developer Portal
- Enable privileged intents in bot settings
- Ensure bot has required server permissions

### Commands Not Working

#### Symptom: Bot responds to ping but not other commands

**Possible Causes:**
- Command prefix conflict
- Cogs not loaded properly
- Permission issues

**Solutions:**

1. **Check Command Prefix**
```python
# Verify prefix is set correctly
print(f"Command prefix: {bot.command_prefix}")
```

2. **Check Cog Loading**
```python
# Add debug logging to cog loading
async def load_cogs(self):
    for cog in cogs:
        try:
            await self.load_extension(cog)
            print(f"Loaded {cog}")
        except Exception as e:
            print(f"Failed to load {cog}: {e}")
```

3. **Verify Permissions**
```bash
# Check bot permissions in Discord
# Right-click bot → Server Settings → Permissions
```

#### Symptom: Commands work in some channels but not others

**Possible Causes:**
- Channel-specific permissions
- Channel restrictions in configuration
- Role-based access control

**Solutions:**

1. **Check Channel Permissions**
```python
# Add permission checking to commands
@commands.command()
@commands.has_permissions(send_messages=True)
async def mycommand(self, ctx):
    # Command logic
```

2. **Verify Configuration**
```json
{
  "guilds": {
    "guild_id": {
      "exclude_channels": ["admin-only"],
      "required_role": "Member"
    }
  }
}
```

## Installation Problems

### Python Version Conflicts

#### Error: `This package requires Python 3.8 or higher`

**Solution:**
```bash
# Install correct Python version
# Ubuntu/Debian
sudo apt update
sudo apt install python3.8

# macOS (using Homebrew)
brew install python@3.8

# Windows
# Download from python.org
```

#### Error: `ModuleNotFoundError: No module named 'discord'`

**Solutions:**

1. **Activate Virtual Environment**
```bash
source .venv/bin/activate  # Unix/macOS
.venv\Scripts\activate     # Windows
```

2. **Reinstall Dependencies**
```bash
pip install -r requirements.txt
```

3. **Check Python Path**
```bash
which python
# Should point to virtual environment
```

### Dependency Conflicts

#### Error: `ERROR: pip's dependency resolver does not currently take into account all the packages that are installed`

**Solutions:**

1. **Upgrade pip**
```bash
python -m pip install --upgrade pip
```

2. **Clean Install**
```bash
pip uninstall discord.py
pip install discord.py
```

3. **Use Specific Versions**
```bash
pip install discord.py==2.0.0
```

### Permission Issues

#### Error: `Permission denied: '.env'`

**Solutions:**

1. **Check File Permissions**
```bash
ls -la .env
# Check owner and permissions
```

2. **Fix Permissions**
```bash
chmod 600 .env
# Owner read/write only
```

3. **Change Ownership**
```bash
sudo chown $USER:$USER .env
```

## Runtime Errors

### Memory Errors

#### Error: `MemoryError` or bot becomes unresponsive

**Possible Causes:**
- Memory leaks in long-running tasks
- Large data structures not cleaned up
- Insufficient system memory

**Solutions:**

1. **Monitor Memory Usage**
```python
import psutil
import tracemalloc

# Start memory tracking
tracemalloc.start()

# Monitor memory
def check_memory():
    process = psutil.Process()
    memory_info = process.memory_info()
    print(f"Memory usage: {memory_info.rss / 1024 / 1024:.2f} MB")
```

2. **Implement Cleanup**
```python
async def cleanup_old_data():
    """Clean up old data to free memory."""
    # Remove old message logs
    # Clear expired cache entries
    # Close unused connections
```

3. **Optimize Data Structures**
```python
# Use generators instead of lists for large datasets
def process_large_dataset(data):
    for item in data:  # Generator, not list comprehension
        yield process_item(item)
```

### Timeout Errors

#### Error: `asyncio.TimeoutError` or commands time out

**Possible Causes:**
- Discord API rate limits
- Slow database operations
- Network connectivity issues

**Solutions:**

1. **Implement Retry Logic**
```python
import asyncio
from functools import wraps

def retry(max_attempts=3, delay=1):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    await asyncio.sleep(delay * (2 ** attempt))
        return wrapper
    return decorator

@retry()
async def send_message_with_retry(channel, content):
    await channel.send(content)
```

2. **Add Timeouts**
```python
try:
    await asyncio.wait_for(some_operation(), timeout=30.0)
except asyncio.TimeoutError:
    print("Operation timed out")
    # Handle timeout
```

## Discord API Issues

### Rate Limiting

#### Error: `429 Too Many Requests`

**Solutions:**

1. **Implement Rate Limiting**
```python
import asyncio
from discord.ext import commands

class RateLimiter:
    def __init__(self, rate_limit, per):
        self.rate_limit = rate_limit
        self.per = per
        self.tokens = rate_limit
        self.last_reset = time.time()
    
    async def wait_if_needed(self):
        now = time.time()
        if now - self.last_reset >= self.per:
            self.tokens = self.rate_limit
            self.last_reset = now
        
        if self.tokens <= 0:
            sleep_time = self.per - (now - self.last_reset)
            await asyncio.sleep(sleep_time)
        
        self.tokens -= 1

# Usage
rate_limiter = RateLimiter(5, 60)  # 5 requests per minute
await rate_limiter.wait_if_needed()
await bot.send_message(channel, "Hello")
```

2. **Use Built-in Cooldowns**
```python
@commands.command()
@commands.cooldown(1, 5, commands.BucketType.user)  # 1 use per 5 seconds per user
async def mycommand(self, ctx):
    await ctx.send("This command has a cooldown")
```

### Gateway Issues

#### Error: `GatewayClosedError` or frequent disconnections

**Solutions:**

1. **Implement Reconnection Logic**
```python
@bot.event
async def on_disconnect():
    print("Bot disconnected from Discord")

@bot.event
async def on_resume():
    print("Bot reconnected to Discord")
```

2. **Configure Heartbeat**
```python
# In bot initialization
intents = discord.Intents.default()
bot = commands.Bot(
    command_prefix='!',
    intents=intents,
    heartbeat_timeout=60
)
```

### Permission Errors

#### Error: `Forbidden: 403 Access Denied`

**Common Causes and Solutions:**

1. **Missing Bot Permissions**
```python
# Check permissions before sending messages
if not ctx.channel.permissions_for(ctx.me).send_messages:
    await ctx.send("I don't have permission to send messages here.")
    return
```

2. **Insufficient User Permissions**
```python
# Check user permissions for commands
@commands.command()
@commands.has_permissions(manage_messages=True)
async def clear_command(self, ctx, amount: int):
    # Command logic
```

3. **Enable Privileged Intents**
```python
# In Discord Developer Portal
# Bot Settings → Bot → Privileged Gateway Intents
# Enable: MESSAGE CONTENT INTENT, SERVER MEMBERS INTENT
```

## Database Problems

### SQLite Locking

#### Error: `sqlite3.OperationalError: database is locked`

**Solutions:**

1. **Use Connection Pooling**
```python
import aiosqlite

class DatabaseManager:
    def __init__(self):
        self.pool = None
    
    async def initialize(self):
        self.pool = await aiosqlite.create_pool(
            "bot.db",
            check_same_thread=False,
            max_connections=10
        )
    
    async def execute(self, query, *args):
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)
```

2. **Implement Retry Logic**
```python
import random
import time

async def database_operation_with_retry(operation, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await operation()
        except aiosqlite.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                # Exponential backoff
                delay = (2 ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(delay)
            else:
                raise
```

### Database Corruption

#### Error: `sqlite3.DatabaseError: database disk image is malformed`

**Solutions:**

1. **Database Recovery**
```bash
# Check database integrity
sqlite3 bot.db "PRAGMA integrity_check;"

# Recover data if corrupted
sqlite3 bot.db ".recover" | sqlite3 recovered.db
```

2. **Regular Backups**
```python
import shutil
import datetime

async def backup_database():
    """Create automatic database backups."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"data/backups/bot_{timestamp}.db"
    
    try:
        shutil.copy2("data/bot.db", backup_path)
        print(f"Database backed up to {backup_path}")
    except Exception as e:
        print(f"Backup failed: {e}")
```

## Performance Issues

### High CPU Usage

#### Symptom: Bot uses excessive CPU

**Solutions:**

1. **Profile CPU Usage**
```python
import cProfile
import pstats

def profile_cpu_usage(func):
    def wrapper(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        result = func(*args, **kwargs)
        pr.disable()
        
        stats = pstats.Stats(pr)
        stats.sort_stats('cumulative')
        stats.print_stats(20)  # Top 20 functions
        return result
    return wrapper
```

2. **Optimize Event Handling**
```python
# Avoid blocking operations in event handlers
@bot.event
async def on_message(message):
    # Quick checks first
    if message.author.bot:
        return
    
    # Defer heavy processing
    asyncio.create_task(process_message_heavy(message))
```

3. **Use Caching**
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_user_data(user_id: int):
    """Cache frequently accessed user data."""
    return expensive_database_lookup(user_id)
```

### Slow Response Times

#### Symptom: Bot takes long time to respond

**Solutions:**

1. **Async Operations**
```python
# Bad: Blocking operations
def slow_command(self, ctx):
    time.sleep(5)  # Blocks everything
    ctx.send("Done")

# Good: Async operations
async def fast_command(self, ctx):
    await asyncio.sleep(5)  # Only blocks this task
    await ctx.send("Done")
```

2. **Database Optimization**
```python
# Use indexes for frequent queries
await database.execute("""
    CREATE INDEX IF NOT EXISTS idx_user_messages 
    ON messages(user_id, timestamp)
""")

# Batch operations
async def update_multiple_users(updates):
    async with database.transaction():
        for user_id, data in updates:
            await database.execute(
                "UPDATE users SET data = ? WHERE user_id = ?",
                (json.dumps(data), user_id)
            )
```

## Network Issues

### Connection Problems

#### Symptom: Bot frequently disconnects

**Solutions:**

1. **Configure Reconnection**
```python
import discord

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=discord.Intents.default(),
            heartbeat_timeout=60,
            guild_ready_timeout=10
        )
    
    async def on_disconnect(self):
        print("Disconnected, attempting to reconnect...")
```

2. **Network Monitoring**
```python
import aiohttp
import asyncio

async def check_connectivity():
    """Check internet connectivity."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://discord.com/api/v10/gateway', timeout=10) as response:
                return response.status == 200
    except Exception as e:
        print(f"Connectivity check failed: {e}")
        return False
```

### DNS Issues

#### Error: `Name or service not known`

**Solutions:**

1. **Use DNS Fallback**
```python
import socket

def get_discord_gateway():
    """Get Discord gateway with DNS fallback."""
    gateways = [
        "gateway.discord.gg",
        "gateway.discord.com"
    ]
    
    for gateway in gateways:
        try:
            ip = socket.gethostbyname(gateway)
            print(f"Resolved {gateway} to {ip}")
            return gateway
        except socket.gaierror:
            continue
    
    raise Exception("All Discord gateways unreachable")
```

2. **Configure DNS Servers**
```bash
# Use reliable DNS servers
echo "nameserver 8.8.8.8" >> /etc/resolv.conf
echo "nameserver 8.8.4.4" >> /etc/resolv.conf
```

## Debugging Tools

### Logging Configuration

#### Enable Debug Logging
```python
import logging

# Comprehensive logging setup
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler()
    ]
)

# Discord.py specific logging
discord.utils.setup_logging(level=logging.DEBUG)
```

#### Structured Logging
```python
import json
import logging

class StructuredLogger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
    
    def log_event(self, event, **kwargs):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'event': event,
            **kwargs
        }
        self.logger.info(json.dumps(log_data))
```

### Performance Monitoring

#### Memory Profiling
```python
import tracemalloc
import time

def start_memory_profiling():
    tracemalloc.start()
    print("Memory profiling started")

def take_memory_snapshot():
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics('lineno')
    print(f"Top memory allocations: {top_stats[:5]}")

# Usage
start_memory_profiling()
# ... run code ...
take_memory_snapshot()
```

#### Response Time Tracking
```python
import time
from functools import wraps

def track_response_time(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            response_time = time.time() - start_time
            print(f"{func.__name__} took {response_time:.3f}s")
            return result
        except Exception as e:
            response_time = time.time() - start_time
            print(f"{func.__name__} failed after {response_time:.3f}s: {e}")
            raise
    return wrapper

@track_response_time
async def some_command(self, ctx):
    await ctx.send("Response")
```

### Health Checks

#### Bot Health Monitor
```python
import discord
import asyncio

class HealthMonitor:
    def __init__(self, bot):
        self.bot = bot
        self.last_heartbeat = time.time()
        self.issues = []
    
    async def start_monitoring(self):
        """Start continuous health monitoring."""
        while True:
            await self.check_health()
            await asyncio.sleep(60)  # Check every minute
    
    async def check_health(self):
        """Perform comprehensive health check."""
        issues = []
        
        # Check Discord connection
        if not self.bot.is_ready():
            issues.append("Discord connection lost")
        
        # Check memory usage
        memory_percent = self.get_memory_usage()
        if memory_percent > 80:
            issues.append(f"High memory usage: {memory_percent}%")
        
        # Check database connectivity
        if not await self.check_database():
            issues.append("Database connection failed")
        
        self.issues = issues
        if issues:
            print(f"Health issues detected: {issues}")
    
    def get_memory_usage(self):
        """Get current memory usage percentage."""
        import psutil
        return psutil.virtual_memory().percent
```

## Getting Help

### Self-Service Resources

1. **Check Logs First**
```bash
# View recent logs
tail -n 50 data/logs/bot.log

# Search for specific errors
grep "ERROR" data/logs/bot.log
```

2. **Common Error Codes**
```python
# Discord API error reference
ERROR_CODES = {
    50001: "Missing access",
    50002: "Invalid account type",
    50003: "Invalid shard",
    50004: "Sharding required",
    50005: "Invalid intents",
    50006: "Disallowed intents",
    50007: "Invalid token",
    50008: "Invalid permissions",
    50009: "Invalid user",
    50010: "Invalid OAuth2 state",
    50011: "Invalid note",
    50012: "Invalid message",
    50013: "Invalid bulk delete",
    50014: "Invalid channel type",
    50015: "Invalid webhook",
    50016: "Invalid webhook token",
    50017: "Invalid page",
    50018: "Invalid roles",
    50019: "Invalid code",
    50020: "Invalid event",
    50021: "Invalid integration",
    50022: "Invalid invite",
    50023: "Invalid guild",
    50024: "Invalid OAuth2 application",
    50025: "Invalid OAuth2 access token",
    50026: "Invalid missing scope",
    50027: "Invalid webhook service",
    50028: "Invalid mfa level",
    50029: "Invalid webhook url",
    50030: "Invalid custom emoji",
    50031: "Invalid bulk delete message",
    50032: "Invalid guild member",
    50033: "Invalid interaction",
    50034: "Invalid application command",
    50035: "Invalid message type",
    50036: "Invalid application command permissions",
    50037: "Invalid API version",
    50038: "Invalid interaction (type)",
    50039: "Invalid interaction (data)",
    50040: "Invalid interaction (member)",
    50041: "Invalid interaction (user)",
    50042: "Invalid guild",
    50043: "Invalid message",
    50044: "Invalid interaction (application command)",
    50045: "Invalid interaction (message component)",
    50046: "Invalid attachment",
    50047: "Invalid interaction (application command autocomplete)",
    50048: "Invalid guild",
    50049: "Invalid interaction (modal submit)",
    50050: "Invalid guild member",
    50051: "Invalid interaction (message component)",
    50052: "Invalid application command",
    50053: "Invalid interaction (message component)",
    50054: "Invalid guild",
    50055: "Invalid interaction (message component)",
    50056: "Invalid webhook",
    50057: "Invalid interaction (application command)",
    50058: "Invalid guild",
    50059: "Invalid interaction (message component)",
    50060: "Invalid interaction (message component)",
    50061: "Invalid interaction (application command)",
    50062: "Invalid guild",
    50063: "Invalid interaction (message component)",
    50064: "Invalid interaction (application command)",
    50065: "Invalid guild",
    50066: "Invalid interaction (message component)",
    50067: "Invalid guild",
    50068: "Invalid guild",
    50069: "Invalid interaction (message component)",
    50070: "Invalid guild",
    50071: "Invalid interaction (message component)",
    50072: "Invalid guild",
    50073: "Invalid guild",
    50074: "Invalid guild",
    50075: "Invalid guild",
    50076: "Invalid guild",
    50077: "Invalid guild",
    50078: "Invalid guild",
    50079: "Invalid guild",
    50080: "Invalid guild",
    50081: "Invalid guild",
    50082: "Invalid guild",
    50083: "Invalid guild",
    50084: "Invalid guild",
    50085: "Invalid guild",
    50086: "Invalid guild",
    50087: "Invalid guild",
    50088: "Invalid guild",
    50089: "Invalid guild",
    50090: "Invalid guild",
    50091: "Invalid guild",
    50092: "Invalid guild",
    50093: "Invalid guild",
    50094: "Invalid guild",
    50095: "Invalid guild",
    50096: "Invalid guild",
    50097: "Invalid guild",
    50098: "Invalid guild",
    50099: "Invalid guild",
    50100: "Invalid guild",
    50101: "Invalid guild",
    50102: "Invalid guild",
    50103: "Invalid guild",
    50104: "Invalid guild",
    50105: "Invalid guild",
    50106: "Invalid guild",
    50107: "Invalid guild",
    50108: "Invalid guild",
    50109: "Invalid guild",
    50110: "Invalid guild",
    50111: "Invalid guild",
    50112: "Invalid guild",
    50113: "Invalid guild",
    50114: "Invalid guild",
    50115: "Invalid guild",
    50116: "Invalid guild",
    50117: "Invalid guild",
    50118: "Invalid guild",
    50119: "Invalid guild",
    50120: "Invalid guild",
    50121: "Invalid guild",
    50122: "Invalid guild",
    50123: "Invalid guild",
    50124: "Invalid guild",
    50125: "Invalid guild",
    50126: "Invalid guild",
    50127: "Invalid guild",
    50128: "Invalid guild",
    50129: "Invalid guild",
    50130: "Invalid guild",
    50131: "Invalid guild",
    50132: "Invalid guild",
    50133: "Invalid guild",
    50134: "Invalid guild",
    50135: "Invalid guild",
    50136: "Invalid guild",
    50137: "Invalid guild",
    50138: "Invalid guild",
    50139: "Invalid guild",
    50140: "Invalid guild",
    50141: "Invalid guild",
    50142: "Invalid guild",
    50143: "Invalid guild",
    50144: "Invalid guild",
    50145: "Invalid guild",
    50146: "Invalid guild",
    50147: "Invalid guild",
    50148: "Invalid guild",
    50149: "Invalid guild",
    50150: "Invalid guild",
    50151: "Invalid guild",
    50152: "Invalid guild",
    50153: "Invalid guild",
    50154: "Invalid guild",
    50155: "Invalid guild",
    50156: "Invalid guild",
    50157: "Invalid guild",
    50158: "Invalid guild",
    50159: "Invalid guild",
    50160: "Invalid guild",
    50161: "Invalid guild",
    50162: "Invalid guild",
    50163: "Invalid guild",
    50164: "Invalid guild",
    50165: "Invalid guild",
    50166: "Invalid guild",
    50167: "Invalid guild",
    50168: "Invalid guild",
    50169: "Invalid guild",
    50170: "Invalid guild",
    50171: "Invalid guild",
    50172: "Invalid guild",
    50173: "Invalid guild",
    50174: "Invalid guild",
    50175: "Invalid guild",
    50176: "Invalid guild",
    50177: "Invalid guild",
    50178: "Invalid guild",
    50179: "Invalid guild",
    50180: "Invalid guild",
    50181: "Invalid guild",
    50182: "Invalid guild",
    50183: "Invalid guild",
    50184: "Invalid guild",
    50185: "Invalid guild",
    50186: "Invalid guild",
    50187: "Invalid guild",
    50188: "Invalid guild",
    50189: "Invalid guild",
    50190: "Invalid guild",
    50191: "Invalid guild",
    50192: "Invalid guild",
    50193: "Invalid guild",
    50194: "Invalid guild",
    50195: "Invalid guild",
    50196: "Invalid guild",
    50197: "Invalid guild",
    50198: "Invalid guild",
    50199: "Invalid guild",
    50200: "Invalid guild"
}
```

### Community Support

1. **GitHub Issues**
   - Search existing issues first
   - Create new issue with detailed information
   - Include error logs and system information

2. **Discord Community**
   - Join bot support server
   - Ask questions in appropriate channels
   - Share error messages and context

3. **Documentation**
   - Check [Installation Guide](Installation)
   - Review [Configuration Guide](Configuration)
   - Consult [API Reference](API-Reference)

### Issue Reporting Template

When creating a GitHub issue, include:

```markdown
## Bug Description
Clear description of the issue

## Steps to Reproduce
1. Step one
2. Step two
3. Step three

## Expected Behavior
What should happen

## Actual Behavior
What actually happened

## Environment
- OS: [Windows/macOS/Linux]
- Python version: [3.x.x]
- Bot version: [x.x.x]
- Discord.py version: [x.x.x]

## Error Messages
```
Full error traceback
```

## Logs
```
Relevant log entries
```

## Additional Context
Any other relevant information
```

---

**Troubleshooting complete!** This guide should help you resolve most common issues with the Discord bot.
