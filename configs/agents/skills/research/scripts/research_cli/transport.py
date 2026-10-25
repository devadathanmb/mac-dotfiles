"""HTTP clients: page downloads over a browser fingerprint, API calls over httpx2.

Bot protection rejects clients by their TLS and HTTP/2 fingerprint, so pages are
downloaded with curl_cffi impersonating Chrome. Some sites block that fingerprint
instead, and curl_cffi does not read the macOS keychain (where a corporate
proxy's root certificate lives), so a refused browser download is retried with
httpx2. API calls use httpx2 directly: an API needs no disguise.
"""

import threading
from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from email.message import Message
from types import TracebackType
from typing import Any, Protocol, Self, cast

import httpx2
from curl_cffi import requests as curl_requests
from curl_cffi.requests import exceptions as curl_errors

from . import config
from .errors import ResearchError

IMPERSONATE = "chrome"
MAX_REDIRECTS = 10
CHUNK_BYTES = 64 * 1024
# Bot protection answers with these; a client with another fingerprint may pass.
BLOCKED_STATUSES = frozenset({401, 403, 429, 503})
GONE_STATUSES = frozenset({404, 410})
# Text types outside text/*; octet-stream is how some hosts serve source files.
TEXT_MIMES = frozenset(
    {
        "application/json",
        "application/xml",
        "application/javascript",
        "application/yaml",
        "application/x-yaml",
        "application/toml",
        "application/octet-stream",
    }
)
TOO_LARGE_HINT = (
    "request a narrower URL: a versioned, filtered, or paginated endpoint, "
    "or one file instead of an index"
)


class BrowserResponse(Protocol):
    status_code: int
    url: str
    headers: Mapping[str, str]

    def iter_content(self) -> Iterator[bytes]: ...


class BrowserSession(Protocol):
    def stream(
        self, method: str, url: str, **options: Any
    ) -> AbstractContextManager[BrowserResponse]: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class Download:
    """A text response body and where it came from."""

    url: str  # after redirects
    mime: str  # lowercase, without parameters
    charset: str | None
    body: bytes

    def text(self) -> str:
        try:
            text = self.body.decode(self.charset or "utf-8")
        except (UnicodeError, LookupError) as error:
            raise ResearchError(
                "response could not be decoded as text", "use fetch --exa"
            ) from error
        if "\x00" in text:
            raise ResearchError(
                "response contains binary data", "use a text source or fetch --exa"
            )
        return text


class Refused(ResearchError):
    """A browser-fingerprint download that a plain client may still complete."""


def timeout(service: str) -> httpx2.Timeout:
    return httpx2.Timeout(
        config.TIMEOUT_SECONDS[service], connect=config.CONNECT_TIMEOUT_SECONDS
    )


def new_api_client() -> httpx2.Client:
    try:
        return httpx2.Client(
            timeout=timeout("page"),
            limits=httpx2.Limits(
                max_connections=config.MAX_WORKERS,
                max_keepalive_connections=config.MAX_WORKERS,
            ),
            max_redirects=MAX_REDIRECTS,
        )
    except (OSError, ValueError) as error:
        # Bad TLS or proxy settings in the environment fail every request alike.
        raise ResearchError(
            f"cannot create HTTP client: {error}",
            "check SSL_CERT_FILE and proxy environment variables",
            final=True,
        ) from error


def new_browser_session() -> BrowserSession:
    # A sync session keeps one curl handle per thread, so worker threads share it.
    session = curl_requests.Session(impersonate=IMPERSONATE)
    return cast(BrowserSession, session)


def content_type(value: str | None) -> tuple[str, str | None]:
    """(lowercase MIME type, charset) from a Content-Type header."""
    header = Message()
    header["Content-Type"] = value or "text/plain"
    return header.get_content_type(), header.get_content_charset()


def is_text(mime: str) -> bool:
    return (
        mime.startswith("text/")
        or mime.endswith(("+json", "+xml"))
        or (mime in TEXT_MIMES)
    )


def read_body(
    url: str, status: int, content_type_header: str | None, chunks: Iterator[bytes]
) -> Download:
    """Check the status and type before the body, then read at most the size cap."""
    if status >= 400:
        raise ResearchError(
            f"HTTP {status}", status=status, final=status in GONE_STATUSES
        )
    mime, charset = content_type(content_type_header)
    if not is_text(mime):
        raise ResearchError(
            f"expected text, got {mime}", "use fetch --exa for document extraction"
        )
    body = bytearray()
    for chunk in chunks:
        if len(body) + len(chunk) > config.MAX_BODY_BYTES:
            # An extraction service would only return a broken fragment of it.
            raise ResearchError("response exceeds 10 MiB", TOO_LARGE_HINT, final=True)
        body.extend(chunk)
    return Download(url, mime, charset, bytes(body))


def root_message(error: BaseException) -> str:
    """The innermost cause's message, which names the actual failure."""
    while (cause := error.__cause__ or error.__context__) is not None:
        error = cause
    # ssl errors render their single argument as a tuple.
    if len(error.args) == 1 and isinstance(error.args[0], str):
        return error.args[0]
    return str(error) or type(error).__name__


def curl_message(error: Exception) -> str:
    """curl's message without its pointer to the libcurl error documentation."""
    return str(error).split(". See https://curl.se/", 1)[0]


def response_detail(response: httpx2.Response) -> str:
    return response.text[:160].replace("\n", " ").strip()


class Http:
    """The clients one command shares across its threads, each opened on first use.

    A command answered from the cache never opens a connection.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._api: httpx2.Client | None = None
        self._browser: BrowserSession | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            if self._api is not None:
                self._api.close()
            if self._browser is not None:
                self._browser.close()
            self._api = self._browser = None

    @property
    def api(self) -> httpx2.Client:
        with self._lock:
            if self._api is None:
                self._api = new_api_client()
            return self._api

    @property
    def browser(self) -> BrowserSession:
        with self._lock:
            if self._browser is None:
                self._browser = new_browser_session()
            return self._browser

    def download(
        self,
        url: str,
        *,
        accept: str = "*/*",
        headers: Mapping[str, str] | None = None,
        impersonate: bool = True,
    ) -> Download:
        """GET a text body of at most `MAX_BODY_BYTES`, following redirects.

        With `impersonate`, a browser fingerprint is tried first and a plain
        client second, when the site refuses the browser.
        """
        request_headers = {"Accept": accept, **(headers or {})}
        if not impersonate:
            return self._download_plain(url, request_headers)
        try:
            return self._download_impersonated(url, request_headers)
        except Refused as error:
            refusal = error
        # Outside the handler, so the plain client's errors do not chain to curl's.
        try:
            return self._download_plain(url, request_headers)
        except ResearchError as error:
            if error.message == refusal.message:
                message = f"{error.message} (browser and plain clients)"
            else:
                message = f"{error.message}; browser client: {refusal}"
            raise ResearchError(
                message, error.hint, final=error.final, status=error.status
            ) from error

    def _download_impersonated(self, url: str, headers: dict[str, str]) -> Download:
        try:
            with self.browser.stream(
                "GET",
                url,
                headers=headers,
                timeout=(
                    config.CONNECT_TIMEOUT_SECONDS,
                    config.TIMEOUT_SECONDS["page"],
                ),
                allow_redirects=True,
                max_redirects=MAX_REDIRECTS,
            ) as response:
                return read_body(
                    str(response.url),
                    response.status_code,
                    response.headers.get("Content-Type"),
                    response.iter_content(),
                )
        except ResearchError as error:
            if error.status in BLOCKED_STATUSES:
                raise Refused(error.message, status=error.status) from error
            raise
        except curl_errors.Timeout as error:
            raise ResearchError(
                "timeout", "the server is slow; try fetch --exa"
            ) from error
        except curl_errors.DNSError as error:
            raise ResearchError("cannot resolve host", "check the URL") from error
        except curl_errors.RequestException as error:
            # TLS (an untrusted proxy root) or HTTP/2 protocol errors.
            raise Refused(f"{type(error).__name__}: {curl_message(error)}") from error

    def _download_plain(self, url: str, headers: dict[str, str]) -> Download:
        try:
            with self.api.stream(
                "GET",
                url,
                headers={"User-Agent": config.USER_AGENT, **headers},
                timeout=timeout("page"),
                follow_redirects=True,
            ) as response:
                return read_body(
                    str(response.url),
                    response.status_code,
                    response.headers.get("Content-Type"),
                    response.iter_bytes(CHUNK_BYTES),
                )
        except httpx2.TimeoutException as error:
            raise ResearchError(
                "timeout", "the server is slow; try fetch --exa"
            ) from error
        except httpx2.DecodingError as error:
            raise ResearchError(
                "invalid compressed response", "retry later or use fetch --exa"
            ) from error
        except (httpx2.HTTPError, httpx2.InvalidURL, httpx2.StreamError) as error:
            raise ResearchError(
                root_message(error), "check the URL and network, then retry"
            ) from error

    def call_api(
        self,
        service: str,
        method: str,
        url: str,
        *,
        label: str,
        hint: str,
        status_hints: Mapping[int, str] | None = None,
        show_body: bool = True,
        **options: Any,
    ) -> httpx2.Response:
        """Send an API request without following redirects.

        Failures raise with `label` as the prefix: `status_hints` explain known
        statuses, and `hint` covers the rest.
        """
        status_hints = status_hints or {}
        try:
            response = self.api.request(
                method, url, timeout=timeout(service), follow_redirects=False, **options
            )
        except httpx2.TimeoutException as error:
            raise ResearchError(f"{label}: timeout", hint) from error
        except (httpx2.HTTPError, httpx2.InvalidURL) as error:
            raise ResearchError(f"{label}: {root_message(error)}", hint) from error
        if response.is_success:
            return response
        status = response.status_code
        # A known status is explained by its hint; other bodies may say why.
        detail = ""
        if show_body and status not in status_hints:
            detail = f" {response_detail(response)}".rstrip()
        raise ResearchError(
            f"{label}: HTTP {status}{detail}",
            status_hints.get(status, hint),
            status=status,
        )


def json_body(response: httpx2.Response, label: str) -> Any:
    try:
        return response.json()
    except ValueError as error:
        raise ResearchError(f"{label}: invalid JSON response") from error
