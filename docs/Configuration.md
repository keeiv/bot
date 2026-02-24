# Configuration Guide

This guide covers all configuration options for the Discord bot, including environment variables, settings files, and runtime configuration.

## Table of Contents

- [Environment Variables](#environment-variables)
- [Configuration Files](#configuration-files)
- [Bot Settings](#bot-settings)
- [Feature Configuration](#feature-configuration)
- [Security Settings](#security-settings)
- [Logging Configuration](#logging-configuration)
- [Advanced Configuration](#advanced-configuration)

## Environment Variables

### Required Variables

These variables must be set for the bot to function:

```env
# Discord Bot Token (Required)
DISCORD_TOKEN=your_discord_bot_token_here
```

**How to get Discord Token:**
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your application
3. Go to "Bot" tab
4. Copy the token under "TOKEN"

### Optional Variables

#### Core Configuration
```env
# Bot prefix for commands (default: !)
COMMAND_PREFIX=!

# Bot status message (default: "Watching Discord!")
STATUS_MESSAGE=Online and ready!

# Activity type (default: watching)
# Options: playing, listening, watching, competing
ACTIVITY_TYPE=watching
```

#### Database Configuration
```env
# Database file path (default: data/bot.db)
DATABASE_PATH=data/bot.db

# Database backup interval in hours (default: 24)
BACKUP_INTERVAL=24
```

#### Logging Configuration
```env
# Log level (default: INFO)
# Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# Log file path (default: data/logs/bot.log)
LOG_FILE=data/logs/bot.log

# Enable console logging (default: true)
CONSOLE_LOGGING=true
```

#### External Service Integration
```env
# GitHub Integration
GITHUB_TOKEN=your_github_personal_access_token
GITHUB_USERNAME=your_github_username

# osu! Integration
OSU_API_KEY=your_osu_api_key
OSU_DEFAULT_MODE=standard  # standard, taiko, catch, mania, fruits

# Webhook Configuration
WEBHOOK_URL=your_discord_webhook_url
WEBHOOK_USERNAME=Bot Webhook
```

## Configuration Files

### Main Configuration File

Location: `data/config/bot.json`

```json
{
  "bot": {
    "name": "Discord Bot",
    "version": "1.0.0",
    "description": "Feature-rich Discord bot",
    "prefix": "!",
    "status": {
      "message": "Online and ready!",
      "activity": "watching",
      "type": "competing"
    }
  },
  "features": {
    "admin": {
      "enabled": true,
      "clear_limit": 100,
      "timeout_duration": 300
    },
    "achievements": {
      "enabled": true,
      "auto_save": true,
      "notification_channel": null
    },
    "anti_spam": {
      "enabled": true,
      "max_messages": 5,
      "time_window": 10,
      "punishment": "mute"
    },
    "message_logging": {
      "enabled": true,
      "log_edits": true,
      "log_deletes": true,
      "exclude_channels": []
    }
  },
  "guilds": {
    "guild_id": {
      "prefix": "!",
      "admin_role": "Admin",
      "mod_role": "Moderator",
      "welcome_channel": "welcome",
      "log_channel": "logs"
    }
  }
}
```

### Guild-Specific Configuration

Each guild can have individual settings:

```json
{
  "guilds": {
    "123456789012345678": {
      "prefix": "!",
      "admin_role": "Server Admin",
      "mod_role": "Moderator",
      "welcome_channel": "welcome",
      "log_channel": "moderation-logs",
      "features": {
        "anti_spam": {
          "enabled": true,
          "max_messages": 3,
          "time_window": 5
        },
        "message_logging": {
          "enabled": true,
          "exclude_channels": ["admin-only", "bot-commands"]
        }
      }
    }
  }
}
```

## Bot Settings

### Command Prefix Configuration

The bot supports multiple command prefixes:

```env
# Single prefix
COMMAND_PREFIX=!

# Multiple prefixes (comma-separated)
COMMAND_PREFIX=!,?,-

# Mention-based prefix (always enabled)
# Users can mention the bot instead of using prefix
```

### Status and Activity

Configure bot's Discord status:

```env
# Playing status
ACTIVITY_TYPE=playing
STATUS_MESSAGE=with commands

# Watching status
ACTIVITY_TYPE=watching
STATUS_MESSAGE=for new messages

# Listening status
ACTIVITY_TYPE=listening
STATUS_MESSAGE=to user commands

# Competing status
ACTIVITY_TYPE=competing
STATUS_MESSAGE=in a coding challenge
```

### Intent Configuration

Discord requires explicit intent configuration:

```env
# Enable privileged intents (requires verification in Discord Developer Portal)
ENABLE_MESSAGE_CONTENT=true
ENABLE_MEMBERS=true
ENABLE_PRESENCES=true
```

## Feature Configuration

### Admin Features

```json
{
  "admin": {
    "enabled": true,
    "commands": {
      "clear": {
        "enabled": true,
        "default_amount": 10,
        "max_amount": 100,
        "required_permission": "manage_messages"
      },
      "kick": {
        "enabled": true,
        "required_permission": "kick_members",
        "log_action": true
      },
      "ban": {
        "enabled": true,
        "required_permission": "ban_members",
        "log_action": true,
        "default_reason": "Violation of server rules"
      },
      "mute": {
        "enabled": true,
        "required_permission": "moderate_members",
        "default_duration": 300,
        "max_duration": 604800
      }
    }
  }
}
```

### Achievement System

```json
{
  "achievements": {
    "enabled": true,
    "auto_save": true,
    "save_interval": 300,
    "notification_channel": null,
    "achievements": {
      "first_message": {
        "name": "First Steps",
        "description": "Send your first message",
        "rarity": "common",
        "points": 10
      },
      "message_master": {
        "name": "Message Master",
        "description": "Send 1000 messages",
        "rarity": "legendary",
        "points": 1000
      }
    }
  }
}
```

### Anti-Spam Protection

```json
{
  "anti_spam": {
    "enabled": true,
    "detection": {
      "max_messages": 5,
      "time_window": 10,
      "similar_content_threshold": 0.8
    },
    "punishment": {
      "type": "mute",
      "duration": 300,
      "warn_before_punishment": true
    },
    "exemptions": {
      "roles": ["Admin", "Moderator"],
      "channels": ["spam-allowed"]
    }
  }
}
```

### Message Logging

```json
{
  "message_logging": {
    "enabled": true,
    "log_edits": true,
    "log_deletes": true,
    "log_reactions": true,
    "storage": {
      "type": "json",
      "file_path": "data/logs/messages.json",
      "rotation": {
        "enabled": true,
        "max_file_size": "100MB",
        "max_files": 10
      }
    },
    "filters": {
      "exclude_channels": ["admin-only", "bot-commands"],
      "exclude_users": ["bot_id"],
      "exclude_content": ["secret", "password"]
    }
  }
}
```

## Security Settings

### Token Security

```env
# Enable token encryption (experimental)
TOKEN_ENCRYPTION=false

# Token encryption key (if encryption enabled)
TOKEN_ENCRYPTION_KEY=your_32_character_encryption_key
```

### Rate Limiting

```json
{
  "rate_limiting": {
    "enabled": true,
    "global_limit": {
      "requests": 100,
      "period": 60
    },
    "user_limit": {
      "requests": 10,
      "period": 60
    },
    "exemptions": {
      "roles": ["Admin", "Premium"],
      "users": ["bot_owner_id"]
    }
  }
}
```

### Blacklist Management

```json
{
  "blacklist": {
    "users": [
      {
        "user_id": "123456789",
        "reason": "Spamming",
        "banned_by": "Admin",
        "timestamp": "2024-01-01T00:00:00Z"
      }
    ],
    "guilds": [],
    "auto_save": true
  }
}
```

## Logging Configuration

### Log Levels and Formatting

```env
# Log level configuration
LOG_LEVEL=INFO
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s
LOG_DATE_FORMAT=%Y-%m-%d %H:%M:%S
```

### Log Rotation

```json
{
  "logging": {
    "rotation": {
      "enabled": true,
      "max_size": "50MB",
      "backup_count": 5,
      "compression": "gzip"
    },
    "handlers": {
      "file": {
        "enabled": true,
        "level": "INFO"
      },
      "console": {
        "enabled": true,
        "level": "DEBUG"
      },
      "discord": {
        "enabled": false,
        "channel_id": "log_channel_id",
        "level": "WARNING"
      }
    }
  }
}
```

### Structured Logging

```json
{
  "structured_logging": {
    "enabled": false,
    "format": "json",
    "fields": {
      "timestamp": true,
      "level": true,
      "logger": true,
      "message": true,
      "guild_id": true,
      "user_id": true,
      "command": true
    }
  }
}
```

## Advanced Configuration

### Performance Tuning

```env
# Discord gateway settings
GATEWAY_COMPRESSION=true
MAX_MESSAGE_SIZE=2000
HEARTBEAT_TIMEOUT=60

# Async settings
MAX_CONCURRENT_TASKS=100
TASK_TIMEOUT=300
```

### Caching Configuration

```json
{
  "cache": {
    "enabled": true,
    "type": "memory",
    "ttl": 3600,
    "max_size": 1000,
    "strategies": {
      "user_data": true,
      "guild_data": true,
      "command_cooldowns": true
    }
  }
}
```

### Database Configuration

```env
# SQLite configuration
DATABASE_PATH=data/bot.db
DATABASE_TIMEOUT=30
DATABASE_CHECK_SAME_THREAD=false

# Connection pooling
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10
```

### Web Server Configuration (for webhooks)

```env
# Enable web server for webhooks
WEB_SERVER_ENABLED=false
WEB_SERVER_HOST=127.0.0.1
WEB_SERVER_PORT=8080
WEB_SERVER_SSL=false
```

## Configuration Validation

### Validation Script

Run the configuration validator to check your setup:

```bash
python scripts/validate_config.py
```

### Common Validation Issues

**Missing Required Variables:**
```
Error: DISCORD_TOKEN is required but not set
```
**Solution**: Add the missing variable to your `.env` file

**Invalid JSON:**
```
Error: Invalid JSON in data/config/bot.json
```
**Solution**: Use a JSON validator to fix syntax errors

**Permission Issues:**
```
Error: Cannot write to data directory
```
**Solution**: Check directory permissions and ownership

## Environment-Specific Configuration

### Development Environment

```env
# Development settings
DEBUG=true
LOG_LEVEL=DEBUG
RELOAD_ON_CHANGE=true
```

### Production Environment

```env
# Production settings
DEBUG=false
LOG_LEVEL=INFO
RELOAD_ON_CHANGE=false
TOKEN_ENCRYPTION=true
```

### Testing Environment

```env
# Testing settings
TEST_MODE=true
MOCK_DISCORD_API=true
LOG_LEVEL=DEBUG
```

## Migration Guide

### Upgrading Configuration

When upgrading bot versions:

1. **Backup current configuration**
```bash
cp data/config/bot.json data/config/bot.json.backup
```

2. **Check for new configuration options**
```bash
python scripts/check_config_migration.py
```

3. **Update configuration file**
   - Add new required fields
   - Remove deprecated options
   - Update existing values

4. **Validate new configuration**
```bash
python scripts/validate_config.py
```

## Best Practices

### Security Best Practices

1. **Never commit `.env` files** to version control
2. **Use strong, unique tokens** for each deployment
3. **Rotate tokens regularly** (every 90 days)
4. **Limit bot permissions** to only what's necessary
5. **Monitor audit logs** for suspicious activity

### Performance Best Practices

1. **Use appropriate log levels** for production
2. **Enable log rotation** to prevent disk space issues
3. **Configure caching** for frequently accessed data
4. **Monitor resource usage** and adjust limits
5. **Use structured logging** for better analysis

### Maintenance Best Practices

1. **Regular backups** of configuration and data
2. **Document custom configurations** for team reference
3. **Test configuration changes** in development first
4. **Monitor configuration validation** results
5. **Keep configuration files** in version control (except secrets)

---

**Configuration complete!** Your bot should now be properly configured for your specific needs.
