"""
AYY-34 — Django settings for the AYY POS store box.

Integrates all spike codebases + new ayypos backend apps
into a single production-ready Django project.

Environment variable overrides:
  DJANGO_ENV=store     — store box mode (Postgres + Redis)
  DJANGO_ENV=test      — test mode (SQLite)
"""
import os
from pathlib import Path

# ── Base ──
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-store-box-dev-key-not-for-production",
)
DEBUG = os.getenv("DJANGO_ENV", "store") != "store"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

# ── Installed apps ──
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "django_celery_beat",
    # Spike apps (production)
    "sync_core",
    "irp_client",
    "tally_client",
    "till",
    "licence_server",
    "hoc",
    # AYY-34 new backend apps
    "ayypos.backend.catalogue",
    "ayypos.backend.billing",
    "ayypos.backend.inventory",
    "ayypos.backend.sync",
    "ayypos.backend.irp",
    "ayypos.backend.tally",
    "ayypos.backend.licence",
    "ayypos.backend.customers",
    "ayypos.backend.reporting",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ayypos.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "ayypos.wsgi.application"

# ── Database ──
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
_DATABASE_URL = os.getenv("DATABASE_URL")
if _DATABASE_URL:
    try:
        import dj_database_url
        DATABASES["default"] = dj_database_url.parse(_DATABASE_URL)
    except ModuleNotFoundError:
        pass

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Sessions ──
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# ── Store identity ──
STORE_ID = os.getenv("STORE_ID", "store-0001")
STORE_GSTIN_STATE = os.getenv("STORE_GSTIN_STATE", "29")

# ── Celery ──
CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Kolkata"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BEAT_SCHEDULE = {
    "export-daily-tally": {
        "task": "ayypos.backend.tally.tasks.export_daily_tally_vouchers",
        "schedule": 86340,
        "args": (STORE_ID,),
    },
}

# ── REST Framework ──
REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
}

# ── Static / Media ──
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "/home/ubuntu/ayypos-data/media"))

# ── Internationalization ──
LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ── Licence ──
LICENCE_SECRET_KEY = os.getenv("LICENCE_SECRET_KEY", "store-box-dev-licence-secret")

# ── Cloud sync ──
CLOUD_API_URL = os.getenv("CLOUD_API_URL", "")
