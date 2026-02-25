# Management Cog Usage Guide

## Repository Tracking
Track GitHub repository updates including commits and pull requests.

### Commands:
- `/repo_track add <owner> <repo> <channel>` - Add repository to track
- `/repo_track remove <owner> <repo>` - Remove repository from tracking
- `/repo_track status` - Show tracking status

### Example:
```
/repo_track add owner:discordjs repo:discord.js channel:#updates
```

## Role Management
Assign and remove roles from server members.

### Commands:
- `/role assign <user> <role>` - Assign role to user
- `/role remove <user> <role>` - Remove role from user

### Permissions:
- Requires "Manage Roles" permission
- Cannot assign/remove roles higher than your highest role

## Emoji Management
Get large versions of emojis and upload new ones.

### Commands:
- `/emoji get <emoji>` - Get emoji as large image
- `/emoji upload <name> <image>` - Upload emoji to server

### Permissions:
- Upload requires "Manage Emojis" permission
- Bot needs "Manage Emojis" permission

## Welcome Messages
Setup automatic welcome messages for new members.

### Commands:
- `/welcome setup <channel> [message]` - Setup welcome messages
- `/welcome disable` - Disable welcome messages
- `/welcome preview` - Preview welcome message

### Message Template Variables:
- `{user}` - User mention
- `{server}` - Server name

### Default Message:
```
Welcome {user} to {server}!
```

### Example:
```
/welcome setup channel:#welcome message:"Hello {user}! Welcome to {server}! Please read the rules."
```

## Required Bot Permissions
- Manage Channels
- Manage Roles
- Manage Emojis
- Send Messages
- Embed Links
- Read Message History

## Data Storage
All configuration is stored in `data/storage/management.json`

## Notes
- Repository tracking checks for updates every 5 minutes
- All commands require appropriate Discord permissions
- No emoji symbols are used in code or messages
