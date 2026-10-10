import contextlib
import gzip
import io
import sys
import tempfile
import threading
import unittest
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from research_cli import cache, cli, commands, config, firecrawl, mcp, network, pages


class FetchTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        transport = patch.object(
            httpx.HTTPTransport,
            "handle_request",
            side_effect=AssertionError("unit tests must not make live HTTP requests"),
        )
        transport.start()
        self.addCleanup(transport.stop)
        for name in ("CACHE", "OUTPUT"):
            directory = Path(temp.name) / name.lower()
            directory.mkdir()
            patcher = patch.object(config, name, directory)
            patcher.start()
            self.addCleanup(patcher.stop)

    def args(self, *tokens):
        args = cli.build_parser().parse_args(tokens)
        cli.validate_args(args)
        return args

    def capture(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            commands.fetch(args)
        return output.getvalue()

    def test_batch_is_concurrent_bounded_and_uses_one_client(self):
        args = self.args("fetch", *(f"https://example.com/{i}" for i in range(12)))
        condition = threading.Condition()
        gate = threading.Event()
        started = []
        clients = []
        active = peak = 0

        def retrieve(args, url, client):
            nonlocal active, peak
            with condition:
                started.append(url)
                clients.append(client())
                active += 1
                peak = max(peak, active)
                condition.notify_all()
            try:
                if not gate.wait(5):
                    raise RuntimeError("fetch workers did not overlap")
                return commands.FetchResult(text=url, source="direct HTTP, markdown")
            finally:
                with condition:
                    active -= 1

        with (
            patch.object(commands, "fetch_result", side_effect=retrieve),
            ThreadPoolExecutor(max_workers=1) as driver,
        ):
            future = driver.submit(self.capture, args)
            try:
                with condition:
                    self.assertTrue(
                        condition.wait_for(
                            lambda: len(started) == config.MAX_FETCH_WORKERS, timeout=5
                        )
                    )
                    self.assertEqual(peak, config.MAX_FETCH_WORKERS)
            finally:
                gate.set()
            output = future.result(timeout=5)
        self.assertEqual(Counter(started), Counter(args.urls))
        self.assertEqual(len({id(client) for client in clients}), 1)
        self.assertTrue(clients[0].is_closed)
        self.assertEqual(output.count("URL:"), len(args.urls))

    def test_pending_submissions_stay_bounded_beyond_the_first_window(self):
        urls = [f"https://example.com/{i}" for i in range(18)]
        args = self.args("fetch", *urls[:7], urls[0], *urls[7:], urls[2], urls[2])
        pending = peak = 0
        submitted = []

        class Submitted:
            def __init__(self, url):
                self.url = url

            def result(self):
                nonlocal pending
                pending -= 1
                return commands.FetchResult(
                    text=self.url, source="direct HTTP, markdown"
                )

        class TrackingExecutor:
            def __init__(self, *, max_workers):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def submit(self, function, args, url, client):
                nonlocal pending, peak
                submitted.append(url)
                pending += 1
                peak = max(peak, pending)
                return Submitted(url)

        with (
            patch.object(commands, "ThreadPoolExecutor", TrackingExecutor),
            httpx.Client() as client,
        ):
            results = list(commands.fetch_results(args, lambda: client))
        self.assertEqual([url for url, result in results], args.urls)
        self.assertEqual(submitted, urls)
        self.assertEqual(peak, config.MAX_FETCH_WORKERS)
        self.assertEqual(pending, 0)

    def test_out_of_order_completion_does_not_interleave_notices_or_output(self):
        args = self.args(
            "fetch", "https://example.com/first", "https://example.com/second"
        )
        second_done = threading.Event()

        def retrieve(args, url, client):
            if url.endswith("first"):
                if not second_done.wait(5):
                    raise RuntimeError("second fetch did not run concurrently")
            else:
                second_done.set()
            return commands.FetchResult(
                text=f"body {url}",
                source="direct HTTP, markdown",
                notices=[f"notice {url}"],
            )

        with patch.object(commands, "fetch_result", side_effect=retrieve):
            output = self.capture(args)
        self.assertEqual(
            output.splitlines(),
            [
                f"notice {args.urls[0]}",
                f"URL: {args.urls[0]} [direct HTTP, markdown]",
                f"body {args.urls[0]}",
                f"notice {args.urls[1]}",
                f"URL: {args.urls[1]} [direct HTTP, markdown]",
                f"body {args.urls[1]}",
            ],
        )

    def test_output_failure_closes_client_only_after_inflight_fetch_finishes(self):
        self.check_failure_cleanup(worker_failure=False)

    def test_worker_failure_closes_client_only_after_inflight_fetch_finishes(self):
        self.check_failure_cleanup(worker_failure=True)

    def check_failure_cleanup(self, *, worker_failure):
        args = self.args("fetch", "https://first.test", "https://second.test")
        second_started = threading.Event()
        failure_seen = threading.Event()
        release_second = threading.Event()
        client = httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200))
        )

        def retrieve(args, url, get_client):
            self.assertIs(get_client(), client)
            if url == "https://second.test":
                second_started.set()
                if not release_second.wait(5):
                    raise RuntimeError("second fetch was not released")
                self.assertFalse(client.is_closed)
            elif not second_started.wait(5):
                raise RuntimeError("second fetch did not start")
            elif worker_failure:
                failure_seen.set()
                raise RuntimeError("worker unavailable")
            return commands.FetchResult(text="page", source="direct HTTP, markdown")

        def fail_output(*args, **kwargs):
            failure_seen.set()
            raise OSError("output unavailable")

        with (
            patch.object(network, "create_client", return_value=client),
            patch.object(commands, "fetch_result", side_effect=retrieve),
            patch.object(commands, "render_response", side_effect=fail_output),
            ThreadPoolExecutor(max_workers=1) as driver,
        ):
            future = driver.submit(self.capture, args)
            try:
                self.assertTrue(failure_seen.wait(5))
                self.assertFalse(future.done())
                self.assertFalse(client.is_closed)
            finally:
                release_second.set()
            error_type = RuntimeError if worker_failure else OSError
            with self.assertRaisesRegex(error_type, "unavailable"):
                future.result(timeout=5)
        self.assertTrue(client.is_closed)

    def test_duplicate_urls_are_retrieved_once_even_when_fresh(self):
        args = self.args(
            "fetch",
            "https://one.test",
            "https://two.test",
            "https://one.test",
            "--raw",
            "--fresh",
        )

        def retrieve(service, tool, arguments, fresh, *, client):
            self.assertTrue(fresh)
            return arguments["url"]

        with patch.object(commands, "cached_call", side_effect=retrieve) as call:
            output = self.capture(args)
        self.assertEqual(call.call_count, 2)
        self.assertEqual(output.count("URL: https://one.test"), 2)
        self.assertLess(
            output.index("URL: https://one.test"), output.index("URL: https://two.test")
        )

    def test_exa_batch_deduplicates_urls_in_one_provider_call(self):
        args = self.args("fetch", "https://one.test", "https://one.test", "--exa")
        with patch.object(commands, "cached_call", return_value="page") as call:
            self.capture(args)
        call.assert_called_once()
        self.assertEqual(call.call_args.args[2]["urls"], ["https://one.test"])

    def test_invalid_exa_batch_does_not_print_notice_or_call_provider(self):
        args = self.args("fetch", "https://one.test", "not-a-url", "--exa")
        output = io.StringIO()
        with (
            patch.object(commands, "cached_call") as call,
            contextlib.redirect_stdout(output),
            self.assertRaises(config.ResearchError),
        ):
            commands.fetch(args)
        self.assertEqual(output.getvalue(), "")
        call.assert_not_called()

    def test_cached_batch_does_not_create_an_http_client(self):
        args = self.args("fetch", "https://one.test", "https://two.test")
        with patch.dict(cache.DIRECT_FETCHERS, {"page": Mock(return_value="# cached")}):
            for url in args.urls:
                cache.cached_call("page", "fetch", {"url": url})
        with patch.object(
            network, "create_client", side_effect=AssertionError("unexpected client")
        ) as create:
            output = self.capture(args)
        create.assert_not_called()
        self.assertEqual(output.count("# cached"), 2)

    def test_all_failures_raise_after_reporting_every_url(self):
        args = self.args("fetch", "https://one.test", "https://two.test", "--raw")
        output = io.StringIO()
        with (
            patch.object(
                commands, "cached_call", side_effect=config.ResearchError("failed")
            ),
            contextlib.redirect_stdout(output),
            self.assertRaisesRegex(config.ResearchError, "no URL could be fetched"),
        ):
            commands.fetch(args)
        self.assertEqual(output.getvalue().count("[error: failed"), 2)

    def test_client_creation_failure_is_reported_per_url_without_fallback(self):
        args = self.args("fetch", "https://one.test", "https://two.test")
        output = io.StringIO()
        with (
            patch.object(httpx, "Client", side_effect=OSError("no such CA bundle")),
            contextlib.redirect_stdout(output),
            self.assertRaisesRegex(config.ResearchError, "no URL could be fetched"),
        ):
            commands.fetch(args)
        self.assertEqual(
            output.getvalue().count(
                "[error: cannot create HTTP client: no such CA bundle"
            ),
            2,
        )
        self.assertNotIn("falling back", output.getvalue())

    def test_failed_duplicates_share_one_attempt_and_report_each_occurrence(self):
        for include_success in (False, True):
            with self.subTest(include_success=include_success):
                urls = ["https://failed.test"] * 3
                if include_success:
                    urls.insert(1, "https://success.test")
                args = self.args("fetch", *urls, "--raw", "--fresh")
                output = io.StringIO()

                def retrieve(service, tool, arguments, fresh, **options):
                    self.assertTrue(fresh)
                    if arguments["url"] == "https://failed.test":
                        raise config.ResearchError("failed", "try another source")
                    return "success"

                with (
                    patch.object(commands, "cached_call", side_effect=retrieve) as call,
                    contextlib.redirect_stdout(output),
                ):
                    if include_success:
                        commands.fetch(args)
                    else:
                        with self.assertRaisesRegex(
                            config.ResearchError, "no URL could be fetched"
                        ):
                            commands.fetch(args)
                self.assertEqual(call.call_count, 2 if include_success else 1)
                self.assertEqual(output.getvalue().count("[error: failed"), 3)

    def test_shared_client_propagates_through_each_cache_backend(self):
        with httpx.Client() as client:
            for service in ("raw", "page", "firecrawl", "exa"):
                with self.subTest(service=service):
                    if service in cache.DIRECT_FETCHERS:
                        call = Mock(return_value="page")
                        with patch.dict(cache.DIRECT_FETCHERS, {service: call}):
                            self.assertEqual(
                                cache.cached_call(
                                    service,
                                    "fetch",
                                    {"url": "https://one.test"},
                                    client=lambda: client,
                                ),
                                "page",
                            )
                        call.assert_called_once_with("https://one.test", client=client)
                    elif service == "firecrawl":
                        with patch.object(
                            cache, "scrape_page", return_value="page"
                        ) as call:
                            cache.cached_call(
                                service,
                                "fetch",
                                {"url": "https://one.test"},
                                client=lambda: client,
                            )
                        call.assert_called_once_with(
                            "https://one.test", fresh=False, client=client
                        )
                    else:
                        with patch.object(
                            cache, "request_tool", return_value="page"
                        ) as call:
                            cache.cached_call(
                                service,
                                "fetch",
                                {"url": "https://one.test"},
                                client=lambda: client,
                            )
                        call.assert_called_once_with(
                            service, "fetch", {"url": "https://one.test"}, client=client
                        )

    def test_compressed_page_and_raw_identity_preserve_text_and_client(self):
        text = b"  # Doc\r\nFull text\r\n"
        seen = []

        def handler(request):
            seen.append(request)
            compressed = request.headers["Accept-Encoding"] != "identity"
            headers = {"Content-Type": "text/markdown"}
            if compressed:
                headers["Content-Encoding"] = "gzip"
            return httpx.Response(
                200,
                headers=headers,
                stream=httpx.ByteStream(gzip.compress(text) if compressed else text),
            )

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            self.assertEqual(
                pages.fetch_page("https://one.test", client=client), text.decode()
            )
            self.assertEqual(
                pages.fetch_raw("https://one.test", client=client), text.decode()
            )
            self.assertFalse(client.is_closed)
        self.assertEqual(seen[0].headers["Accept-Encoding"], "gzip, deflate")
        self.assertEqual(seen[1].headers["Accept-Encoding"], "identity")
        self.assertEqual(seen[0].extensions["timeout"]["connect"], 5)
        self.assertEqual(seen[0].extensions["timeout"]["read"], 90)

    def test_size_limit_applies_to_decompressed_page(self):
        def handler(request):
            return httpx.Response(
                200,
                headers={"Content-Type": "text/markdown", "Content-Encoding": "gzip"},
                stream=httpx.ByteStream(gzip.compress(b"a" * 2048)),
            )

        with (
            httpx.Client(transport=httpx.MockTransport(handler)) as client,
            patch.object(config, "MAX_RAW_BYTES", 1024),
            self.assertRaisesRegex(config.ResearchError, "exceeds"),
        ):
            pages.fetch_page("https://one.test", client=client)

    def test_backend_timeouts_keep_service_read_budgets(self):
        for service, read in config.REQUEST_TIMEOUT_SECONDS.items():
            with self.subTest(service=service):
                timeout = network.request_timeout(service)
                self.assertEqual(timeout.connect, 5)
                self.assertEqual(timeout.read, read)

    def test_mcp_and_firecrawl_use_supplied_client(self):
        calls = []

        def handler(request):
            calls.append(request)
            if request.url.host == "api.firecrawl.dev":
                return httpx.Response(
                    200, json={"success": True, "data": {"markdown": "page"}}
                )
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "result": {"content": [{"type": "text", "text": "docs"}]},
                },
            )

        with (
            httpx.Client(transport=httpx.MockTransport(handler)) as client,
            patch.object(firecrawl, "api_key", return_value="test-key"),
        ):
            self.assertEqual(mcp.request_tool("dw", "tool", {}, client=client), "docs")
            self.assertEqual(
                firecrawl.scrape_page("https://one.test", client=client), "page"
            )
            self.assertFalse(client.is_closed)
        self.assertEqual(
            [request.extensions["timeout"]["read"] for request in calls], [240, 75]
        )

    def test_firecrawl_redirect_is_rejected_even_with_redirecting_shared_client(self):
        requests = []

        def handler(request):
            requests.append(request)
            if request.url.host == "api.firecrawl.dev":
                return httpx.Response(
                    302, headers={"Location": "https://other.test/scrape"}
                )
            return httpx.Response(
                200, json={"success": True, "data": {"markdown": "page"}}
            )

        with (
            httpx.Client(
                transport=httpx.MockTransport(handler), follow_redirects=True
            ) as client,
            patch.object(firecrawl, "api_key", return_value="test-key"),
            self.assertRaisesRegex(config.ResearchError, "HTTP 302"),
        ):
            firecrawl.scrape_page("https://one.test", client=client)
        self.assertEqual(len(requests), 1)

    def test_mcp_redirect_does_not_forward_custom_api_keys(self):
        for service, header in (("exa", "x-api-key"), ("c7", "CONTEXT7_API_KEY")):
            for target in (
                "https://other.test/mcp",
                "http://same.test/mcp",
                "https://same.test:8443/mcp",
            ):
                with self.subTest(service=service, target=target):
                    requests = []

                    def handler(request, requests=requests, target=target):
                        requests.append(request)
                        return httpx.Response(307, headers={"Location": target})

                    with (
                        httpx.Client(
                            transport=httpx.MockTransport(handler),
                            follow_redirects=True,
                        ) as client,
                        patch.dict(
                            config.ENDPOINTS, {service: "https://same.test/mcp"}
                        ),
                        patch.object(mcp, "api_key", return_value="test-key"),
                        self.assertRaisesRegex(
                            config.ResearchError, "cross-origin redirect refused"
                        ) as caught,
                    ):
                        mcp.request_tool(service, "tool", {}, client=client)
                    self.assertEqual(len(requests), 1)
                    self.assertEqual(requests[0].headers[header], "test-key")
                    self.assertIn("canonical MCP endpoint", caught.exception.hint)

    def test_mcp_same_origin_redirect_keeps_method_body_and_key(self):
        requests = []

        def handler(request):
            requests.append(request)
            if request.url.path == "/mcp":
                return httpx.Response(307, headers={"Location": "/canonical"})
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "result": {"content": [{"type": "text", "text": "docs"}]},
                },
            )

        with (
            httpx.Client(transport=httpx.MockTransport(handler)) as client,
            patch.dict(config.ENDPOINTS, {"exa": "https://same.test/mcp"}),
            patch.object(mcp, "api_key", return_value="test-key"),
        ):
            self.assertEqual(mcp.request_tool("exa", "tool", {}, client=client), "docs")
            self.assertFalse(client.is_closed)
        self.assertEqual(len(requests), 2)
        self.assertEqual([request.method for request in requests], ["POST", "POST"])
        self.assertEqual(requests[0].content, requests[1].content)
        self.assertEqual(
            [request.headers["x-api-key"] for request in requests],
            ["test-key", "test-key"],
        )

    def test_html_anchor_without_value_does_not_crash(self):
        html = (
            "<html><body><main><a href>anchor</a><p>"
            + "body " * 50
            + "</p></main></body></html>"
        )
        self.assertIn("anchor", pages.html_to_markdown(html, "https://one.test"))


if __name__ == "__main__":
    unittest.main()
