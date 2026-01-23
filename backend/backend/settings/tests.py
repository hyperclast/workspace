import tempfile
from pathlib import Path

from cryptography.fernet import Fernet

from backend.utils import init_logging

from .base import *


DEBUG = False

# Use existing encryption key from env, or generate a test key
if not WS_ENCRYPTION_KEY:
    WS_ENCRYPTION_KEY = Fernet.generate_key().decode()
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
FILEHUB_FEATURE_ENABLED = True  # Enable for existing filehub tests

# Performance test thresholds (in nanoseconds)
# These can be overridden via environment variables for different hardware
WS_PERF_REQUEST_ID_GEN_NS = config("WS_PERF_REQUEST_ID_GEN_NS", default=1000, cast=int)
WS_PERF_MIDDLEWARE_NS = config("WS_PERF_MIDDLEWARE_NS", default=10000, cast=int)
WS_PERF_LOGGING_NS = config("WS_PERF_LOGGING_NS", default=1000, cast=int)

# Filehub storage settings - disabled for tests, all storage should be mocked
WS_FILEHUB_R2_ENDPOINT_URL = None
WS_FILEHUB_R2_ACCOUNT_ID = ""
WS_FILEHUB_R2_ACCESS_KEY_ID = ""
WS_FILEHUB_R2_SECRET_ACCESS_KEY = ""
WS_FILEHUB_R2_BUCKET = "test-filehub-uploads"

# Use temp directory for local storage in tests
WS_FILEHUB_LOCAL_STORAGE_ROOT = Path(tempfile.gettempdir()) / "filehub-tests"

# Disable replication in tests by default (use override_settings to enable per-test)
WS_FILEHUB_REPLICATION_ENABLED = False

# R2 Webhook settings for tests
WS_FILEHUB_R2_WEBHOOK_SECRET = "test-webhook-secret-for-unit-tests"
WS_FILEHUB_R2_WEBHOOK_ENABLED = False  # Disabled by default, enable per-test
