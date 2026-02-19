# API Documentation

## Bot API Endpoints

### osu! API Integration
The bot provides osu! user information through Discord slash commands.

#### Available Commands
- `/user_info_osu <username>` - Get osu! user statistics
- `/osu bind <username>` - Link Discord account to osu! account
- `/osu best` - Get best plays (requires linked account)
- `/osu recent` - Get recent plays (requires linked account)

### GitHub Integration
Monitor GitHub repositories for updates.

#### Commands
- `/repo_watch set owner:<owner> repo:<repo> channel:<channel>` - Set up monitoring
- `/repo_watch status` - Check monitoring status
- `/repo_watch disable` - Disable monitoring

## Configuration Files

### Bot Configuration (`data/config/bot.json`)
```json
{
  "guilds": {
    "guild_id": {
      "log_channel": "channel_id"
    }
  }
}
```

### Storage Files Location
- Achievements: `data/storage/achievements.json`
- Blacklist: `data/storage/blacklist.json`
- osu! Links: `data/storage/osu_links.json`
- GitHub Watch: `data/storage/github_watch.json`
- Log Channels: `data/storage/log_channels.json`

### Message Logs
- Guild messages: `data/logs/messages/guild_*.json`
- General logs: `data/logs/messages/message_log.json`
