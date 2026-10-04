"""On-disk response cache and cleanup of expired cache/output files."""

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

from . import config
from .config import CACHE_TTL_SECONDS, RETENTION_SECONDS
from .firecrawl import scrape_page
from .mcp import request_tool
from .network import ClientFactory
from .pages import fetch_page, fetch_raw

DIRECT_FETCHERS = {"raw": fetch_raw, "page": fetch_page}


def remove_expired_files() -> None:
    cutoff = time.time() - RETENTION_SECONDS
    for directory in (config.CACHE, config.OUTPUT):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        for path in directory.iterdir():
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                pass


def cached_call(
    service: str,
    tool: str,
    arguments: dict,
    fresh: bool = False,
    *,
    client: ClientFactory | None = None,
) -> str:
    key = hashlib.sha1(
        json.dumps([service, tool, arguments], sort_keys=True).encode()
    ).hexdigest()
    path = config.CACHE / key
    if (
        not fresh
        and path.exists()
        and time.time() - path.stat().st_mtime < CACHE_TTL_SECONDS[service]
    ):
        return path.read_bytes().decode("utf-8")
    options = {"client": client()} if client is not None else {}
    if service in DIRECT_FETCHERS:
        text = DIRECT_FETCHERS[service](arguments["url"], **options)
    elif service == "firecrawl":
        text = scrape_page(arguments["url"], fresh=fresh, **options)
    else:
        text = request_tool(service, tool, arguments, **options)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", dir=config.CACHE, delete=False
    ) as pending:
        pending.write(text)
    try:
        os.replace(pending.name, path)
    finally:
        Path(pending.name).unlink(missing_ok=True)
    return text
