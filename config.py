import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CHAT_USERNAME = os.getenv("CHAT_USERNAME", "@isitish_qozonlari")
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "7"))
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
SPAM_CONFIDENCE_THRESHOLD = float(os.getenv("SPAM_CONFIDENCE_THRESHOLD", "0.2"))
