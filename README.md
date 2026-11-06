# Telegram Music Bot

Python + aiogram 3 Telegram bot.

## Current features
- Search YouTube music videos with YouTube Data API v3.
- Show up to five results as Telegram buttons.
- Relay audio files sent by users as Telegram audio messages.
- Keep API credentials in environment variables.

## Required environment variables
- `BOT_TOKEN` — token from @BotFather.
- `YOUTUBE_API_KEY` — YouTube Data API v3 key.

Never commit real tokens or `.env` files.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

Set the two environment variables before starting the bot. On Windows, activate with `.venv\\Scripts\\activate`.

## Commands
- `/start`
- `/help`
- `/search song name`

## Audio playback limitation
YouTube Data API returns metadata and video links; it does not provide an audio stream or permission to redistribute audio. This project does not rip or convert YouTube videos. For native Telegram playback of searched tracks, connect a licensed/authorized music catalogue or provide audio files you have rights to distribute. The bot can already relay audio files users send it.

## Hosting
GitHub stores the source; it does not keep a polling bot running. Deploy as a persistent Python worker on a host that supports background processes, and add the environment variables in that host's secrets/settings panel.
