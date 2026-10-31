"""The real curl_cffi and httpx2 clients against a local HTTP server."""

import contextlib
import gzip
import socket
import tempfile
import threading
import time
import unittest
import zlib
from collections.abc import Callable
from compression import zstd
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from research_cli import config, health
from research_cli.errors import ResearchError
from research_cli.transport import Http

TEXT = b"  # Doc\r\n" + b"Content with spacing.  \r\n" * 100
ENCODERS: dict[str, Callable[[bytes], bytes]] = {
    "gzip": gzip.compress,
    "deflate": zlib.compress,
    "zstd": zstd.compress,
}


class Handler(BaseHTTPRequestHandler):
    """Paths: /<encoding>, /bomb, /pdf, /nul, /redirect, /picky, /blocked, /gone,
    /slow."""

    seen: list[tuple[str, dict[str, str]]]

    def log_message(self, format: str, *args: object) -> None:
        pass

    def reply(
        self, status: int, body: bytes, content_type: str, encoding: str = ""
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if encoding:
            self.send_header("Content-Encoding", encoding)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        # The client may stop reading at its size cap.
        with contextlib.suppress(BrokenPipeError):
            self.wfile.write(body)

    def do_GET(self) -> None:
        self.seen.append((self.path, dict(self.headers)))
        path = self.path.strip("/")
        agent = self.headers.get("User-Agent", "")
        if path in ENCODERS:
            self.reply(200, ENCODERS[path](TEXT), "text/markdown; charset=utf-8", path)
        elif path == "bomb":
            self.reply(200, gzip.compress(b"a" * 4096), "text/plain", "gzip")
        elif path == "broken-gzip":
            self.reply(200, b"not gzip at all", "text/html", "gzip")
        elif path == "pdf":
            self.reply(200, b"%PDF-1.7" + b"\x00" * 1000, "application/pdf")
        elif path == "nul":
            self.reply(200, b"text\x00more", "text/plain")
        elif path == "latin":
            self.reply(200, "café".encode("latin-1"), "text/plain; charset=iso-8859-1")
        elif path == "redirect":
            self.send_response(302)
            self.send_header("Location", "/gzip")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif path == "picky":  # refuses browser fingerprints, serves honest clients
            if agent.startswith("research-cli/"):
                self.reply(200, b"served", "text/plain")
            else:
                self.reply(403, b"denied", "text/html")
        elif path == "blocked":
            self.reply(403, b"denied", "text/html")
        elif path == "gone":
            self.reply(404, b"missing", "text/html")
        elif path == "slow":  # outlasts the client, which hangs up first
            time.sleep(3)
            with contextlib.suppress(OSError):
                self.reply(200, b"late", "text/plain")
        else:
            self.reply(500, b"unknown path", "text/plain")


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.seen: list[tuple[str, dict[str, str]]] = []
        handler = type("BoundHandler", (Handler,), {"seen": cls.seen})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self) -> None:
        self.seen.clear()
        self.http = Http()
        self.addCleanup(self.http.close)
        cache = tempfile.TemporaryDirectory()
        self.addCleanup(cache.cleanup)
        patcher = patch.object(config, "CACHE", Path(cache.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def download(self, path: str, *, impersonate: bool = True) -> bytes:
        return self.http.download(self.base + path, impersonate=impersonate).body

    def test_both_clients_decompress_every_encoding_preserving_text(self):
        for impersonate in (True, False):
            for encoding in ENCODERS:
                with self.subTest(impersonate=impersonate, encoding=encoding):
                    self.assertEqual(
                        self.download(f"/{encoding}", impersonate=impersonate), TEXT
                    )

    def test_size_cap_applies_to_decompressed_bytes_and_is_final(self):
        for impersonate in (True, False):
            with (
                self.subTest(impersonate=impersonate),
                patch.object(config, "MAX_BODY_BYTES", 1024),
                self.assertRaises(ResearchError) as raised,
            ):
                self.download("/bomb", impersonate=impersonate)
            self.assertTrue(raised.exception.final)
            self.assertIn("exceeds", raised.exception.message)

    def test_documents_are_rejected_by_type_and_binary_by_content(self):
        with self.assertRaisesRegex(
            ResearchError, "expected text, got application/pdf"
        ):
            self.download("/pdf")
        download = self.http.download(self.base + "/nul")
        with self.assertRaisesRegex(ResearchError, "binary"):
            download.text()

    def test_declared_charset_decodes_the_body(self):
        self.assertEqual(self.http.download(self.base + "/latin").text(), "café")

    def test_redirects_report_the_final_url(self):
        for impersonate in (True, False):
            with self.subTest(impersonate=impersonate):
                download = self.http.download(
                    self.base + "/redirect", impersonate=impersonate
                )
                self.assertEqual(download.url, self.base + "/gzip")

    def test_refused_browser_fingerprint_falls_back_to_the_plain_client(self):
        self.assertEqual(self.download("/picky"), b"served")
        agents = [headers["User-Agent"] for _, headers in self.seen]
        self.assertIn("Chrome", agents[0])
        self.assertTrue(agents[1].startswith("research-cli/"))

    def test_refusal_by_both_clients_says_so_and_stays_recoverable(self):
        with self.assertRaises(ResearchError) as raised:
            self.download("/blocked")
        self.assertEqual(
            raised.exception.message, "HTTP 403 (browser and plain clients)"
        )
        self.assertEqual(raised.exception.status, 403)
        self.assertFalse(raised.exception.final)

    def test_missing_page_is_final_without_a_second_client(self):
        with self.assertRaises(ResearchError) as raised:
            self.download("/gone")
        self.assertTrue(raised.exception.final)
        self.assertEqual(len(self.seen), 1)

    def test_browser_keeps_markdown_negotiation_and_browser_encodings(self):
        self.http.download(self.base + "/gzip", accept="text/markdown, */*;q=0.5")
        headers = self.seen[0][1]
        self.assertEqual(headers["Accept"], "text/markdown, */*;q=0.5")
        self.assertIn("zstd", headers["Accept-Encoding"])

    def test_invalid_compressed_body_is_a_recoverable_error(self):
        for impersonate in (True, False):
            with (
                self.subTest(impersonate=impersonate),
                self.assertRaises(ResearchError) as raised,
            ):
                self.download("/broken-gzip", impersonate=impersonate)
            self.assertFalse(raised.exception.final)

    def test_read_timeout_is_reported_once_not_retried(self):
        for impersonate in (True, False):
            with (
                self.subTest(impersonate=impersonate),
                # A streamed curl read times out after connect + read seconds,
                # rounded up, without data.
                patch.dict(config.TIMEOUT_SECONDS, {"page": 0.5}),
                patch.object(config, "CONNECT_TIMEOUTS_SECONDS", (0.2, 0.2, 0.4)),
                self.assertRaises(ResearchError) as raised,
            ):
                self.seen.clear()
                self.download("/slow", impersonate=impersonate)
            self.assertEqual(raised.exception.message, "no response within 0.5s")
            self.assertEqual(len(self.seen), 1)

    def test_unreachable_host_is_reported_not_raised_as_oserror(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        with self.assertRaises(ResearchError):
            self.http.download(f"http://127.0.0.1:{port}/")


class SilentTlsServer:
    """Accepts TCP connections and never answers the TLS handshake.

    Some networks drop handshakes to particular hosts this way: the TCP
    connect succeeds and the server's reply to the ClientHello never arrives.
    """

    def __init__(self) -> None:
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.url = f"https://127.0.0.1:{self.listener.getsockname()[1]}/file"
        self.accepted: list[socket.socket] = []
        threading.Thread(target=self.accept, daemon=True).start()

    def accept(self) -> None:
        with contextlib.suppress(OSError):
            while True:
                self.accepted.append(self.listener.accept()[0])

    def hang_up(self) -> None:
        for connection in self.accepted:
            connection.close()
        self.accepted.clear()

    def close(self) -> None:
        self.listener.close()
        self.hang_up()


class StallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = SilentTlsServer()
        self.addCleanup(self.server.close)
        self.http = Http()
        self.addCleanup(self.http.close)
        cache = tempfile.TemporaryDirectory()
        self.addCleanup(cache.cleanup)
        for patcher in (
            patch.object(config, "CACHE", Path(cache.name)),
            patch.object(config, "CONNECT_TIMEOUTS_SECONDS", (0.2, 0.2, 0.4)),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_stalled_handshakes_are_retried_then_reported_as_stalls(self):
        for impersonate in (True, False):
            with self.subTest(impersonate=impersonate):
                self.server.hang_up()
                started = time.monotonic()
                with self.assertRaises(ResearchError) as raised:
                    self.http.download(self.server.url, impersonate=impersonate)
                self.assertLess(time.monotonic() - started, 3)
                self.assertEqual(
                    raised.exception.message,
                    "connection to 127.0.0.1 stalled: no TCP/TLS handshake "
                    "in 3 attempts (0.8s)",
                )
                self.assertFalse(raised.exception.final)
                self.assertEqual(len(self.server.accepted), 3)
        self.assertTrue(health.stalled_recently("127.0.0.1"))

    def test_api_calls_retry_stalled_handshakes(self):
        with self.assertRaises(ResearchError) as raised:
            self.http.call_api(
                "github", "GET", self.server.url, label="GitHub API", hint="retry"
            )
        self.assertTrue(raised.exception.message.startswith("GitHub API: connection"))
        self.assertEqual(len(self.server.accepted), 3)


if __name__ == "__main__":
    unittest.main()
