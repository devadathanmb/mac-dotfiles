"""API keys from the environment or untracked files in ~/.secrets."""

import os
import subprocess
from dataclasses import dataclass
from functools import cache

from . import config


@dataclass(frozen=True)
class Key:
    variable: str
    filename: str

    @property
    def locations(self) -> str:
        return f"${self.variable} or ~/.secrets/{self.filename}"


KEYS = {
    "exa": Key("EXA_API_KEY", "exa-api-key"),
    "context7": Key("CONTEXT7_API_KEY", "context7-api-key"),
    "parallel": Key("PARALLEL_API_KEY", "parallel-api-key"),
    "brave": Key("BRAVE_API_KEY", "brave-api-key"),
    "tavily": Key("TAVILY_API_KEY", "tavily-api-key"),
    "firecrawl": Key("FIRECRAWL_API_KEY", "firecrawl-api-key"),
    # Optional: raises the Stack Exchange quota from 300 to 10,000 requests a day.
    "stackexchange": Key("STACKEXCHANGE_KEY", "stackexchange-key"),
}


def api_key(service: str) -> str | None:
    key = KEYS[service]
    if value := os.environ.get(key.variable, "").strip():
        return value
    try:
        return (config.SECRETS / key.filename).read_text().strip() or None
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
    except OSError, subprocess.SubprocessError:
        return None
    return result.stdout.strip() or None
