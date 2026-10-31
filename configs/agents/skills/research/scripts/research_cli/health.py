"""Hosts whose connections stalled recently, remembered across commands.

An agent runs many commands in a row; once a host's handshakes stall, later
commands read the same content from another host first instead of waiting on
the stalled one again.
"""

import json
import os
import tempfile
import threading
import time
from pathlib import Path

from . import config

_lock = threading.Lock()


def stalls_file() -> Path:
    return config.CACHE / "stalls.json"


def read_stalls() -> dict[str, float]:
    try:
        stalls = json.loads(stalls_file().read_text())
    except OSError, ValueError:
        return {}
    return stalls if isinstance(stalls, dict) else {}


def record_stall(host: str) -> None:
    with _lock:
        stalls = read_stalls()
        stalls[host] = time.time()
        try:
            config.CACHE.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Write then rename, so a concurrent reader never sees a partial file.
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=config.CACHE, delete=False
            ) as pending:
                json.dump(stalls, pending)
            try:
                os.replace(pending.name, stalls_file())
            finally:
                Path(pending.name).unlink(missing_ok=True)
        except OSError:
            pass  # a lost record only costs a later command one stalled attempt


def stalled_recently(host: str) -> bool:
    stalled_at = read_stalls().get(host)
    return (
        isinstance(stalled_at, (int, float))
        and time.time() - stalled_at < config.STALL_MEMORY_SECONDS
    )
