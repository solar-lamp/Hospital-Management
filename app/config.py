"""Non-secret application configuration.

Every value can be overridden with an environment variable so the same code
runs locally (``streamlit run app.py``), in tests (temporary database) and in
the browser build hosted on GitHub Pages (database kept in IndexedDB).
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

APP_NAME = "MediTrack HMS"
APP_TITLE = "MediTrack: Hospital Management and Resource Tracking System"


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_db_path() -> Path:
    """Resolve the database path at call time so tests can override it."""
    return Path(os.environ.get("HMS_DB_PATH", BASE_DIR / "data" / "hospital.db"))


def get_backup_dir() -> Path:
    return Path(os.environ.get("HMS_BACKUP_DIR", get_db_path().parent / "backups"))


# Demo mode shows the fictional demo credentials on the login page and allows
# resetting the demo data. It is on for the public GitHub Pages build.
def demo_mode() -> bool:
    return _env_bool("HMS_DEMO_MODE", False)


# When true and the database has no users, synthetic demo data is created on
# first start. Otherwise the app asks for a first administrator account.
def auto_seed_demo() -> bool:
    return _env_bool("HMS_AUTO_SEED_DEMO", False)


def pbkdf2_iterations() -> int:
    return int(os.environ.get("HMS_PBKDF2_ITERATIONS", "600000"))


# Business settings (documented in README "Metric definitions").
EXPIRY_WARNING_DAYS = 90          # batches expiring within N days (today inclusive)
SESSION_TIMEOUT_MINUTES = 480     # idle time before a user must log in again
DEFAULT_APPOINTMENT_MINUTES = 15
CURRENCY_SYMBOL = "₹"

# Timestamp policy: all timestamps are stored as local time text
# "YYYY-MM-DD HH:MM:SS" and dates as "YYYY-MM-DD". Lexical order == time order.
DATE_FORMAT = "%Y-%m-%d"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
