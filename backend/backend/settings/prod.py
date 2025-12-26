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
