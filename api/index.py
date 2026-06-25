import os
import logging

from fastapi import FastAPI, Request

from config import BOT_TOKEN, CHAT_USERNAME, SPAM_CONFIDENCE_THRESHOLD, GROQ_API_KEY
from spam_detector import init_client, is_spam
from src.telegram import delete_message, ban_chat_member, get_chat, send_message, set_webhook
from src.admin import is_admin, parse_command, get_help_text, stats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vercel")

app = FastAPI(docs_url=None, redoc_url=None)
_resolved_chat_id = None

if GROQ_API_KEY:
    init_client(GROQ_API_KEY)

TARGET_USERNAME = CHAT_USERNAME.lstrip("@").lower()


async def reply(bot_token: str, chat_id: int, text: str):
    await send_message(bot_token, chat_id, text)


async def handle_admin_command(text: str, username: str, chat_id: int):
    cmd_type, params = parse_command(text)

    if cmd_type is None:
        await reply(BOT_TOKEN, chat_id, "Unknown command. Send /help")
        return

    if cmd_type == "start":
        await reply(BOT_TOKEN, chat_id, f"Welcome admin @{username}!\n\n{get_help_text()}")

    elif cmd_type == "help":
        await reply(BOT_TOKEN, chat_id, get_help_text())

    elif cmd_type == "stats":
        await reply(BOT_TOKEN, chat_id, stats.to_text())

    elif cmd_type == "setinterval":
        interval = params["interval"]
        stats.check_interval_minutes = interval
        await reply(BOT_TOKEN, chat_id, f"Check interval set to {interval} minutes")

    elif cmd_type == "error":
        await reply(BOT_TOKEN, chat_id, params["msg"])


@app.post("/webhook")
async def handle_webhook(request: Request):
    global _resolved_chat_id

    try:
        update = await request.json()
    except Exception:
        return {"ok": False}

    message = update.get("message") or update.get("edited_message")
    if not message:
        return {"ok": True}

    chat = message.get("chat", {})
    chat_type = chat.get("type")
    chat_id = chat.get("id")
    chat_username = chat.get("username", "").lower()
    text = message.get("text") or message.get("caption", "")

    if not chat_id or not text:
        return {"ok": True}

    # Handle private admin commands
    if chat_type == "private":
        sender = message.get("from", {})
        sender_username = sender.get("username", "")
        if is_admin(sender_username):
            await handle_admin_command(text, sender_username, chat_id)
        return {"ok": True}

    # Handle group messages
    if chat_username != TARGET_USERNAME:
        return {"ok": True}

    if _resolved_chat_id is None:
        _resolved_chat_id = chat_id

    is_spam_flag, reason, confidence = await is_spam(text)

    if is_spam_flag and confidence >= SPAM_CONFIDENCE_THRESHOLD:
        message_id = message["message_id"]
        user_id = message["from"]["id"]

        await delete_message(BOT_TOKEN, chat_id, message_id)
        stats.record_delete()
        logger.info(f"Deleted {message_id} from {user_id}: {reason} ({confidence:.2f})")

        await ban_chat_member(BOT_TOKEN, chat_id, user_id)
        stats.record_ban(user_id)
        logger.info(f"Banned {user_id}: {reason}")

    return {"ok": True}


@app.get("/cron")
async def cron_check():
    chat = await get_chat(BOT_TOKEN, CHAT_USERNAME)
    chat_id = chat.get("id")
    if chat_id:
        await send_message(
            BOT_TOKEN, chat_id,
            f"Periodic check completed | Interval: {stats.check_interval_minutes}min"
        )
    return {"ok": True, "interval": stats.check_interval_minutes}


@app.get("/setup")
async def setup(request: Request):
    public_url = str(request.base_url).rstrip("/")
    webhook_url = f"{public_url}/webhook"

    wh = await set_webhook(BOT_TOKEN, webhook_url)
    logger.info(f"Webhook set: {wh}")

    chat = await get_chat(BOT_TOKEN, CHAT_USERNAME)
    chat_id = chat.get("id")

    return {
        "webhook": wh.get("description", "OK"),
        "chat": CHAT_USERNAME,
        "chat_id": chat_id,
        "admins": ["@Dilshod_Eshmurodov", "@cesicu"],
        "note": "Send /start to bot in private chat for admin panel"
    }


@app.get("/")
async def root():
    return {
        "status": "running",
        "chat": CHAT_USERNAME,
        "admins": ["@Dilshod_Eshmurodov", "@cesicu"],
        "endpoints": {
            "POST /webhook": "Telegram webhook",
            "GET /setup": "Configure webhook",
            "GET /cron": "Periodic check"
        }
    }
