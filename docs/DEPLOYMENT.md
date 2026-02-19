# Deployment Guide

## Prerequisites
- Python 3.8 or higher
- Discord Bot Token
- (Optional) osu! API credentials
- (Optional) GitHub Personal Access Token

## Setup Steps

### 1. Clone Repository
```bash
git clone https://github.com/finn001023-cpu/bot.git
cd bot
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env` and fill in your credentials:
```env
DISCORD_TOKEN=your_discord_token
OSU_CLIENT_ID=your_osu_client_id
OSU_CLIENT_SECRET=your_osu_client_secret
GITHUB_TOKEN=your_github_token
```

### 4. Run Migration
```bash
python scripts/migrate.py
```

### 5. Start the Bot
```bash
python src/main.py
```

## Alternative: Automated Deployment
Use the deployment script:
```bash
python scripts/deploy.py
```

## Docker Deployment (Future)
A Docker configuration will be added in a future update for containerized deployment.

## Troubleshooting

### Common Issues
1. **Import Errors**: Ensure all dependencies are installed
2. **Permission Errors**: Check bot has proper Discord permissions
3. **API Failures**: Verify API tokens are valid and have required scopes

### Log Location
- Bot logs: Console output
- Message logs: `data/logs/messages/`
- Error logs: Will be added to `data/logs/errors/` in future
