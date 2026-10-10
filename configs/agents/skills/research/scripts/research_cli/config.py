"""Paths, service tables, limits, and the shared error type."""

import os
import tempfile
from pathlib import Path

SECRETS = Path.home() / ".secrets"
WORK = Path(tempfile.gettempdir()) / f"research-{os.getuid()}"
CACHE = WORK / "cache"
OUTPUT = WORK / "out"
RETENTION_SECONDS = 24 * 3600
MAX_RAW_BYTES = 10 * 1024 * 1024
MAX_FETCH_WORKERS = 6
CONNECT_TIMEOUT_SECONDS = 5

ENDPOINTS = {
    "exa": "https://mcp.exa.ai/mcp?tools=web_search_exa,web_search_advanced_exa,web_fetch_exa,get_code_context_exa",
    "c7": "https://mcp.context7.com/mcp",
    "dw": "https://mcp.deepwiki.com/mcp",
    "grep": "https://mcp.grep.app",
}
CACHE_TTL_SECONDS = {
    "c7": 24 * 3600,
    "dw": 24 * 3600,
    "grep": 6 * 3600,
    "exa": 3600,
    "raw": 3600,
    "page": 3600,
    "firecrawl": 3600,
    "parallel": 3600,
    "brave": 3600,
    "tavily": 3600,
}
REQUEST_TIMEOUT_SECONDS = {
    "dw": 240,
    "exa": 90,
    "c7": 60,
    "grep": 60,
    "firecrawl": 75,
    "parallel": 30,
    "brave": 30,
    "tavily": 30,
}
DEFAULT_MAX_CHARS = 4000
# Exa's page text is saved, not printed, so the cap only has to fit a long PDF.
EXA_PAGE_CHARS = 200_000


class ResearchError(Exception):
    def __init__(
        self,
        message: str,
        hint: str = "",
        *,
        final: bool = False,
        status: int | None = None,
    ):
        super().__init__(message)
        self.hint = hint
        # final: retrying with another source cannot help (e.g. HTTP 404).
        self.final = final
        # status: the HTTP status behind the failure, when a provider reported one.
        self.status = status
