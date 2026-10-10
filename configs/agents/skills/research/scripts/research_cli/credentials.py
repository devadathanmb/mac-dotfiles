"""Load API keys from the environment or untracked local secret files."""

import os
import subprocess
from functools import cache

from .config import SECRETS


def api_key(environment_variable: str, filename: str) -> str | None:
    if value := os.environ.get(environment_variable, "").strip():
        return value
    try:
        return (SECRETS / filename).read_text().strip() or None
    except OSError:
        return None


@cache
def github_token() -> str | None:
    """A token for api.github.com, whose anonymous limit is 60 requests an hour."""
    for variable in ("GITHUB_TOKEN", "GH_TOKEN"):
        if value := os.environ.get(variable, "").strip():
            return value
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None
