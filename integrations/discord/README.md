# Pepper Discord Bot

Bridges Discord messages to Pepper's channel server.

## Discord Developer Portal Setup

1. Go to https://discord.com/developers/applications
2. Click **New Application**, name it "Pepper" (or your preferred name)
3. Go to **Bot** section:
   - Click **Reset Token** and copy the token
   - Under **Privileged Gateway Intents**, enable **Message Content Intent**
4. Go to **OAuth2 > URL Generator**:
   - Scopes: select `bot`
   - Bot Permissions: select:
     - Send Messages
     - Send Messages in Threads
     - Read Message History
     - Add Reactions
     - View Channels
   - Copy the generated URL and open it to add the bot to your server

## Configuration

```bash
cp .env.example .env
# Edit .env and add your bot token:
# DISCORD_BOT_TOKEN=your-token-here
```

## Running

The bot is started automatically by the launch script:

```bash
# From the pepper root directory:
./scripts/start-pepper.sh
```

Or run standalone for testing:

```bash
cd integrations/discord
uv run python bot.py
```

## How It Works

- The bot listens for messages in all channels it's been added to, plus DMs
- Messages are forwarded to the channel server at localhost:8788
- Replies from Pepper come back via SSE stream and are sent to Discord
- The bot shows a typing indicator while Pepper is thinking
- Pepper can react to messages and send rich embeds
