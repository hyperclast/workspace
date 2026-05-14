from decouple import Csv

from backend.utils import init_logging, init_sentry_sdk

from .base import *


DEBUG = True
RUNTIME_ENV = "dev"

INSTALLED_APPS += [
    "debug_toolbar",
]

MIDDLEWARE += [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

INTERNAL_IPS = [
    "127.0.0.1",
]

CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# Allow Expo web dev server
CORS_ALLOWED_ORIGINS += ["http://localhost:8081"]
CSRF_TRUSTED_ORIGINS += ["http://localhost:8081"]

# Loosen import rate limits for the dev stack so the E2E suite, which
# imports the same PDF many times in a row, doesn't exhaust the per-user
# budget mid-run. Operators can still override via env vars; prod keeps
# the tighter base.py default (10 / 3600s).
WS_IMPORTS_RATE_LIMIT_REQUESTS = config("WS_IMPORTS_RATE_LIMIT_REQUESTS", default=1000, cast=int)
WS_IMPORTS_RATE_LIMIT_WINDOW_SECONDS = config("WS_IMPORTS_RATE_LIMIT_WINDOW_SECONDS", default=60, cast=int)

init_sentry_sdk(dsn=WS_SENTRY_DSN)

LOGGING = init_logging(WS_DEPLOYMENT_ID, LOG_FILE, log_level=LOG_LEVEL)
