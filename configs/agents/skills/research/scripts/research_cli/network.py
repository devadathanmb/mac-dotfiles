"""HTTP connection limits and phase-specific timeouts shared by the fetch backends."""

from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from threading import Lock

import httpx

from .config import (
    CONNECT_TIMEOUT_SECONDS,
    MAX_FETCH_WORKERS,
    REQUEST_TIMEOUT_SECONDS,
    ResearchError,
)

ClientFactory = Callable[[], httpx.Client]


def request_timeout(service: str) -> httpx.Timeout:
    return httpx.Timeout(
        REQUEST_TIMEOUT_SECONDS[service], connect=CONNECT_TIMEOUT_SECONDS
    )


def create_client() -> httpx.Client:
    try:
        return httpx.Client(
            timeout=request_timeout("exa"),
            limits=httpx.Limits(
                max_connections=MAX_FETCH_WORKERS,
                max_keepalive_connections=MAX_FETCH_WORKERS,
            ),
            follow_redirects=True,
        )
    except (OSError, ValueError) as error:
        # Bad TLS or proxy settings in the environment fail every backend alike.
        raise ResearchError(
            f"cannot create HTTP client: {error}",
            "check SSL_CERT_FILE and proxy environment variables",
            final=True,
        ) from error


@contextmanager
def open_client(client: httpx.Client | None = None) -> Iterator[httpx.Client]:
    """Yield the caller's pooled client, or a private one closed on exit."""
    if client is not None:
        yield client
        return
    with create_client() as owned:
        yield owned


@contextmanager
def shared_client() -> Iterator[ClientFactory]:
    """Open one pooled client on the first cache miss, then close it after the batch."""
    with ExitStack() as stack:
        client = None
        lock = Lock()

        def get_client() -> httpx.Client:
            nonlocal client
            with lock:
                if client is None:
                    client = stack.enter_context(create_client())
                return client

        yield get_client
