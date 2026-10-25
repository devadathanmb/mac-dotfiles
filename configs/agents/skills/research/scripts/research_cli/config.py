"""Paths, limits, timeouts, and cache lifetimes."""

import os
import tempfile
from pathlib import Path

from . import __version__

USER_AGENT = f"research-cli/{__version__}"

SECRETS = Path.home() / ".secrets"


def work_directory() -> Path:
    """Where saved responses and the cache live.

    `tempfile.gettempdir()` silently skips a `TMPDIR` that does not exist yet;
    a requested location is honoured and created on first use instead.
    """
    base = os.environ.get("TMPDIR") or tempfile.gettempdir()
    return Path(base) / f"research-{os.getuid()}"


WORK = work_directory()
CACHE = WORK / "cache"
OUTPUT = WORK / "out"
RETENTION_SECONDS = 24 * 3600

# Decompressed size; larger responses are an index or a dump, not a page to read.
MAX_BODY_BYTES = 10 * 1024 * 1024
MAX_WORKERS = 6
DEFAULT_MAX_CHARS = 4000
# Exa's page text is saved, not printed, so the cap only has to fit a long PDF.
EXA_PAGE_CHARS = 200_000

CONNECT_TIMEOUT_SECONDS = 5.0
# Read budget per service; DeepWiki answers questions by running a model.
TIMEOUT_SECONDS = {
    "deepwiki": 240.0,
    "page": 90.0,
    "exa": 90.0,
    "firecrawl": 75.0,
    "context7": 60.0,
    "grep": 60.0,
    "github": 30.0,
    "stackexchange": 30.0,
    "parallel": 30.0,
    "brave": 30.0,
    "tavily": 30.0,
}
# How long a cached response stays fresh; documentation indexes change slowly.
CACHE_TTL_SECONDS = {
    "context7": 24 * 3600,
    "deepwiki": 24 * 3600,
    "grep": 6 * 3600,
    "exa": 3600,
    "page": 3600,
    "raw": 3600,
    "firecrawl": 3600,
    "parallel": 3600,
    "brave": 3600,
    "tavily": 3600,
}
