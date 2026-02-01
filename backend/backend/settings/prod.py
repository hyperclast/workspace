from backend.utils import init_logging, init_sentry_sdk

from .base import *

DEBUG = False
RUNTIME_ENV = "prod"

init_sentry_sdk(dsn=WS_SENTRY_DSN)

LOGGING = init_logging(WS_DEPLOYMENT_ID, LOG_FILE, log_level=LOG_LEVEL)
LOGGING["loggers"]["django"]["handlers"] = ["file"]
LOGGING["root"]["handlers"] = ["file"]

JOB_RUNNER = "rq"

EMAIL_BACKEND = EMAIL_BACKENDS_MAP["postmark"]

# Trust the X-Forwarded-Proto header from reverse proxy (nginx)
# Required for correct HTTPS scheme detection in build_absolute_uri()
# nginx config sets: proxy_set_header X-Forwarded-Proto $scheme;
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
