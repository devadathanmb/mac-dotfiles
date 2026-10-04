import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from research_cli import (
    cache,
    cli,
    commands,
    config,
    credentials,
    firecrawl,
    mcp,
    pages,
)
from research_cli import output as out


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        transport = patch.object(
            httpx.HTTPTransport,
            "handle_request",
            side_effect=AssertionError("unit tests must not make live HTTP requests"),
        )
        transport.start()
        self.addCleanup(transport.stop)
        root = Path(self.temp.name)
        for name in ("CACHE", "OUTPUT"):
            directory = root / name.lower()
            directory.mkdir()
            patcher = patch.object(config, name, directory)
            patcher.start()
            self.addCleanup(patcher.stop)

    def args(self, *tokens):
        args = cli.build_parser().parse_args(tokens)
        cli.validate_args(args)
        return args

    def capture(self, callback, *args, **kwargs):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = callback(*args, **kwargs)
        return result, output.getvalue()

    def test_common_options_before_and_after_command(self):
        args = self.args("--max-chars", "12", "web", "query", "--context", "1")
        self.assertEqual((args.max_chars, args.context), (12, 1))
        self.assertEqual(self.args("web", "query").max_chars, 4000)

    def test_invalid_arguments_rejected_before_network(self):
        cases = [
            ("docs", "/encode/httpx"),
            ("docs", "/encode/httpx", "question", "--list"),
            ("web", "q", "-n", "0"),
            ("web", "q", "-n", "101"),
            ("web", "q", "--chars", "0"),
            ("fetch", "https://example.com", "--chars", "-1"),
            ("web", "q", "--max-chars", "-1"),
            ("web", "q", "--context", "-1"),
            ("web", "q", "--match", "["),
            ("web", "q", "--after", "2026-02-30"),
            ("web", "q", "--after", "20261001"),
            ("web", "q", "--after", "2026-10-01", "--before", "2026-09-01"),
            ("web", "q", "--objective", "goal", "--domain", "example.com"),
            ("web", "q", "--objective", "goal", "--chars", "100"),
            ("wiki", "ask", "owner/repo"),
            ("wiki", "ask", "owner/repo", " "),
            ("wiki", "ask", "not-a-repo", "q"),
            ("wiki", "ask", ",".join(["owner/repo"] * 11), "q"),
            ("wiki", "outline", "owner/repo", "ignored question"),
            ("wiki", "read", "one/repo,two/repo"),
        ]
        for tokens in cases:
            with self.subTest(tokens=tokens), self.assertRaises(config.ResearchError):
                self.args(*tokens)

    def test_current_exa_categories(self):
        for category in ("publication", "people", "financial report", "github"):
            self.args("web", "query", "--category", category)

    def test_explicit_chars_selects_advanced_search(self):
        args = self.args("web", "query", "--chars", "321")
        with patch.object(commands, "cached_call", return_value="result") as call:
            self.capture(commands.web, args)
        self.assertEqual(call.call_args.args[1], "web_search_advanced_exa")
        self.assertEqual(call.call_args.args[2]["textMaxCharacters"], 321)

    def test_basic_search_preserves_objective(self):
        args = self.args("web", "query", "--objective", "goal")
        with patch.object(commands, "cached_call", return_value="result") as call:
            self.capture(commands.web, args)
        self.assertEqual(call.call_args.args[1], "web_search_exa")
        self.assertEqual(call.call_args.args[2]["objective"], "goal")

    def test_filtered_search_default_extraction_limit(self):
        args = self.args("web", "query", "--domain", "example.com")
        with patch.object(commands, "cached_call", return_value="result") as call:
            self.capture(commands.web, args)
        self.assertEqual(call.call_args.args[2]["textMaxCharacters"], 1500)

    def test_short_response_stays_inline(self):
        args = self.args("web", "query")
        used, output = self.capture(out.emit_response, "short", args, "test")
        self.assertEqual((used, output), (5, "short\n"))
        self.assertEqual(list(config.OUTPUT.iterdir()), [])

    def test_large_response_saved_with_bounded_preview(self):
        args = self.args("web", "query", "--max-chars", "20")
        text = "a" * 100
        used, output = self.capture(out.emit_response, text, args, "test")
        self.assertEqual(used, 20)
        self.assertTrue(output.startswith("[saved:"))
        self.assertTrue(output.rstrip().endswith("a" * 20))
        self.assertEqual(next(config.OUTPUT.iterdir()).read_text(), text + "\n")

    def test_no_match_still_saves_full_response(self):
        args = self.args("web", "query", "--match", "missing")
        _, output = self.capture(out.emit_response, "full response", args, "test")
        self.assertIn("No matching lines", output)
        self.assertEqual(next(config.OUTPUT.iterdir()).read_text(), "full response\n")

    def test_matching_lines_merge_context_and_keep_source_numbers(self):
        text = "a\nb\nmatch\nd\nmatch\nf\ng\nh\nmatch"
        self.assertEqual(
            out.matching_lines(text, re.compile("match"), 1),
            "2: b\n3: match\n4: d\n5: match\n6: f\n...\n8: h\n9: match",
        )

    def test_raw_batch_shares_preview_budget_and_preserves_files(self):
        args = self.args(
            "fetch",
            "--raw",
            "https://one.test",
            "https://two.test",
            "--max-chars",
            "20",
        )

        def retrieve(service, tool, arguments, fresh, **options):
            return ("a" if arguments["url"] == "https://one.test" else "b") * 40

        with patch.object(commands, "cached_call", side_effect=retrieve):
            _, output = self.capture(commands.fetch, args)
        self.assertIn("a" * 20, output)
        self.assertNotIn("b" * 20, output)
        self.assertIn("preview 0/40", output)
        self.assertEqual(len(list(config.OUTPUT.iterdir())), 2)
        self.assertEqual(
            {path.read_text() for path in config.OUTPUT.iterdir()},
            {"a" * 40, "b" * 40},
        )

    def test_unlimited_preview_is_explicit(self):
        args = self.args("web", "query", "--max-chars", "0")
        used, output = self.capture(out.emit_response, "a" * 5000, args, "test")
        self.assertEqual(used, 5000)
        self.assertNotIn("[saved:", output)

    def test_cache_hit_fresh_and_atomic_write(self):
        with patch.object(
            cache, "request_tool", side_effect=["first", "second"]
        ) as call:
            self.assertEqual(cache.cached_call("exa", "tool", {"q": "x"}), "first")
            self.assertEqual(cache.cached_call("exa", "tool", {"q": "x"}), "first")
            self.assertEqual(
                cache.cached_call("exa", "tool", {"q": "x"}, True), "second"
            )
        self.assertEqual(call.call_count, 2)
        self.assertEqual(len(list(config.CACHE.iterdir())), 1)

    def test_failed_response_is_not_cached(self):
        with (
            patch.object(
                cache, "request_tool", side_effect=config.ResearchError("failed")
            ),
            self.assertRaises(config.ResearchError),
        ):
            cache.cached_call("exa", "tool", {})
        self.assertEqual(list(config.CACHE.iterdir()), [])

    def test_raw_cache_preserves_line_endings(self):
        text = "first\r\nlast\r\n"
        fetch = Mock(return_value=text)
        with patch.dict(cache.DIRECT_FETCHERS, {"raw": fetch}):
            self.assertEqual(
                cache.cached_call("raw", "fetch", {"url": "https://example.com"}),
                text,
            )
            self.assertEqual(
                cache.cached_call("raw", "fetch", {"url": "https://example.com"}),
                text,
            )
        self.assertEqual(fetch.call_count, 1)

    def test_html_converts_to_main_content_markdown(self):
        html = (
            "<html><head><title>t</title><script>var x=1</script></head><body>"
            "<nav><a href='/nav'>Navigation</a></nav>"
            "<main><h1>Title</h1><p>" + "Body text. " * 30 + "</p>"
            "<a href='/guide'>guide</a> <a href='#frag'>frag</a>"
            "<pre><code>print('hi')</code></pre><img src='x.png' alt='pic'></main>"
            "<footer>Copyright</footer></body></html>"
        )
        markdown = pages.html_to_markdown(html, "https://example.com/docs/")
        self.assertIn("# Title", markdown)
        self.assertIn("(https://example.com/guide)", markdown)
        self.assertIn("(#frag)", markdown)
        self.assertIn("```", markdown)
        for noise in ("Navigation", "Copyright", "var x", "x.png"):
            self.assertNotIn(noise, markdown)

    def test_fetch_page_passes_markdown_through_and_rejects_empty_html(self):
        with patch.object(pages, "download", return_value=("# Doc\n", "text/markdown")):
            self.assertEqual(pages.fetch_page("https://example.com"), "# Doc\n")
        shell = "<html><body><div id='root'></div><script>app()</script></body></html>"
        with (
            patch.object(pages, "download", return_value=(shell, "text/html")),
            self.assertRaisesRegex(config.ResearchError, "little static content"),
        ):
            pages.fetch_page("https://example.com")

    def test_fetch_page_pretty_prints_json(self):
        with patch.object(
            pages, "download", return_value=('{"a":{"b":1}}', "application/json")
        ):
            self.assertEqual(
                pages.fetch_page("https://example.com/x"),
                '{\n  "a": {\n    "b": 1\n  }\n}',
            )

    def test_code_prepends_compact_index(self):
        hit = "Repository: o/{n}\nPath: src/{n}.tsx\nURL: u\nLicense: MIT\n\nSnippets:\n--- Snippet 1 (Line {l}) ---\n  code\n\n"
        result = hit.format(n="a", l=5) + hit.format(n="b", l=9)
        index = commands.code_index(result)
        self.assertIn("Index (2 hits):", index)
        self.assertIn("o/a src/a.tsx:5", index)
        self.assertIn("o/b src/b.tsx:9", index)
        self.assertEqual(commands.code_index(hit.format(n="a", l=5)), "")

    def test_fetch_defaults_to_direct_markdown(self):
        args = self.args("fetch", "https://example.com")
        with patch.object(commands, "cached_call", return_value="# Page") as call:
            _, output = self.capture(commands.fetch, args)
        self.assertEqual(call.call_args.args[:2], ("page", "fetch"))
        self.assertIn("[direct HTTP, markdown]", output)

    def test_fetch_falls_back_to_exa_per_url(self):
        args = self.args("fetch", "https://example.com")
        with patch.object(
            commands,
            "cached_call",
            side_effect=[config.ResearchError("blocked"), "exa text"],
        ) as call:
            _, output = self.capture(commands.fetch, args)
        self.assertEqual(call.call_args.args[:2], ("exa", "web_fetch_exa"))
        self.assertIn("falling back to Exa", output)
        self.assertIn("exa text", output)

    def test_fetch_404_skips_exa_and_continues_batch(self):
        args = self.args("fetch", "https://a.test/x", "https://b.test/y")
        missing = config.ResearchError("HTTP 404", "fix the URL", final=True)

        def retrieve(service, tool, arguments, fresh, **options):
            if arguments["url"] == "https://a.test/x":
                raise missing
            return "# Page"

        with patch.object(commands, "cached_call", side_effect=retrieve) as call:
            _, output = self.capture(commands.fetch, args)
        self.assertEqual([c.args[0] for c in call.call_args_list], ["page", "page"])
        self.assertIn("[error: HTTP 404", output)
        self.assertIn("# Page", output)
        with (
            patch.object(commands, "cached_call", side_effect=missing),
            self.assertRaises(config.ResearchError),
        ):
            self.capture(commands.fetch, self.args("fetch", "https://a.test/x"))

    def test_fetch_exa_flag_skips_direct_fetch(self):
        args = self.args("fetch", "--exa", "https://example.com")
        with patch.object(commands, "cached_call", return_value="exa text") as call:
            self.capture(commands.fetch, args)
        call.assert_called_once()
        self.assertEqual(call.call_args.args[1], "web_fetch_exa")
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.args("fetch", "--raw", "--exa", "https://example.com")

    def test_fetch_firecrawl_flag_skips_other_backends(self):
        args = self.args("fetch", "--firecrawl", "https://example.com")
        with patch.object(commands, "cached_call", return_value="# Page") as call:
            _, output = self.capture(commands.fetch, args)
        self.assertEqual(
            call.call_args.args,
            ("firecrawl", "scrape", {"url": "https://example.com"}, False),
        )
        self.assertTrue(callable(call.call_args.kwargs["client"]))
        self.assertIn("[Firecrawl]", output)
        for other in ("--raw", "--exa"):
            with (
                self.assertRaises(SystemExit),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                self.args("fetch", "--firecrawl", other, "https://example.com")

    def test_fetch_falls_back_to_firecrawl_after_exa_failure(self):
        args = self.args("fetch", "https://example.com", "--fresh")
        with (
            patch.object(commands, "api_key", return_value="test-key"),
            patch.object(
                commands,
                "cached_call",
                side_effect=[
                    config.ResearchError("blocked"),
                    config.ResearchError("Exa blocked"),
                    "# Scraped page",
                ],
            ) as call,
        ):
            _, output = self.capture(commands.fetch, args)
        self.assertEqual(
            [c.args[0] for c in call.call_args_list], ["page", "exa", "firecrawl"]
        )
        self.assertTrue(call.call_args.args[3])
        self.assertIn("falling back to Firecrawl", output)

    def test_fetch_skips_unconfigured_firecrawl_and_continues_batch(self):
        args = self.args("fetch", "https://one.test", "https://two.test")

        def retrieve(service, tool, arguments, fresh, **options):
            if arguments.get("url") == "https://two.test":
                return "# Second page"
            raise config.ResearchError("blocked" if service == "page" else "Exa failed")

        with (
            patch.object(commands, "api_key", return_value=None),
            patch.object(
                commands,
                "cached_call",
                side_effect=retrieve,
            ) as call,
        ):
            _, output = self.capture(commands.fetch, args)
        self.assertCountEqual(
            [c.args[0] for c in call.call_args_list], ["page", "exa", "page"]
        )
        self.assertIn("# Second page", output)

    def test_firecrawl_request_returns_markdown_and_bypasses_provider_cache(self):
        response = httpx.Response(
            200,
            json={
                "success": True,
                "data": {"markdown": " # Page\n", "metadata": {"statusCode": 200}},
            },
            request=httpx.Request("POST", "https://api.firecrawl.dev/v2/scrape"),
        )
        with (
            patch.object(firecrawl, "api_key", return_value="test-key"),
            patch.object(httpx, "post", return_value=response) as post,
        ):
            self.assertEqual(
                firecrawl.scrape_page("https://example.com", True), "# Page"
            )
        self.assertEqual(post.call_args.kwargs["json"]["maxAge"], 0)
        self.assertEqual(post.call_args.kwargs["json"]["formats"], ["markdown"])
        self.assertEqual(
            post.call_args.kwargs["headers"], {"Authorization": "Bearer test-key"}
        )

    def test_firecrawl_default_request_allows_provider_cache(self):
        response = httpx.Response(
            200,
            json={"success": True, "data": {"markdown": "# Page"}},
            request=httpx.Request("POST", "https://api.firecrawl.dev/v2/scrape"),
        )
        with (
            patch.object(firecrawl, "api_key", return_value="test-key"),
            patch.object(httpx, "post", return_value=response) as post,
        ):
            firecrawl.scrape_page("https://example.com")
        self.assertNotIn("maxAge", post.call_args.kwargs["json"])

    def test_firecrawl_rejects_failed_empty_and_blocked_results(self):
        results = [
            [],
            {"success": False},
            {"success": True, "data": []},
            {"success": True, "data": {}},
            {"success": True, "data": {"markdown": "  "}},
            {
                "success": True,
                "data": {"markdown": "blocked", "metadata": {"statusCode": 403}},
            },
        ]
        for result in results:
            response = httpx.Response(
                200,
                json=result,
                request=httpx.Request("POST", "https://api.firecrawl.dev/v2/scrape"),
            )
            with (
                self.subTest(result=result),
                patch.object(firecrawl, "api_key", return_value="test-key"),
                patch.object(httpx, "post", return_value=response),
                self.assertRaises(config.ResearchError),
            ):
                firecrawl.scrape_page("https://example.com")

    def test_firecrawl_missing_key_and_timeout_do_not_retry(self):
        with (
            patch.object(firecrawl, "api_key", return_value=None),
            patch.object(httpx, "post") as post,
            self.assertRaisesRegex(config.ResearchError, "key not configured"),
        ):
            firecrawl.scrape_page("https://example.com")
        post.assert_not_called()
        with (
            patch.object(firecrawl, "api_key", return_value="test-key"),
            patch.object(
                httpx, "post", side_effect=httpx.ReadTimeout("timeout")
            ) as post,
            self.assertRaisesRegex(config.ResearchError, "timeout"),
        ):
            firecrawl.scrape_page("https://example.com")
        self.assertEqual(post.call_count, 1)

    def test_firecrawl_cache_dispatch_preserves_fresh(self):
        with patch.object(cache, "scrape_page", return_value="# Page") as scrape:
            args = ("firecrawl", "scrape", {"url": "https://example.com"})
            cache.cached_call(*args)
            cache.cached_call(*args)
            cache.cached_call(*args, fresh=True)
        self.assertEqual(scrape.call_count, 2)
        scrape.assert_called_with("https://example.com", fresh=True)

    def test_firecrawl_http_errors_are_actionable_and_redact_response(self):
        cases = {
            401: "check",
            402: "credits exhausted",
            429: "rate limited",
            500: "another source",
        }
        for status, hint in cases.items():
            response = httpx.Response(
                status,
                text="provider echoed secret-key",
                request=httpx.Request("POST", "https://api.firecrawl.dev/v2/scrape"),
            )
            with (
                self.subTest(status=status),
                patch.object(firecrawl, "api_key", return_value="secret-key"),
                patch.object(httpx, "post", return_value=response) as post,
                self.assertRaises(config.ResearchError) as caught,
            ):
                firecrawl.scrape_page("https://example.com")
            self.assertIn(f"HTTP {status}", str(caught.exception))
            self.assertIn(hint, caught.exception.hint)
            self.assertNotIn("secret-key", str(caught.exception))
            self.assertEqual(post.call_count, 1)

    def test_firecrawl_bad_json_and_network_error_are_concise(self):
        response = httpx.Response(
            200,
            text="not JSON",
            request=httpx.Request("POST", "https://api.firecrawl.dev/v2/scrape"),
        )
        for failure in (None, httpx.ConnectError("network unavailable")):
            with (
                self.subTest(failure=failure),
                patch.object(firecrawl, "api_key", return_value="test-key"),
                patch.object(httpx, "post", return_value=response, side_effect=failure),
                self.assertRaisesRegex(
                    config.ResearchError, "request or response failed"
                ),
            ):
                firecrawl.scrape_page("https://example.com")

    def test_invalid_fetch_urls_never_reach_providers(self):
        urls = (
            "file:///etc/passwd",
            "https://user:secret@example.com",
            "https://[",
            "not-a-url",
        )
        for url in urls:
            for mode in ((), ("--raw",), ("--exa",), ("--firecrawl",)):
                args = self.args("fetch", url, *mode)
                with (
                    self.subTest(url=url, mode=mode),
                    patch.object(commands, "cached_call") as call,
                    self.assertRaises(config.ResearchError),
                ):
                    self.capture(commands.fetch, args)
                call.assert_not_called()

    def test_firecrawl_failure_does_not_abort_next_url(self):
        args = self.args("fetch", "--firecrawl", "https://one.test", "https://two.test")

        def retrieve(service, tool, arguments, fresh, **options):
            if arguments["url"] == "https://one.test":
                raise config.ResearchError("blocked")
            return "# Page"

        with patch.object(
            commands,
            "cached_call",
            side_effect=retrieve,
        ) as call:
            _, output = self.capture(commands.fetch, args)
        self.assertEqual(call.call_count, 2)
        self.assertIn("[error: blocked", output)
        self.assertIn("# Page", output)

    def test_firecrawl_failure_is_not_cached(self):
        with (
            patch.object(
                cache, "scrape_page", side_effect=config.ResearchError("blocked")
            ),
            self.assertRaises(config.ResearchError),
        ):
            cache.cached_call("firecrawl", "scrape", {"url": "https://example.com"})
        self.assertEqual(list(config.CACHE.iterdir()), [])

    def test_api_key_environment_precedence_and_file_fallback(self):
        secrets = Path(self.temp.name) / "secrets"
        secrets.mkdir()
        (secrets / "test-key").write_text(" file-key\n")
        with patch.object(credentials, "SECRETS", secrets):
            for value, expected in (
                (" env-key ", "env-key"),
                ("  ", "file-key"),
                ("", "file-key"),
            ):
                with (
                    self.subTest(value=value),
                    patch.dict("os.environ", {"TEST_API_KEY": value}),
                ):
                    self.assertEqual(
                        credentials.api_key("TEST_API_KEY", "test-key"), expected
                    )
            with patch.dict("os.environ", {}, clear=True):
                self.assertIsNone(credentials.api_key("TEST_API_KEY", "missing"))

    def test_fetch_page_rejects_loading_error_placeholder(self):
        html = (
            "<html><body>A required part of this site couldn’t load. "
            "This may be due to a browser extension, network issues, or browser settings. "
            "Please check your connection, disable any ad blockers, or try using a "
            "different browser.</body></html>"
        )
        with (
            patch.object(pages, "download", return_value=(html, "text/html")),
            self.assertRaisesRegex(config.ResearchError, "loading error"),
        ):
            pages.fetch_page("https://example.com")

    def test_code_without_matches_gives_actionable_error(self):
        args = self.args("code", "nope(", "--repo", "a/b")
        with (
            patch.object(
                commands,
                "cached_call",
                return_value="No results found for your query.\n",
            ),
            self.assertRaisesRegex(config.ResearchError, "no matches") as caught,
        ):
            commands.code(args)
        self.assertIn("drop --repo", caught.exception.hint)

    def test_json_and_sse_tool_responses(self):
        response = json.dumps(
            {"id": 1, "result": {"content": [{"type": "text", "text": "ok"}]}}
        )
        for body in (
            response,
            'data: {"method":"notification"}\n\ndata: ' + response + "\n\n",
        ):
            self.assertEqual(mcp.parse_tool_response(body, "tool"), "ok")

    def test_tool_errors_and_empty_responses(self):
        responses = [
            {"id": 1, "error": {"message": "failed"}},
            {
                "id": 1,
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": "failed"}],
                },
            },
            {"id": 1, "result": {"content": []}},
        ]
        for response in responses:
            with (
                self.subTest(response=response),
                self.assertRaises(config.ResearchError),
            ):
                mcp.parse_tool_response(json.dumps(response), "tool")

    def test_timeout_does_not_repeat_expensive_call(self):
        with (
            patch.object(
                httpx.Client, "post", side_effect=httpx.ReadTimeout("timeout")
            ) as post,
            self.assertRaisesRegex(config.ResearchError, "timeout"),
        ):
            mcp.request_tool("dw", "ask_wiki_question", {})
        self.assertEqual(post.call_count, 1)

    def test_raw_fetch_rejects_credentials_and_non_http(self):
        for url in ("file:///etc/passwd", "https://user:pass@example.com", "not-a-url"):
            with self.subTest(url=url), self.assertRaises(config.ResearchError):
                pages.fetch_raw(url)

    def test_raw_fetch_ignores_extraction_limit(self):
        self.args("fetch", "--raw", "https://example.com", "--chars", "0")

    def test_raw_fetch_preserves_text_exactly(self):
        response = httpx.Response(
            200,
            content=b"  first\r\nlast\n\n",
            headers={"Content-Type": "text/plain"},
            request=httpx.Request("GET", "https://example.com"),
        )
        with patch.object(
            httpx.Client, "stream", return_value=contextlib.nullcontext(response)
        ):
            self.assertEqual(
                pages.fetch_raw("https://example.com"), "  first\r\nlast\n\n"
            )

    def test_raw_fetch_rejects_binary_and_oversized_text(self):
        cases = [
            (b"binary\x00", "application/octet-stream", 100),
            (b"pdf", "application/pdf", 100),
            (b"too long", "text/plain", 4),
        ]
        for body, mime, limit in cases:
            response = httpx.Response(
                200,
                content=body,
                headers={"Content-Type": mime},
                request=httpx.Request("GET", "https://example.com"),
            )
            with (
                self.subTest(mime=mime, limit=limit),
                patch.object(
                    httpx.Client,
                    "stream",
                    return_value=contextlib.nullcontext(response),
                ),
                patch.object(config, "MAX_RAW_BYTES", limit),
                self.assertRaises(config.ResearchError),
            ):
                pages.fetch_raw("https://example.com")

    def test_filesystem_errors_are_concise(self):
        stderr = io.StringIO()
        with (
            patch.object(sys, "argv", ["research", "web", "query"]),
            patch.object(
                cli,
                "remove_expired_files",
                side_effect=PermissionError("no access"),
            ),
            contextlib.redirect_stderr(stderr),
        ):
            self.assertEqual(cli.main(), 1)
        self.assertIn("error: no access | hint:", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_direct_docs_emit_selected_id(self):
        args = self.args("docs", "/encode/httpx", "timeout defaults")
        with patch.object(commands, "cached_call", return_value="answer"):
            _, output = self.capture(commands.docs, args)
        self.assertTrue(output.startswith("# Context7: /encode/httpx\n"))

    def library_result(self, index=0, versions="v14.0.0, v15.0.0"):
        return (
            f"- Title: Next.js {index}\n"
            f"- Context7-compatible library ID: /vercel/next{index}\n"
            "- Description: Full-stack React framework\n"
            "- Code Snippets: 5115\n"
            "- Source Reputation: High\n"
            "- Benchmark Score: 89.01\n"
            f"- Versions: {versions}\n----------"
        )

    def test_docs_listing_preserves_selection_metadata_and_all_candidates(self):
        args = self.args(
            "docs",
            "Next.js",
            "Next.js 14 authentication",
            "--list",
            "--max-chars",
            "500",
        )
        result = "\n".join(self.library_result(i) for i in range(10))
        with patch.object(commands, "cached_call", return_value=result) as call:
            _, output = self.capture(commands.docs, args)
        call.assert_called_once()
        self.assertEqual(call.call_args.args[2]["query"], args.query)
        saved = next(config.OUTPUT.iterdir()).read_text()
        for expected in (
            "/vercel/next9",
            "reputation: High; snippets: 5115; score: 89.01",
            "Versions: v14.0.0, v15.0.0",
        ):
            self.assertIn(expected, saved)
        self.assertIn("[saved:", output)

    def test_docs_auto_selection_is_explicit_and_unpinned(self):
        args = self.args("docs", "Next.js", "Next.js 14 authentication")
        with patch.object(
            commands, "cached_call", side_effect=[self.library_result(), "answer"]
        ) as call:
            _, output = self.capture(commands.docs, args)
        self.assertEqual(call.call_args.args[2]["libraryId"], "/vercel/next0")
        self.assertIn("Selection: first match of 1; use --list to compare.", output)
        self.assertIn("Version: unpinned", output)
        self.assertNotIn("Versions:", output)
        self.assertNotIn("snippets:", output)
        self.assertTrue(output.endswith("answer\n"))

    def test_docs_versioned_id_is_passed_through_without_resolution(self):
        args = self.args("docs", "/vercel/next.js/v14.0.0", "authentication")
        with patch.object(commands, "cached_call", return_value="answer") as call:
            _, output = self.capture(commands.docs, args)
        call.assert_called_once_with(
            "c7",
            "query-docs",
            {"libraryId": args.library, "query": args.query},
            False,
        )
        self.assertNotIn("unpinned", output)

    def test_docs_listing_missing_metadata_does_not_invent_versions(self):
        args = self.args("docs", "Example", "--list")
        result = "- Title: Example\n- Context7-compatible library ID: /org/example"
        with patch.object(commands, "cached_call", return_value=result):
            _, output = self.capture(commands.docs, args)
        self.assertIn("Versions: not listed", output)
        self.assertNotIn("score:", output)

    def test_docs_listing_next_step_is_visible_once_without_question(self):
        args = self.args("docs", "Next.js")
        with patch.object(commands, "cached_call", return_value=self.library_result()):
            _, output = self.capture(commands.docs, args)
        self.assertTrue(output.startswith("# Context7 candidates (1)\nNext:"))
        self.assertEqual(output.count('docs <id> "<question>"'), 1)

    def test_docs_compact_selection_preserves_full_saved_documentation(self):
        args = self.args("docs", "Next.js", "authentication", "--max-chars", "250")
        result = "### Example\n\n" + "example body\n" * 100
        with patch.object(
            commands, "cached_call", side_effect=[self.library_result(), result]
        ):
            _, output = self.capture(commands.docs, args)
        self.assertIn("### Example", output)
        saved = next(config.OUTPUT.iterdir()).read_text()
        self.assertTrue(saved.endswith(result))

    def test_wiki_normalizes_repository_list(self):
        args = self.args("wiki", "ask", "one/repo, two/repo", "question")
        with patch.object(commands, "cached_call", return_value="answer") as call:
            self.capture(commands.wiki, args)
        self.assertEqual(call.call_args.args[2]["repoName"], ["one/repo", "two/repo"])


if __name__ == "__main__":
    unittest.main()
