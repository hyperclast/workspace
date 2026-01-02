from backend.utils import init_logging

from .base import *


DEBUG = False
RUNTIME_ENV = "tests"

WS_DEPLOYMENT_ID = "_tests"
LOGGING = init_logging(WS_DEPLOYMENT_ID, log_file=None, log_level="INFO")

# Allow localhost for test redirects
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

STRIPE_API_PUBLIC_KEY = None
STRIPE_API_SECRET_KEY = None
STRIPE_ENDPOINT_SECRET = None
STRIPE_PRO_PRICE_ID = None

JOB_RUNNER = None

DEFAULT_FROM_EMAIL = "webmaster@localhost"
SERVER_EMAIL = "server@localhost"
EMAIL_BACKEND = EMAIL_BACKENDS_MAP["test"]

HEADLESS_ONLY = True

ASK_FEATURE_ENABLED = False
