import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "event.db"

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

ID_WIDTH = 3
ROLE_NONE = "none"
ROLE_RECEPTION = "reception"
ROLE_STAND = "stand"
ROLE_ADMIN = "admin"

ROLE_LABELS = {
    ROLE_NONE: "нет доступа",
    ROLE_RECEPTION: "ресепшен",
    ROLE_STAND: "стенд",
    ROLE_ADMIN: "админ",
}
