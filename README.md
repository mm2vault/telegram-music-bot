# Telegram Music Bot

Python + aiogram 3 Telegram bot, deployed in webhook mode.

## Features
- Search YouTube music videos with YouTube Data API v3.
- Show up to five results as Telegram buttons.
- Relay audio files sent by users as Telegram audio messages.
- Use Telegram webhooks instead of long polling for Render Web Service hosting.
- Expose `/health` for service health checks.

## Required Render environment variables
- `BOT_TOKEN` — token from @BotFather.
- `YOUTUBE_API_KEY` — YouTube Data API v3 key.

Render provides `PORT` and `RENDER_EXTERNAL_URL` automatically. The app generates a webhook secret at startup; optionally set `WEBHOOK_SECRET` yourself if you want a stable value.

Never commit real tokens or `.env` files. Add credentials in Render → your service → Environment.

## Run locally

```bash
pip install -r requirements.txt
export BOT_TOKEN="your-token"
export YOUTUBE_API_KEY="your-youtube-api-key"
export RENDER_EXTERNAL_URL="https://your-public-host.example"
python bot.py
```

## Commands
- `/start`
- `/help`
- `/search song name`

## Important audio limitation
YouTube Data API returns metadata and video links; it does not provide an audio stream or permission to redistribute audio. This project does not rip or convert YouTube videos. For native Telegram playback of searched tracks, connect a licensed/authorized music catalogue or provide audio files you have rights to distribute. The bot can relay audio files users send it.

## Render free plan note
A free Render web service may spin down after 15 minutes without inbound traffic. A Telegram webhook can wake it when an update arrives, but the first response may be delayed and this is not a guaranteed 24/7 service.
