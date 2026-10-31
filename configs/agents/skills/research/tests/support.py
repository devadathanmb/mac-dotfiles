"""Test harness: the real CLI against a fake web, isolated from keys and the cache.

`FakeWeb` answers every HTTP request either client makes. Handlers receive an
httpx2 request plus the transport's name ("browser" or "plain"), so a test can
make a site refuse the browser fingerprint but serve the plain client.
"""

import contextlib
import io
import json
import os
import tempfile
import unittest
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urljoin

import httpx2
from curl_cffi.requests import exceptions as curl_errors

from research_cli import cli, config, credentials, mcp, providers, transport

Handler = Callable[[httpx2.Request, str], httpx2.Response]


@dataclass
class Sent:
    method: str
    url: str
    transport: str
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body)


@dataclass
class FakeWeb:
    """Routes by host, or by `host/path` prefix; the longest match wins."""

    routes: dict[str, Handler] = field(default_factory=dict)
    sent: list[Sent] = field(default_factory=list)

    def route(self, prefix: str, handler: Handler) -> None:
        self.routes[prefix] = handler

    def serve(self, prefix: str, response: Callable[[], httpx2.Response]) -> None:
        self.route(prefix, lambda request, name: response())

    def handle(self, request: httpx2.Request, transport_name: str) -> httpx2.Response:
        request.read()
        self.sent.append(
            Sent(
                request.method,
                str(request.url),
                transport_name,
                dict(request.headers),
                request.content,
            )
        )
        target = f"{request.url.host}{request.url.path}"
        matches = [prefix for prefix in self.routes if target.startswith(prefix)]
        if not matches:
            raise AssertionError(f"unexpected request: {request.method} {request.url}")
        return self.routes[max(matches, key=len)](request, transport_name)

    def urls(self, host: str | None = None) -> list[str]:
        return [sent.url for sent in self.sent if host is None or host in sent.url]


class FakeBrowserResponse:
    def __init__(self, response: httpx2.Response, url: str) -> None:
        self.status_code = response.status_code
        self.headers = response.headers
        self.url = url
        self._response = response

    def iter_content(self) -> Iterator[bytes]:
        yield from self._response.iter_bytes()


class FakeBrowserSession:
    """curl_cffi's Session surface, answered by the fake web."""

    def __init__(self, web: FakeWeb) -> None:
        self.web = web
        self.closed = False

    @contextlib.contextmanager
    def stream(
        self, method: str, url: str, **options: Any
    ) -> Iterator[FakeBrowserResponse]:
        headers = options.get("headers") or {}
        for _ in range(transport.MAX_REDIRECTS + 1):
            request = httpx2.Request(method, url, headers=headers)
            response = self.web.handle(request, "browser")
            location = response.headers.get("Location")
            if response.is_redirect and location:
                url = urljoin(url, location)
                continue
            yield FakeBrowserResponse(response, url)
            return
        raise AssertionError("too many redirects")

    def close(self) -> None:
        self.closed = True


def stall(request: httpx2.Request, transport_name: str) -> httpx2.Response:
    """A handshake the network dropped, as each client reports it."""
    if transport_name == "browser":
        raise curl_errors.Timeout(
            "Failed to perform, curl: (28) Connection timed out after 3001 milliseconds"
        )
    raise httpx2.ConnectTimeout("handshake timed out", request=request)


def in_turn(*handlers: Handler) -> Handler:
    """A handler answering successive requests with each of `handlers`."""
    remaining = list(handlers)

    def handle(request: httpx2.Request, transport_name: str) -> httpx2.Response:
        return remaining.pop(0)(request, transport_name)

    return handle


def mcp_text(text: str) -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": [{"type": "text", "text": text}]},
        },
    )


def tool_call(request: httpx2.Request) -> tuple[str, dict[str, Any]]:
    """(tool name, arguments) of an MCP request."""
    params = json.loads(request.content)["params"]
    return params["name"], params["arguments"]


def html_page(body: str, title: str = "") -> httpx2.Response:
    head = f"<head><title>{title}</title></head>" if title else ""
    return httpx2.Response(200, html=f"<html>{head}<body>{body}</body></html>")


@dataclass
class Result:
    code: int
    stdout: str
    stderr: str

    @property
    def lines(self) -> list[str]:
        return self.stdout.splitlines()


KEY_VARIABLES = [key.variable for key in credentials.KEYS.values()] + [
    "GITHUB_TOKEN",
    "GH_TOKEN",
]


class ResearchTestCase(unittest.TestCase):
    """Runs the CLI with a fresh cache, no keys, and the fake web as the network."""

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.web = FakeWeb()
        self.browsers: list[FakeBrowserSession] = []
        self.api_clients: list[httpx2.Client] = []
        secrets = self.root / "secrets"
        secrets.mkdir()
        environment = {
            name: value
            for name, value in os.environ.items()
            if name not in KEY_VARIABLES
        }
        credentials.github_token.cache_clear()
        self.addCleanup(credentials.github_token.cache_clear)
        for patcher in (
            patch.object(config, "CACHE", self.root / "cache"),
            patch.object(config, "OUTPUT", self.root / "out"),
            patch.object(config, "SECRETS", secrets),
            patch.dict(os.environ, environment, clear=True),
            patch.object(credentials, "github_token", return_value=None),
            patch.object(transport, "new_api_client", side_effect=self.new_api_client),
            patch.object(
                transport, "new_browser_session", side_effect=self.new_browser
            ),
            patch.object(mcp, "sleep"),
            patch.object(providers.brave_throttle, "interval", 0),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.secrets = secrets

    def new_api_client(self) -> httpx2.Client:
        client = httpx2.Client(
            transport=httpx2.MockTransport(
                lambda request: self.web.handle(request, "plain")
            ),
            max_redirects=transport.MAX_REDIRECTS,
        )
        self.api_clients.append(client)
        return client

    def new_browser(self) -> FakeBrowserSession:
        session = FakeBrowserSession(self.web)
        self.browsers.append(session)
        return session

    def set_key(self, service: str, value: str = "test-key") -> None:
        os.environ[credentials.KEYS[service].variable] = value

    def run_cli(self, *argv: str) -> Result:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.main(list(argv))
        return Result(code, stdout.getvalue(), stderr.getvalue())

    def ok(self, *argv: str) -> Result:
        result = self.run_cli(*argv)
        self.assertEqual(result.code, 0, result.stderr or result.stdout)
        return result

    def fails(self, *argv: str) -> Result:
        result = self.run_cli(*argv)
        self.assertEqual(result.code, 1, result.stdout)
        return result

    def saved(self, output: str) -> str:
        """The text of the first saved file a notice in `output` names."""
        marker = "[saved: "
        start = output.index(marker) + len(marker)
        return Path(output[start : output.index(" |", start)]).read_text()
