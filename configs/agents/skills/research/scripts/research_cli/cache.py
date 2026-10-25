"""On-disk response cache, and cleanup of expired cache and output files."""

import hashlib
import json
import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from . import config


def remove_expired_files() -> None:
    cutoff = time.time() - config.RETENTION_SECONDS
    for directory in (config.CACHE, config.OUTPUT):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        for path in directory.iterdir():
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                pass  # removed concurrently by another research process


def cached(
    namespace: str,
    key: object,
    compute: Callable[[], str],
    *,
    fresh: bool = False,
) -> str:
    """`compute()`, reused for `config.CACHE_TTL_SECONDS[namespace]` seconds.

    `key` must be JSON-serialisable; failures raise and are never cached.
    """
    digest = hashlib.sha256(
        json.dumps([namespace, key], sort_keys=True).encode()
    ).hexdigest()
    path = config.CACHE / digest
    ttl = config.CACHE_TTL_SECONDS[namespace]
    if not fresh and path.exists() and time.time() - path.stat().st_mtime < ttl:
        return path.read_bytes().decode("utf-8")
    text = compute()
    config.CACHE.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Write then rename, so a concurrent reader never sees a partial file.
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", dir=config.CACHE, delete=False
    ) as pending:
        pending.write(text)
    try:
        os.replace(pending.name, path)
    finally:
        Path(pending.name).unlink(missing_ok=True)
    return text
