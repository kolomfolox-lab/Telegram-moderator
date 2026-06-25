import os
import logging

from fastapi import FastAPI, Request

from config import BOT_TOKEN, CHAT_USERNAME, SPAM_CONFIDENCE_THRESHOLD, GROQ_API_KEY
from spam_detector import init_client, is_spam
from src.telegram import delete_message, ban_chat_member, get_chat, send_message, set_webhook

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vercel")

app = FastAPI(docs_url=None, redoc_url=None)
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID")

if GROQ_API_KEY:
    init_client(GROQ_API_KEY)


def _is_target_chat(chat_id) -> bool:
    if not TARGET_CHAT_ID:
        return True
    return str(chat_id) == str(TARGET_CHAT_ID)


@app.post("/webhook")
async def handle_webhook(request: Request):
    try:
        update = await request.json()
    except Exception:
        return {"ok": False}

    message = update.get("message") or update.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id = message.get("chat", {}).get("id")
    text = message.get("text") or message.get("caption", "")

    if not chat_id or not text:
        return {"ok": True}

    if not _is_target_chat(chat_id):
        return {"ok": True}

    is_spam_flag, reason, confidence = await is_spam(text)

    if is_spam_flag and confidence >= SPAM_CONFIDENCE_THRESHOLD:
        message_id = message["message_id"]
        user_id = message["from"]["id"]

        await delete_message(BOT_TOKEN, chat_id, message_id)
        logger.info(f"Deleted {message_id} from {user_id}: {reason} ({confidence:.2f})")

        await ban_chat_member(BOT_TOKEN, chat_id, user_id)
        logger.info(f"Banned {user_id}: {reason}")

    return {"ok": True}


@app.get("/cron")
async def cron_check():
    if TARGET_CHAT_ID:
        await send_message(
            BOT_TOKEN, int(TARGET_CHAT_ID),
            "Periodic check completed"
        )
    return {"ok": True}


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
        "note": f"Add TARGET_CHAT_ID={chat_id} to Vercel env vars for chat filtering"
    }


@app.get("/")
async def root():
    return {
        "status": "running",
        "chat": CHAT_USERNAME,
        "endpoints": {
            "POST /webhook": "Telegram webhook",
            "GET /setup": "Configure webhook",
            "GET /cron": "Periodic check"
        }
    }
