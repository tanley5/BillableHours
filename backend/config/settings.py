from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "unsafe-dev-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "tracker",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "NAME": os.environ.get("POSTGRES_DB", "billable"),
        "USER": os.environ.get("POSTGRES_USER", "billable"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "billable"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "tracker.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "contractor": "120/min",
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Billable Hours Tracker API",
    "DESCRIPTION": "Single-tenant contractor billable hours tracker (local Docker).",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

CORS_ALLOWED_ORIGINS = [
    "http://localhost",
    "http://127.0.0.1",
]
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost",
    "http://127.0.0.1",
]

CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"

# Photo constraints
PHOTO_MAX_BYTES = 5 * 1024 * 1024
PHOTO_MAX_PER_KIND = 10
PHOTO_MAX_DIMENSION = 1920
VISIT_MAX_HOURS = 16

# n8n notifications (empty disables delivery)
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "")
N8N_WEBHOOK_TIMEOUT = float(os.environ.get("N8N_WEBHOOK_TIMEOUT", "3"))

# Public app origin (invite / Connect return URLs)
APP_ORIGIN = os.environ.get("APP_ORIGIN", "http://localhost")
PASSWORD_INVITE_TTL_DAYS = int(os.environ.get("PASSWORD_INVITE_TTL_DAYS", "7"))

# Stripe Connect Express (set STRIPE_API_BASE to stripe-sim for local demos)
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_API_BASE = os.environ.get("STRIPE_API_BASE", "").rstrip("/")
STRIPE_CONNECT_RETURN_URL = os.environ.get(
    "STRIPE_CONNECT_RETURN_URL", f"{APP_ORIGIN}/contractor/connect/return"
)
STRIPE_CONNECT_REFRESH_URL = os.environ.get(
    "STRIPE_CONNECT_REFRESH_URL", f"{APP_ORIGIN}/contractor/connect/refresh"
)
ESCROW_HOLD_DAYS = int(os.environ.get("ESCROW_HOLD_DAYS", "7"))
ESCROW_EXPIRY_WARNING_HOURS = int(os.environ.get("ESCROW_EXPIRY_WARNING_HOURS", "24"))
REMINDER_ASSIGNMENT_INVITE_HOURS = int(os.environ.get("REMINDER_ASSIGNMENT_INVITE_HOURS", "24"))
REMINDER_IN_ROUTE_HOURS = int(os.environ.get("REMINDER_IN_ROUTE_HOURS", "4"))
REMINDER_SUBJOB_PENDING_HOURS = int(os.environ.get("REMINDER_SUBJOB_PENDING_HOURS", "24"))
REMINDER_SUBMISSION_REVIEW_HOURS = int(os.environ.get("REMINDER_SUBMISSION_REVIEW_HOURS", "24"))
REMINDER_PROJECT_FROZEN_HOURS = int(os.environ.get("REMINDER_PROJECT_FROZEN_HOURS", "24"))
