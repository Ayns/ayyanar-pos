from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent

# Ensure storebox (hoc app) is on Python path
_STOREBOX = BASE_DIR.parent / "storebox"
if _STOREBOX.exists() and str(_STOREBOX) not in sys.path:
    sys.path.insert(0, str(_STOREBOX))

SECRET_KEY = "spike-not-a-secret"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "sync_core",
    "hoc",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
