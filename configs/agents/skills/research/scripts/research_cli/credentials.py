"""Load API keys from the environment or untracked local secret files."""

import os

from .config import SECRETS


def api_key(environment_variable: str, filename: str) -> str | None:
    if value := os.environ.get(environment_variable, "").strip():
        return value
    try:
        return (SECRETS / filename).read_text().strip() or None
    except OSError:
        return None
