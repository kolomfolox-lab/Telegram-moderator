from datetime import datetime
from config import ADMIN_USERNAMES as _CONFIG_ADMINS


class BotStats:
    def __init__(self):
        self.total_deleted = 0
        self.total_banned = 0
        self.check_interval_minutes = 7
        self.started_at = datetime.now()
        self.last_banned_user = None
        self.last_deleted_at = None

    def record_delete(self):
        self.total_deleted += 1
        self.last_deleted_at = datetime.now()

    def record_ban(self, user_id=None):
        self.total_banned += 1
        self.last_banned_user = user_id

    def to_text(self) -> str:
        runtime = datetime.now() - self.started_at
        hours = int(runtime.total_seconds() // 3600)
        minutes = int((runtime.total_seconds() % 3600) // 60)
        return (
            f"🤖 Admin Panel\n"
            f"━━━━━━━━━━━━━━\n"
            f"🗑 Deleted: {self.total_deleted}\n"
            f"🔨 Banned: {self.total_banned}\n"
            f"⏱ Interval: {self.check_interval_minutes} min\n"
            f"🕐 Uptime: {hours}h {minutes}m"
        )


stats = BotStats()


def is_admin(username: str) -> bool:
    if not username:
        return False
    return username.lower() in [u.lower() for u in _CONFIG_ADMINS]


def parse_command(text: str) -> tuple:
    cmd = text.strip().split()
    if not cmd:
        return None, {}

    command = cmd[0].lower()

    if command == "/start":
        return "start", {}
    elif command == "/stats":
        return "stats", {}
    elif command == "/setinterval" and len(cmd) >= 2:
        try:
            interval = int(cmd[1])
            if 1 <= interval <= 60:
                return "setinterval", {"interval": interval}
        except ValueError:
            pass
        return "error", {"msg": "Usage: /setinterval <minutes> (1-60)"}
    elif command == "/help":
        return "help", {}
    elif command == "/banlist":
        return "banlist", {}

    return None, {}


def get_help_text() -> str:
    admins = ", ".join(f"@{a}" for a in _CONFIG_ADMINS)
    return (
        "🔐 Admin Commands\n"
        "━━━━━━━━━━━━━━\n"
        "/stats — View statistics\n"
        "/setinterval N — Change check interval (1-60 min)\n"
        "/help — Show this help\n"
        "━━━━━━━━━━━━━━\n"
        f"Admins: {admins}"
    )
