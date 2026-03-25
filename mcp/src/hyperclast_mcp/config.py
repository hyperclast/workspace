"""Environment variable configuration."""

from __future__ import annotations

import os
import sys


def get_token() -> str:
    """Return the Hyperclast API token or exit with an error."""
    token = os.environ.get("HYPERCLAST_TOKEN", "").strip()
    if not token:
        print(
            "Error: HYPERCLAST_TOKEN environment variable is required.\n"
            "\n"
            "Set it to a Hyperclast access token. You can create one at:\n"
            "  https://hyperclast.com/settings/tokens\n"
            "\n"
            "Then export it:\n"
            "  export HYPERCLAST_TOKEN=your-token-here",
            file=sys.stderr,
        )
        sys.exit(1)
    return token


def get_base_url() -> str:
    """Return the Hyperclast base URL (no trailing slash)."""
    url = os.environ.get("HYPERCLAST_URL", "https://hyperclast.com").strip()
    return url.rstrip("/")
