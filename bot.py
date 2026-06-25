import logging
from collections import deque
from datetime import datetime, timedelta

from telegram import ChatMemberAdministrator
from telegram.ext import Application, MessageHandler, filters, CommandHandler
from telegram.error import TelegramError

from config import (
    BOT_TOKEN, GROQ_API_KEY, CHAT_USERNAME,
    CHECK_INTERVAL_MINUTES, GROQ_MODEL, SPAM_CONFIDENCE_THRESHOLD
)
from spam_detector import is_spam, init_client
from src.admin import is_admin, parse_command, get_help_text, stats

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

target_chat_id = None
recent_messages = deque(maxlen=500)
checked_ids = set()


async def check_and_act(message, context):
    if not message.text and not message.caption:
        return False

    text = message.text or message.caption
    is_spam_flag, reason, confidence = await is_spam(text)

    if is_spam_flag and confidence >= SPAM_CONFIDENCE_THRESHOLD:
        chat_id = message.chat_id
        user_id = message.from_user.id if message.from_user else None

        try:
            await message.delete()
            stats.record_delete()
            logger.info(f"Deleted (conf={confidence:.2f}): {reason}")

            if user_id:
                try:
                    await context.bot.ban_chat_member(chat_id, user_id)
                    stats.record_ban(user_id)
                    logger.info(f"Banned {user_id}: {reason}")
                except TelegramError as e:
                    if "user is an administrator" in str(e).lower():
                        logger.warning(f"Cannot ban admin {user_id}")
                    else:
                        raise
            return True
        except TelegramError as e:
            logger.warning(f"Delete/ban error: {e}")

    return False


async def handle_message(update, context):
    global target_chat_id

    message = update.message or update.edited_message
    if not message:
        return

    chat = message.chat
    user = message.from_user

    # Handle private admin commands
    if chat.type == "private" and user:
        username = user.username
        if is_admin(username) and message.text:
            cmd_type, params = parse_command(message.text)
            if cmd_type == "start":
                await message.reply_text(f"Welcome admin @{username}!\n\n{get_help_text()}")
            elif cmd_type == "help":
                await message.reply_text(get_help_text())
            elif cmd_type == "stats":
                await message.reply_text(stats.to_text())
            elif cmd_type == "setinterval":
                interval = params["interval"]
                stats.check_interval_minutes = interval
                await message.reply_text(f"Interval set to {interval} minutes")
            elif cmd_type == "error":
                await message.reply_text(params["msg"])
            else:
                await message.reply_text("Unknown command. Send /help")
        return

    # Handle group messages
    if target_chat_id and chat.id != target_chat_id:
        return

    if target_chat_id is None:
        target_chat_id = chat.id

    if message.message_id not in checked_ids:
        recent_messages.append(message)

    await check_and_act(message, context)


async def periodic_check(context):
    global target_chat_id

    if not target_chat_id:
        logger.info("Chat not set yet, skipping periodic check")
        return

    now = datetime.now()
    checked = 0
    banned = 0

    for msg in list(recent_messages):
        if msg.message_id in checked_ids:
            continue

        created = msg.date.replace(tzinfo=None) if msg.date else None
        if created and (now - created) > timedelta(hours=6):
            checked_ids.add(msg.message_id)
            continue

        result = await check_and_act(msg, context)
        if result:
            banned += 1
        checked_ids.add(msg.message_id)
        checked += 1

    logger.info(f"Periodic check: {checked} msgs, {banned} banned")
    if banned > 0:
        try:
            await context.bot.send_message(
                target_chat_id,
                f"Periodic check: {banned} spammers banned"
            )
        except TelegramError:
            pass


async def start(update, context):
    await update.message.reply_text(
        f"Moderator Bot Active\n\n"
        f"Chat: {CHAT_USERNAME}\n"
        f"Check interval: {stats.check_interval_minutes} min\n"
        f"GROQ model: {GROQ_MODEL}\n"
        f"Confidence threshold: {SPAM_CONFIDENCE_THRESHOLD}\n\n"
        f"Add bot as admin with delete & ban permissions."
    )


async def verify_bot_admin(app):
    global target_chat_id

    try:
        bot = app.bot
        chat = await bot.get_chat(CHAT_USERNAME)
        target_chat_id = chat.id
        logger.info(f"Found chat: {CHAT_USERNAME} (ID: {chat.id})")

        bot_member = await chat.get_member(bot.id)
        if not isinstance(bot_member, ChatMemberAdministrator):
            logger.warning(
                f"Bot is NOT admin in {CHAT_USERNAME}!\n"
                "Add bot as admin with: delete messages, ban users"
            )
        else:
            logger.info(f"Bot IS admin in {CHAT_USERNAME}")

        return chat.id
    except TelegramError as e:
        logger.error(f"Cannot find chat {CHAT_USERNAME}: {e}")
        logger.error(
            "Make sure:\n"
            "1. Chat exists\n"
            "2. Bot is added to chat\n"
            "3. Token is correct"
        )
        return None


async def post_init(app):
    global target_chat_id
    await verify_bot_admin(app)

    if target_chat_id:
        logger.info(f"Bot started. Monitoring: {CHAT_USERNAME}")
    else:
        logger.warning(f"Bot started but chat not found. Add bot to {CHAT_USERNAME} as admin.")


def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is missing! Create .env file from .env.example")
        return

    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY is missing! Create .env file from .env.example")
        return

    init_client(GROQ_API_KEY)

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND,
        handle_message
    ))

    app.job_queue.run_repeating(
        periodic_check,
        interval=stats.check_interval_minutes * 60,
        first=30
    )

    app.run_polling(allowed_updates=["message", "edited_message"])


if __name__ == "__main__":
    main()
