import os
from datetime import timedelta
from pathlib import Path

from decouple import config as _default_config, Config, RepositoryEnv, Csv

if dotenv_file := os.environ.get("DOTENV_FILE"):
    config = Config(RepositoryEnv(dotenv_file))
else:
    config = _default_config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("WS_SECRET_KEY")
DEBUG = True

ALLOWED_HOSTS = config("WS_ALLOWED_HOSTS", cast=Csv(), default="localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "allauth",
    "allauth.account",
    "allauth.headless",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "anymail",
    "channels",
    "django_extensions",
    "django_rq",
    "hijack",
    "hijack.contrib.admin",
    "ask",
    "core",
    "collab",
    "pages.apps.PagesConfig",
    "users",
]

AUTH_USER_MODEL = "users.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

MIDDLEWARE = [
    "core.middlewares.RequestIDMiddleware",  # Must be first to capture all requests
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middlewares.RestrictAuthMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "hijack.middleware.HijackUserMiddleware",
]

# Hyperclast settings (moved up for use in other settings)
WS_ROOT_URL = config("WS_ROOT_URL", default="http://localhost:9800")

FRONTEND_URL = WS_ROOT_URL

# CSRF trusted origins - set via WS_CSRF_TRUSTED_ORIGINS env var
# Should match WS_ROOT_URL (e.g., http://localhost:9800)
CSRF_TRUSTED_ORIGINS = config(
    "WS_CSRF_TRUSTED_ORIGINS",
    cast=Csv(),
    default="",
)

# CSRF settings for same-origin setup
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

ROOT_URLCONF = "backend.urls"

# CORS
CORS_ALLOWED_ORIGINS = []
CORS_ALLOW_CREDENTIALS = True  # Required for session-based auth with cross-origin requests
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-password-reset-key",  # Custom header for password reset
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.branding",
            ],
        },
    },
]

WSGI_APPLICATION = "backend.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("WS_DB_NAME"),
        "USER": config("WS_DB_USER"),
        "PASSWORD": config("WS_DB_PASSWORD"),
        "HOST": config("WS_DB_HOST"),
        "PORT": config("WS_DB_PORT"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "static"

# Additional static file directories (outside of app static/ folders)
# In dev, serve frontend assets directly from the build directory.
# In prod, assets are copied to static/core/spa/assets/ before deployment.
_frontend_assets = BASE_DIR.parent / "frontend" / "dist" / "assets"
STATICFILES_DIRS = [("core/spa/assets", _frontend_assets)] if _frontend_assets.exists() else []

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# WhiteNoise storage - use CompressedStaticFilesStorage (not Manifest version)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# allauth

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
ACCOUNT_SIGNUP_AUTO_LOGIN = True
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_EMAIL_SUBJECT_PREFIX = ""
ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False
ACCOUNT_MAX_EMAIL_ADDRESSES = 1
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_ADAPTER = "users.adapters.CustomAccountAdapter"
ACCOUNT_FORMS = {
    "signup": "users.forms.UserSignupForm",
}

SOCIALACCOUNT_ADAPTER = "users.adapters.CustomSocialAccountAdapter"
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": [
            "profile",
            "email",
        ],
        "AUTH_PARAMS": {
            "access_type": "online",
        },
        "APP": {
            "client_id": config("WS_GOOGLE_SIGNIN_CLIENT_ID", default=None),
            "secret": config("WS_GOOGLE_SIGNIN_SECRET_KEY", default=None),
        },
    }
}

# headless allauth
HEADLESS_ADAPTER = "users.adapters.CustomHeadlessAdapter"
HEADLESS_ONLY = True
HEADLESS_CLIENTS = ["browser"]
HEADLESS_FRONTEND_URLS = {
    "account_reset_password_from_key": f"{FRONTEND_URL}/reset-password?key={{key}}",
}

# Hyperclast settings (continued)
WS_DEPLOYMENT_ID = config("WS_DEPLOYMENT_ID", "_local")
WS_EXTERNAL_API_MAX_RETRIES = 5
WS_EXTERNAL_API_BASE_WAIT_SECONDS = 2
WS_EXTERNAL_API_TIMEOUT_SECONDS = 30
WS_DEFAULT_PAGE_SIZE = 25
WS_ENCRYPTION_KEY = config("WS_ENCRYPTION_KEY", default=None)


# Alerts and logging

WS_SENTRY_DSN = config("WS_SENTRY_DSN", default=None)

LOG_FILE = config("WS_LOG_FILE", default="/var/log/gunicorn/ws.log")
LOG_LEVEL = config("WS_LOG_LEVEL", default="INFO")

# Stripe
STRIPE_API_PUBLIC_KEY = config("WS_STRIPE_API_PUBLIC_KEY", default=None)
STRIPE_API_SECRET_KEY = config("WS_STRIPE_API_SECRET_KEY", default=None)
STRIPE_ENDPOINT_SECRET = config("WS_STRIPE_ENDPOINT_SECRET", default=None)
STRIPE_PRO_PRICE_ID = config("WS_STRIPE_PRO_PRICE_ID", default=None)


# Redis

REDIS_HOST = config("WS_REDIS_HOST", default="localhost")
REDIS_PORT = config("WS_REDIS_PORT", default=6379, cast=int)
REDIS_DB_NUMBER = config("WS_REDIS_DB_NUMBER", default=1, cast=int)

# Queues
COMMON_RQ_SETTINGS = {
    "HOST": REDIS_HOST,
    "PORT": REDIS_PORT,
    "DB": REDIS_DB_NUMBER,  # use unique db to avoid conflicts with other apps
    "DEFAULT_TIMEOUT": 360,
}
JOB_INTERNAL_QUEUE = "internal"
JOB_EMAIL_QUEUE = "email"
JOB_AI_QUEUE = "ai"

RQ_QUEUES = {
    JOB_INTERNAL_QUEUE: COMMON_RQ_SETTINGS,
    JOB_EMAIL_QUEUE: COMMON_RQ_SETTINGS,
    JOB_AI_QUEUE: COMMON_RQ_SETTINGS,
}

JOB_RUNNER = config("WS_JOB_RUNNER", default=None)


# Email

EMAIL_BACKENDS_MAP = {
    "console": "django.core.mail.backends.console.EmailBackend",
    "postmark": "anymail.backends.postmark.EmailBackend",
    "test": "anymail.backends.test.EmailBackend",
    "local": "anymail.backends.console.EmailBackend",
}
EMAIL_BACKEND = EMAIL_BACKENDS_MAP[config("WS_EMAIL_BACKEND", default="console")]

ANYMAIL = {
    "POSTMARK_SERVER_TOKEN": config("WS_POSTMARK_SERVER_TOKEN", default=None),
    "WEBHOOK_SECRET": config("WS_EMAIL_WEBHOOK_SECRET", default=None),
}

DEFAULT_FROM_EMAIL = config("WS_DEFAULT_FROM_EMAIL", default="webmaster@localhost")
SERVER_EMAIL = config("WS_SERVER_EMAIL", default="server@localhost")

# CRDT, websockets, and channels
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(config("WS_REDIS_HOST", default="localhost"), int(config("WS_REDIS_PORT", default=6379)))],
        },
    },
}

ASGI_APPLICATION = "backend.asgi.application"

CRDT_SNAPSHOT_INTERVAL_SECONDS = 15  # Reduced from 60 for faster persistence
CRDT_SNAPSHOT_AFTER_EDIT_COUNT = 50  # Reduced from 100 for faster persistence

# WebSocket rate limiting (prevents DoS from rapid reconnection loops)
WS_RATE_LIMIT_CONNECTIONS = 30  # Max connections per window
WS_RATE_LIMIT_WINDOW_SECONDS = 60  # Window duration in seconds

# Page invitation
PAGE_INVITATION_TOKEN_BYTES = 32
PAGE_INVITATION_TOKEN_EXPIRES_IN = timedelta(days=7)
PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY = "pending_invitation_token"
PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY = "pending_invitation_email"

# Project invitation
PROJECT_INVITATION_TOKEN_BYTES = 32
PROJECT_INVITATION_TOKEN_EXPIRES_IN = timedelta(days=7)
PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY = "pending_project_invitation_token"
PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY = "pending_project_invitation_email"

# OpenaAI
OPENAI_API_KEY = config("WS_OPENAI_API_KEY", default=None)
OPENAI_DEFAULT_CHAT_MODEL = "gpt-4o"
OPENAI_DEFAULT_CHAT_MAX_TOKENS = 1500
OPENAI_DEFAULT_CHAT_TEMPERATURE = 0.3

# Ask feature
ASK_FEATURE_ENABLED = config("WS_ASK_FEATURE_ENABLED", cast=bool, default=False)
ASK_EMBEDDINGS_DEFAULT_MODEL = "text-embedding-3-small"
ASK_EMBEDDINGS_DEFAULT_ENCODING = "cl100k_base"
ASK_EMBEDDINGS_DEFAULT_MAX_INPUT = 8191
ASK_EMBEDDINGS_MAX_PAGES = 5

# Dev sidebar (shows API code snippets in the sidebar)
DEV_SIDEBAR_ENABLED = config("WS_DEV_SIDEBAR_ENABLED", cast=bool, default=False)

# Branding configuration
BRAND_NAME = config("WS_BRAND_NAME", default="Hyperclast")
LANDING_TEMPLATE = config("WS_LANDING_TEMPLATE", default="core/landing.html")

# Private features (not included in OSS release)
# Comma-separated list of private features to enable, e.g., "feature1,feature2"
PRIVATE_FEATURES = config("WS_PRIVATE_FEATURES", cast=Csv(), default="")

# Socratic preview output directory
SOCRATIC_PREVIEW_DIR = config("WS_SOCRATIC_PREVIEW_DIR", default="/tmp/socratic")

# Private feature configuration (passed to frontend, read by private modules)
PRIVATE_CONFIG = {
    "previewUrl": config("WS_PRIVATE_PREVIEW_URL", default=""),
}


def _discover_private_apps():
    """Load private Django apps that are both present and enabled."""
    private_apps = []
    private_dir = BASE_DIR / "private"

    if not private_dir.exists() or not PRIVATE_FEATURES:
        return private_apps

    for feature_name in PRIVATE_FEATURES:
        feature_dir = private_dir / feature_name
        if feature_dir.is_dir() and (feature_dir / "__init__.py").exists():
            private_apps.append(f"private.{feature_name}")

    return private_apps


PRIVATE_APPS = _discover_private_apps()
INSTALLED_APPS += PRIVATE_APPS
