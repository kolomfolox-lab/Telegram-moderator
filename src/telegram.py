import httpx

API_BASE = "https://api.telegram.org/bot"


async def _call(method: str, token: str, **kwargs):
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(f"{API_BASE}{token}/{method}", json=kwargs)
        return r.json()


async def delete_message(token: str, chat_id: int, message_id: int):
    return await _call("deleteMessage", token, chat_id=chat_id, message_id=message_id)


async def ban_chat_member(token: str, chat_id: int, user_id: int):
    r = await _call("banChatMember", token, chat_id=chat_id, user_id=user_id)
    return r.get("ok", False)


async def get_chat(token: str, chat_id_or_username: str) -> dict:
    r = await _call("getChat", token, chat_id=chat_id_or_username)
    return r.get("result", {})


async def set_webhook(token: str, url: str):
    return await _call(
        "setWebhook", token,
        url=url,
        allowed_updates=["message", "edited_message"]
    )


async def send_message(token: str, chat_id: int, text: str):
    return await _call("sendMessage", token, chat_id=chat_id, text=text)
