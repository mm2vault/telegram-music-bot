import asyncio
import logging
import os
from html import escape

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.client.default import DefaultBotProperties

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/search"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("telegram-music-bot")

dp = Dispatcher()


def youtube_results_keyboard(items: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for item in items:
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        title = snippet.get("title", "Untitled")
        if not video_id:
            continue
        rows.append([
            InlineKeyboardButton(
                text=f"▶ {title[:55]}",
                url=f"https://www.youtube.com/watch?v={video_id}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
                    payload.get("error", {})
                    .get("message", "YouTube API request failed")
                )
                raise RuntimeError(reason)
            return payload.get("items", [])


@dp.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "🎧 <b>Music Bot'a hoş geldin!</b>\n\n"
        "Bir şarkı bulmak için:\n"
        "<code>/search şarkı adı - sanatçı</code>\n\n"
        "YouTube sonuçlarını listelerim. Bana gönderdiğin ses "
        "dosyalarını da Telegram müzik formatında geri gönderebilirim."
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
            "GitHub/hosting ortamına <code>YOUTUBE_API_KEY</code> değişkenini ekle."
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
            reply_markup=youtube_results_keyboard(items),
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
    audio = message.audio
    await bot.send_audio(
        chat_id=message.chat.id,
        audio=audio.file_id,
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


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is required")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    log.info("Bot is starting")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
