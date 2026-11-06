import asyncio
import logging
import os
import secrets
from html import escape
from pathlib import Path
from urllib.parse import quote
from hmac import compare_digest

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    Update,
    WebAppInfo,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()
PORT = int(os.getenv("PORT", "10000"))
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip() or secrets.token_urlsafe(32)
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/search"
WEBAPP_URL = f"{RENDER_EXTERNAL_URL}/app" if RENDER_EXTERNAL_URL else ""
WEBAPP_HTML = Path(__file__).with_name("webapp.html")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("telegram-music-bot")

dp = Dispatcher()
bot = (
    Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    if BOT_TOKEN
    else None
)


def youtube_results_keyboard(query: str) -> InlineKeyboardMarkup | None:
    if not WEBAPP_URL:
        return None
    app_url = f"{WEBAPP_URL}?q={quote(query)}"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🎧 Sonuçları Telegram müzik ekranında aç",
            web_app=WebAppInfo(url=app_url),
        )
    ]])


async def search_youtube(query: str) -> list[dict]:
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "videoCategoryId": "10",
        "maxResults": 5,
        "key": YOUTUBE_API_KEY,
    }
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(YOUTUBE_API_URL, params=params) as response:
            payload = await response.json()
            if response.status != 200:
                reason = (
                    payload.get("error", {}).get("message", "YouTube API request failed")
                )
                raise RuntimeError(reason)
            return payload.get("items", [])


@dp.message(CommandStart())
async def start(message: Message) -> None:
    keyboard = None
    if WEBAPP_URL:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🎧 Müzik oynatıcıyı aç", web_app=WebAppInfo(url=WEBAPP_URL))
        ]])
    await message.answer(
        "🎧 <b>Music Bot'a hoş geldin!</b>\n\n"
        "Bir şarkı bulmak için:\n"
        "<code>/search şarkı adı - sanatçı</code>\n\n"
        "YouTube sonuçlarını listelerim. Bana gönderdiğin ses "
        "dosyalarını da Telegram müzik formatında geri gönderebilirim.",
        reply_markup=keyboard,
    )


@dp.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "<b>Kullanım</b>\n"
        "• <code>/search şarkı adı</code> — YouTube'da ara\n"
        "• Bana bir ses dosyası gönder — Telegram audio olarak geri al\n\n"
        "Not: YouTube Data API arama ve video bilgisi sağlar; "
        "video sesini indirme/MP3'e dönüştürme hizmeti değildir."
    )


@dp.message(Command("search"))
async def search_command(message: Message) -> None:
    query = (message.text or "").partition(" ")[2].strip()
    if not query:
        await message.answer("Aranacak şarkıyı yaz: <code>/search şarkı adı</code>")
        return

    if not YOUTUBE_API_KEY:
        await message.answer(
            "YouTube API anahtarı henüz ayarlanmamış. "
            "Render ortamına <code>YOUTUBE_API_KEY</code> değişkenini ekle."
        )
        return

    status = await message.answer("🔎 Şarkı aranıyor...")
    try:
        items = await search_youtube(query)
        if not items:
            await status.edit_text("Bu aramayla eşleşen sonuç bulamadım.")
            return

        lines = ["<b>Bulduğum sonuçlar:</b>"]
        for index, item in enumerate(items, start=1):
            snippet = item.get("snippet", {})
            title = escape(snippet.get("title", "Başlıksız"))
            channel = escape(snippet.get("channelTitle", ""))
            lines.append(f"{index}. <b>{title}</b>\n   <i>{channel}</i>")

        await status.edit_text(
            "\n\n".join(lines),
            reply_markup=youtube_results_keyboard(query),
            disable_web_page_preview=True,
        )
    except Exception as exc:
        log.exception("YouTube search failed")
        await status.edit_text(
            "Arama sırasında hata oluştu. API anahtarını ve YouTube "
            "Data API v3 erişimini kontrol et.\n\n"
            f"<code>{escape(str(exc)[:500])}</code>"
        )


@dp.message(F.audio)
async def received_audio(message: Message, bot: Bot) -> None:
    await bot.send_audio(
        chat_id=message.chat.id,
        audio=message.audio.file_id,
        caption="🎵 Gönderdiğin ses dosyası",
    )


@dp.message(F.document)
async def received_document(message: Message, bot: Bot) -> None:
    document = message.document
    mime = (document.mime_type or "").lower()
    name = (document.file_name or "").lower()
    if mime.startswith("audio/") or name.endswith(
        (".mp3", ".m4a", ".ogg", ".flac", ".wav")
    ):
        await bot.send_audio(
            chat_id=message.chat.id,
            audio=document.file_id,
            caption="🎵 Gönderdiğin ses dosyası",
        )


async def mini_app(_: web.Request) -> web.Response:
    if not WEBAPP_HTML.exists():
        return web.Response(text="Mini App dosyası bulunamadı.", status=404)
    return web.FileResponse(WEBAPP_HTML)


async def api_search(request: web.Request) -> web.Response:
    query = (request.query.get("q") or "").strip()[:150]
    if not query:
        return web.json_response({"items": []})
    if not YOUTUBE_API_KEY:
        return web.json_response({"error": "YouTube API anahtarı ayarlanmamış."}, status=503)
    try:
        items = await search_youtube(query)
        results = []
        for item in items:
            video_id = item.get("id", {}).get("videoId")
            snippet = item.get("snippet", {})
            if not video_id:
                continue
            thumbs = snippet.get("thumbnails", {})
            thumbnail = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
            results.append({
                "id": video_id,
                "title": snippet.get("title", "Başlıksız"),
                "artist": snippet.get("channelTitle", ""),
                "thumbnail": thumbnail,
            })
        return web.json_response({"items": results})
    except Exception as exc:
        log.exception("Mini App YouTube search failed")
        return web.json_response({"error": str(exc)[:300]}, status=502)


async def health(_: web.Request) -> web.Response:
    return web.json_response(
        {"status": "ok", "bot_configured": bot is not None, "mode": "webhook"}
    )


async def telegram_webhook(request: web.Request) -> web.Response:
    if bot is None:
        return web.json_response({"error": "BOT_TOKEN is not configured"}, status=503)

    supplied_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not compare_digest(supplied_secret, WEBHOOK_SECRET):
        return web.Response(status=403, text="Forbidden")

    try:
        update = Update.model_validate(await request.json(), context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception:
        log.exception("Failed to process Telegram update")
        return web.Response(status=500, text="Update processing failed")

    return web.Response(text="OK")


async def on_startup(_: web.Application) -> None:
    if bot is None:
        log.error("BOT_TOKEN is missing. Add it in Render Environment settings.")
        return
    if not RENDER_EXTERNAL_URL:
        log.error("RENDER_EXTERNAL_URL is missing; Telegram webhook was not registered.")
        return

    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook/{WEBHOOK_SECRET}"
    await bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET,
        allowed_updates=dp.resolve_used_update_types(),
        drop_pending_updates=False,
    )
    log.info("Telegram webhook registered: %s", RENDER_EXTERNAL_URL)


async def on_shutdown(_: web.Application) -> None:
    if bot is not None:
        await bot.session.close()


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    app.router.add_get("/app", mini_app)
    app.router.add_get("/api/search", api_search)
    app.router.add_post(f"/webhook/{WEBHOOK_SECRET}", telegram_webhook)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=PORT)
