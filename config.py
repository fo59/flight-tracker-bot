import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

OPENSKY_USERNAME = os.getenv("OPENSKY_USERNAME") or None
OPENSKY_PASSWORD = os.getenv("OPENSKY_PASSWORD") or None

AVIATIONSTACK_API_KEY = os.getenv("AVIATIONSTACK_API_KEY") or None

AIRLABS_API_KEY = os.getenv("AIRLABS_API_KEY") or None

CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "300"))
LANDING_THRESHOLD_MINUTES = int(os.getenv("LANDING_THRESHOLD_MINUTES", "30"))
DELAY_THRESHOLD_MINUTES = int(os.getenv("DELAY_THRESHOLD_MINUTES", "45"))
AIRLABS_COOLDOWN_SECONDS = int(os.getenv("AIRLABS_COOLDOWN_SECONDS", "2700"))

DB_PATH = os.getenv("DB_PATH", "flights.db")
AIRPORTS_CACHE_PATH = os.getenv("AIRPORTS_CACHE_PATH", "airports_cache.json")
AIRPORTS_DATA_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"

PORT = os.getenv("PORT")

OWNER_ID = int(os.getenv("OWNER_ID", "0")) or None

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN ortam degiskeni bulunamadi."
    )
