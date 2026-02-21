import os
from datetime import timedelta
from pathlib import Path

from decouple import Config, Csv, RepositoryEnv
from decouple import config as _default_config

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
    "filehub",
    "imports",
    "pages.apps.PagesConfig",
    "pulse",
    "updates",
    "users",
]

AUTH_USER_MODEL = "users.User"

HIJACK_LOGOUT_REDIRECT_URL = "/admin/users/user/"
HIJACK_PERMISSION_CHECK = "users.utils.can_hijack_user"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

MIDDLEWARE = [
    "core.middlewares.RequestIDMiddleware",  # Must be first to capture all requests
    "core.middlewares.ClientHeaderMiddleware",  # Log client identification headers
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middlewares.ThrottledSessionRefreshMiddleware",  # Rolling session refresh (after auth)
    "users.middlewares.LastActiveMiddleware",
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
SESSION_COOKIE_AGE = 400 * 24 * 60 * 60  # 400 days (browser max)
SESSION_COOKIE_SAMESITE = "Lax"

# Rolling session refresh interval - sessions are extended by this middleware
# once per interval instead of on every request (avoids DB write overhead).
# Set to None to disable rolling sessions entirely.
SESSION_REFRESH_INTERVAL = timedelta(hours=24)

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
    "x-hyperclast-client",  # Client identification header for telemetry
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
ACCOUNT_EMAIL_VERIFICATION = config("ACCOUNT_EMAIL_VERIFICATION", default="mandatory")
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
    "account_confirm_email": "/accounts/confirm-email/{key}/",
}

# Hyperclast settings (continued)
WS_DEPLOYMENT_ID = config("WS_DEPLOYMENT_ID", "_local")
CLI_VERSION = config("WS_CLI_VERSION", default="0.1.0")
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
STRIPE_API_PUBLISHABLE_KEY = config("WS_STRIPE_API_PUBLISHABLE_KEY", default=None)
STRIPE_API_SECRET_KEY = config("WS_STRIPE_API_SECRET_KEY", default=None)
STRIPE_ENDPOINT_SECRET = config("WS_STRIPE_ENDPOINT_SECRET", default=None)
STRIPE_PRO_PRICE_ID = config("WS_STRIPE_PRO_PRICE_ID", default=None)
BILLING_ADMIN_EMAILS = config(
    "WS_BILLING_ADMIN_EMAILS", default="", cast=lambda v: [e.strip() for e in v.split(",") if e.strip()]
)

# Billing authorization settings
# When True, only org admins can initiate checkout and access the billing portal
# When False, any org member can manage billing
ALLOW_ONLY_ORG_ADMIN_TO_MANAGE_BILLING = config("WS_ALLOW_ONLY_ORG_ADMIN_TO_MANAGE_BILLING", cast=bool, default=True)


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
JOB_IMPORTS_QUEUE = "imports"

RQ_QUEUES = {
    JOB_INTERNAL_QUEUE: COMMON_RQ_SETTINGS,
    JOB_EMAIL_QUEUE: COMMON_RQ_SETTINGS,
    JOB_AI_QUEUE: COMMON_RQ_SETTINGS,
    JOB_IMPORTS_QUEUE: {
        **COMMON_RQ_SETTINGS,
        "DEFAULT_TIMEOUT": 900,  # 15 minutes for large imports
    },
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

# OpenAI defaults (API keys are now configured per-user/org via AIProviderConfig)
OPENAI_DEFAULT_CHAT_MODEL = "gpt-4o"
OPENAI_DEFAULT_CHAT_MAX_TOKENS = 1500
OPENAI_DEFAULT_CHAT_TEMPERATURE = 0.3

# Ask feature
ASK_FEATURE_ENABLED = config("WS_ASK_FEATURE_ENABLED", cast=bool, default=True)
ASK_EMBEDDINGS_DEFAULT_MODEL = "text-embedding-3-small"
ASK_EMBEDDINGS_DEFAULT_ENCODING = "cl100k_base"
ASK_EMBEDDINGS_DEFAULT_MAX_INPUT = 8191
ASK_EMBEDDINGS_MAX_PAGES = 5
WS_ASK_RATE_LIMIT_REQUESTS = config("WS_ASK_RATE_LIMIT_REQUESTS", cast=int, default=30)
WS_ASK_RATE_LIMIT_WINDOW_SECONDS = config("WS_ASK_RATE_LIMIT_WINDOW_SECONDS", cast=int, default=60)

# Dev sidebar (shows API code snippets in the sidebar)
DEV_SIDEBAR_ENABLED = config("WS_DEV_SIDEBAR_ENABLED", cast=bool, default=False)

# Filehub (file upload) feature
FILEHUB_FEATURE_ENABLED = config("WS_FILEHUB_FEATURE_ENABLED", cast=bool, default=False)

# Branding configuration
BRAND_NAME = config("WS_BRAND_NAME", default="Hyperclast")
LANDING_TEMPLATE = config("WS_LANDING_TEMPLATE", default="core/landing.html")

# Updates/broadcast email configuration
UPDATES_TEST_EMAIL = config("WS_UPDATES_TEST_EMAIL", default="test@example.com")
UPDATES_FROM_EMAIL = config("WS_UPDATES_FROM_EMAIL", default=DEFAULT_FROM_EMAIL)
UPDATES_POSTMARK_TOKEN = config("WS_UPDATES_POSTMARK_TOKEN", default=None)
UPDATE_DEFAULT_AUTHOR_NAME = config("WS_UPDATE_DEFAULT_AUTHOR_NAME", default="")
UPDATE_DEFAULT_AUTHOR_PICTURE = config("WS_UPDATE_DEFAULT_AUTHOR_PICTURE", default="")


# Filehub Storage Configuration
WS_FILEHUB_PRIMARY_UPLOAD_TARGET = config("WS_FILEHUB_PRIMARY_UPLOAD_TARGET", default="r2")

# R2 Configuration (Cloudflare R2 / S3-compatible storage)
WS_FILEHUB_R2_ENDPOINT_URL = config("WS_FILEHUB_R2_ENDPOINT_URL", default=None)
WS_FILEHUB_R2_PUBLIC_ENDPOINT_URL = config("WS_FILEHUB_R2_PUBLIC_ENDPOINT_URL", default=None)
WS_FILEHUB_R2_ACCOUNT_ID = config("WS_FILEHUB_R2_ACCOUNT_ID", default="")
WS_FILEHUB_R2_ACCESS_KEY_ID = config("WS_FILEHUB_R2_ACCESS_KEY_ID", default="")
WS_FILEHUB_R2_SECRET_ACCESS_KEY = config("WS_FILEHUB_R2_SECRET_ACCESS_KEY", default="")
WS_FILEHUB_R2_BUCKET = config("WS_FILEHUB_R2_BUCKET", default="ws-filehub-uploads")

# Local Storage Configuration (for development/testing or replication)
WS_FILEHUB_LOCAL_STORAGE_ROOT = config("WS_FILEHUB_LOCAL_STORAGE_ROOT", default="/var/filehub/storage")
WS_FILEHUB_LOCAL_BASE_URL = config("WS_FILEHUB_LOCAL_BASE_URL", default="http://localhost:8000")

# URL Expiration Settings (in seconds)
WS_FILEHUB_UPLOAD_URL_EXPIRATION = config("WS_FILEHUB_UPLOAD_URL_EXPIRATION", default=600, cast=int)  # 10 minutes
WS_FILEHUB_DOWNLOAD_URL_EXPIRATION = config("WS_FILEHUB_DOWNLOAD_URL_EXPIRATION", default=600, cast=int)  # 10 minutes

# Replication Settings
# When enabled, files are replicated to all storage providers after upload finalization
WS_FILEHUB_REPLICATION_ENABLED = config("WS_FILEHUB_REPLICATION_ENABLED", default=False, cast=bool)

# R2 Webhook Settings (for automatic upload finalization via Cloudflare Worker)
WS_FILEHUB_R2_WEBHOOK_SECRET = config("WS_FILEHUB_R2_WEBHOOK_SECRET", default="")
WS_FILEHUB_R2_WEBHOOK_ENABLED = config("WS_FILEHUB_R2_WEBHOOK_ENABLED", default=False, cast=bool)

# Stale Upload Cleanup Settings
# Time in seconds after which pending uploads are considered stale (default: 24 hours)
WS_FILEHUB_STALE_UPLOAD_THRESHOLD_SECONDS = config("WS_FILEHUB_STALE_UPLOAD_THRESHOLD_SECONDS", default=86400, cast=int)
# Maximum number of stale uploads to process per batch (default: 1000)
WS_FILEHUB_STALE_UPLOAD_BATCH_SIZE = config("WS_FILEHUB_STALE_UPLOAD_BATCH_SIZE", default=1000, cast=int)

# Rate Limiting for File Upload Creation
WS_FILEHUB_UPLOAD_RATE_LIMIT_REQUESTS = config("WS_FILEHUB_UPLOAD_RATE_LIMIT_REQUESTS", default=60, cast=int)
WS_FILEHUB_UPLOAD_RATE_LIMIT_WINDOW_SECONDS = config(
    "WS_FILEHUB_UPLOAD_RATE_LIMIT_WINDOW_SECONDS", default=60, cast=int
)

# Maximum File Size Limit (default: 10 MB)
WS_FILEHUB_MAX_FILE_SIZE_BYTES = config("WS_FILEHUB_MAX_FILE_SIZE_BYTES", default=10485760, cast=int)

# Allowed Content Types for File Uploads
# Comprehensive list of safe content types for file uploads.
# Can be overridden via environment variable as comma-separated values.
WS_FILEHUB_ALLOWED_CONTENT_TYPES = config(
    "WS_FILEHUB_ALLOWED_CONTENT_TYPES",
    cast=lambda v: frozenset(x.strip() for x in v.split(",") if x.strip()) if v else None,
    default=None,
)

# Default allowed content types (used when WS_FILEHUB_ALLOWED_CONTENT_TYPES is not set)
WS_FILEHUB_DEFAULT_ALLOWED_CONTENT_TYPES = frozenset(
    {
        # Images
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/svg+xml",
        "image/bmp",
        "image/tiff",
        "image/x-icon",
        "image/vnd.microsoft.icon",
        "image/heic",
        "image/heif",
        "image/avif",
        # Documents
        "application/pdf",
        "application/rtf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.oasis.opendocument.text",
        "application/vnd.oasis.opendocument.spreadsheet",
        "application/vnd.oasis.opendocument.presentation",
        # Text and code
        "text/plain",
        "text/markdown",
        "text/csv",
        "text/html",
        "text/css",
        "text/javascript",
        "text/xml",
        "text/x-python",
        "text/x-java-source",
        "text/x-c",
        "text/x-c++",
        "text/x-ruby",
        "text/x-go",
        "text/x-rust",
        "text/x-typescript",
        "text/x-yaml",
        "text/x-toml",
        # Data formats
        "application/json",
        "application/xml",
        "application/yaml",
        "application/x-yaml",
        # Archives
        "application/zip",
        "application/gzip",
        "application/x-gzip",
        "application/x-tar",
        "application/x-bzip2",
        "application/x-7z-compressed",
        "application/x-rar-compressed",
        # Audio
        "audio/mpeg",
        "audio/mp3",
        "audio/wav",
        "audio/x-wav",
        "audio/ogg",
        "audio/webm",
        "audio/aac",
        "audio/flac",
        "audio/x-flac",
        "audio/mp4",
        "audio/x-m4a",
        # Video
        "video/mp4",
        "video/mpeg",
        "video/webm",
        "video/ogg",
        "video/quicktime",
        "video/x-msvideo",
        "video/x-matroska",
        # Fonts
        "font/woff",
        "font/woff2",
        "font/ttf",
        "font/otf",
        "application/font-woff",
        "application/font-woff2",
        # Other common types
        "application/octet-stream",  # Generic binary
        "application/x-sqlite3",
        "application/wasm",
    }
)


# Private features (not included in OSS release)
# Comma-separated list of private features to enable, e.g., "feature1,feature2"
PRIVATE_FEATURES = config("WS_PRIVATE_FEATURES", cast=Csv(), default="")

# Imports temp directory (must be shared between web and worker containers)
WS_IMPORTS_TEMP_DIR = config("WS_IMPORTS_TEMP_DIR", default="/tmp")

# Import archive size limits (to upload)
WS_IMPORTS_MAX_FILE_SIZE_BYTES = config("WS_IMPORTS_MAX_FILE_SIZE_BYTES", default=104857600, cast=int)  # 100MB

# Import Rate Limiting
WS_IMPORTS_RATE_LIMIT_REQUESTS = config("WS_IMPORTS_RATE_LIMIT_REQUESTS", default=10, cast=int)
WS_IMPORTS_RATE_LIMIT_WINDOW_SECONDS = config("WS_IMPORTS_RATE_LIMIT_WINDOW_SECONDS", default=3600, cast=int)

# Zip Bomb Prevention Thresholds
# Maximum total uncompressed size (default: 5GB)
WS_IMPORTS_MAX_UNCOMPRESSED_SIZE_BYTES = config(
    "WS_IMPORTS_MAX_UNCOMPRESSED_SIZE_BYTES",
    default=5 * 1024 * 1024 * 1024,  # 5 GB
    cast=int,
)
# Maximum compression ratio allowed (default: 30x)
WS_IMPORTS_MAX_COMPRESSION_RATIO = config("WS_IMPORTS_MAX_COMPRESSION_RATIO", default=30.0, cast=float)
# Maximum number of files in archive (default: 100,000)
WS_IMPORTS_MAX_FILE_COUNT = config("WS_IMPORTS_MAX_FILE_COUNT", default=100000, cast=int)
# Maximum size of a single file within the archive (default: 1GB)
WS_IMPORTS_MAX_SINGLE_FILE_SIZE_BYTES = config(
    "WS_IMPORTS_MAX_SINGLE_FILE_SIZE_BYTES",
    default=1 * 1024 * 1024 * 1024,  # 1 GB
    cast=int,
)
# Maximum directory depth within archive (default: 30)
WS_IMPORTS_MAX_PATH_DEPTH = config("WS_IMPORTS_MAX_PATH_DEPTH", default=30, cast=int)
# Maximum nested zip depth (default: 2, for Notion's ExportBlock-*-Part-*.zip pattern)
WS_IMPORTS_MAX_NESTED_ZIP_DEPTH = config("WS_IMPORTS_MAX_NESTED_ZIP_DEPTH", default=2, cast=int)
# Extraction timeout in seconds (default: 300 = 5 minutes)
WS_IMPORTS_EXTRACTION_TIMEOUT_SECONDS = config("WS_IMPORTS_EXTRACTION_TIMEOUT_SECONDS", default=300, cast=int)

# Import abuse thresholds (violations within window trigger ban)
# Number of days to look back for abuse threshold calculations
WS_IMPORTS_ABUSE_WINDOW_DAYS = config("WS_IMPORTS_ABUSE_WINDOW_DAYS", default=7, cast=int)
# Number of CRITICAL severity violations to trigger ban (default: 1)
WS_IMPORTS_ABUSE_CRITICAL_THRESHOLD = config("WS_IMPORTS_ABUSE_CRITICAL_THRESHOLD", default=1, cast=int)
# Number of HIGH severity violations to trigger ban (default: 2)
WS_IMPORTS_ABUSE_HIGH_THRESHOLD = config("WS_IMPORTS_ABUSE_HIGH_THRESHOLD", default=2, cast=int)
# Number of MEDIUM severity violations to trigger ban (default: 5)
WS_IMPORTS_ABUSE_MEDIUM_THRESHOLD = config("WS_IMPORTS_ABUSE_MEDIUM_THRESHOLD", default=5, cast=int)
# Number of LOW severity violations to trigger ban (default: 10)
WS_IMPORTS_ABUSE_LOW_THRESHOLD = config("WS_IMPORTS_ABUSE_LOW_THRESHOLD", default=10, cast=int)

# Stale import cleanup settings
# Time in seconds after which orphaned temp files are cleaned up (default: 24 hours)
WS_IMPORTS_TEMP_FILE_CLEANUP_THRESHOLD_SECONDS = config(
    "WS_IMPORTS_TEMP_FILE_CLEANUP_THRESHOLD_SECONDS",
    default=86400,  # 24 hours
    cast=int,
)
# Maximum number of stale imports to process per cleanup run (default: 1000)
WS_IMPORTS_STALE_CLEANUP_BATCH_SIZE = config("WS_IMPORTS_STALE_CLEANUP_BATCH_SIZE", default=1000, cast=int)

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
