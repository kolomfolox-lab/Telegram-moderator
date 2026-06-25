import json
from groq import AsyncGroq

from config import GROQ_MODEL

client: AsyncGroq = None  # type: ignore

SPAM_SYSTEM_PROMPT = """Ты — агрессивный ИИ-детектор спама для Telegram-чата. Твоя задача — НЕ ПРОПУСТИТЬ НИ ОДНОГО спама. Лучше удалить обычное сообщение, чем пропустить спам.

Если есть ХОТЯ БЫ 1 признак спама — ставь is_spam=true:

1. ДЕНЬГИ: любые упоминания денег, сумм, цифр с пробелами, символами (ρ, ₽, $, €), заработок, доход, выплата, на карту
2. ВРЕМЯ: указание времени (за 8 часов, каждые 4 часа, через 6 часов)
3. ССЫЛКИ ТОЛЬКО: t.me/m/ и t.me/joinchat (никакие другие ссылки не считай спамом!)
4. ЗАМЕНА БУКВ: использование похожих символов (ρ/р, зᴀ/за, ʙ/в, κ/к, σ/о, ᴦ/г, ʍ/м, ᴧ/л, ᴨ/п, ᴘ/р, ᴛ/т, ᴜ/у, u/и, a/а, o/о, c/с, e/е, x/х)
5. ВОЗРАСТ: 18+, РФ 18+
6. ПРИЗЫВЫ: пиши, жми, переходи, нажми, заработай, получи
7. ЭМОДЗИ: 🔥 ⚡️ 💰 🚨 👇 💎 ✅ 💥 (только если есть и другие признаки)
8. ОБЕЩАНИЯ: быстрый заработок, пассивный доход, деньги на карту, лёгкие деньги
9. ФРАЗЫ: "твой день", "твой шанс", "не упусти"

НЕ СПАМ (никогда не удаляй):
- Обычные сообщения, вопросы, шутки
- Ссылки на YouTube, Instagram, TikTok, Twitter
- Любые обычные домены и ссылки (кроме t.me/m/ и t.me/joinchat)

ВАЖНО: Ссылка на YouTube или любой другой обычный сайт — это НЕ спам.

Ответь строго в формате JSON. ТОЛЬКО JSON:
{"is_spam": true/false, "reason": "краткая причина (2-5 слов)", "confidence": 0.0-1.0}"""


def init_client(api_key: str):
    global client
    client = AsyncGroq(api_key=api_key)


SPAM_KEYWORDS = [
    "заработ", "выплат", "деньг", "на карт", "доход", "крипт",
    "пиши", "жми", "переход", "18+", "за 8 час", "за 6 час", "за 4 час",
    "каждые 4", "каждые 6", "каждые 8", "через 6 час", "через 8 час",
    "8OO", "5OO", "9OO", "ρ",
    "t.me/m/",
]


async def is_spam(text: str) -> tuple:
    if not text or not text.strip():
        return False, "пустое", 0.0

    text_lower = text.lower()
    keyword_hits = sum(1 for kw in SPAM_KEYWORDS if kw in text_lower)

    if keyword_hits >= 3:
        return True, f"ключевые слова ({keyword_hits})", 0.95

    try:
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SPAM_SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0.1,
            max_tokens=150
        )

        content = response.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        result = json.loads(content)

        is_spam_flag = result.get("is_spam", False)
        reason = result.get("reason", "неизвестно")
        confidence = result.get("confidence", 0.0)

        if keyword_hits >= 1 and confidence > 0:
            confidence = max(confidence, 0.5)
            is_spam_flag = True

        return is_spam_flag, reason, confidence
    except json.JSONDecodeError:
        if keyword_hits >= 2:
            return True, "ключевые слова", 0.7
        return False, "ошибка парсинга", 0.0
    except Exception as e:
        if keyword_hits >= 2:
            return True, "ключевые слова", 0.7
        return False, f"ошибка: {str(e)}", 0.0
