import contextlib
import importlib.util
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

spec = importlib.util.spec_from_file_location(
    "research", Path(__file__).resolve().parents[1] / "scripts" / "research.py"
)
research = importlib.util.module_from_spec(spec)
spec.loader.exec_module(research)


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for name in ("CACHE", "OUTPUT"):
            directory = root / name.lower()
            directory.mkdir()
            self.enterContext(patch.object(research, name, directory))

    def args(self, *tokens):
        args = research.build_parser().parse_args(tokens)
        research.validate_args(args)
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
            with self.subTest(tokens=tokens), self.assertRaises(research.ResearchError):
                self.args(*tokens)

    def test_current_exa_categories(self):
        for category in ("publication", "people", "financial report", "github"):
            self.args("web", "query", "--category", category)

    def test_explicit_chars_selects_advanced_search(self):
        args = self.args("web", "query", "--chars", "321")
        with patch.object(research, "cached_call", return_value="result") as call:
            self.capture(research.web, args)
        self.assertEqual(call.call_args.args[1], "web_search_advanced_exa")
        self.assertEqual(call.call_args.args[2]["textMaxCharacters"], 321)

    def test_basic_search_preserves_objective(self):
        args = self.args("web", "query", "--objective", "goal")
        with patch.object(research, "cached_call", return_value="result") as call:
            self.capture(research.web, args)
        self.assertEqual(call.call_args.args[1], "web_search_exa")
        self.assertEqual(call.call_args.args[2]["objective"], "goal")

    def test_filtered_search_default_extraction_limit(self):
        args = self.args("web", "query", "--domain", "example.com")
        with patch.object(research, "cached_call", return_value="result") as call:
            self.capture(research.web, args)
        self.assertEqual(call.call_args.args[2]["textMaxCharacters"], 1500)

    def test_short_response_stays_inline(self):
        args = self.args("web", "query")
        used, output = self.capture(research.emit_response, "short", args, "test")
        self.assertEqual((used, output), (5, "short\n"))
        self.assertEqual(list(research.OUTPUT.iterdir()), [])

    def test_large_response_saved_with_bounded_preview(self):
        args = self.args("web", "query", "--max-chars", "20")
        text = "a" * 100
        used, output = self.capture(research.emit_response, text, args, "test")
        self.assertEqual(used, 20)
        self.assertTrue(output.startswith("a" * 20 + "\n[saved:"))
        self.assertEqual(next(research.OUTPUT.iterdir()).read_text(), text + "\n")

    def test_no_match_still_saves_full_response(self):
        args = self.args("web", "query", "--match", "missing")
        _, output = self.capture(research.emit_response, "full response", args, "test")
        self.assertIn("No matching lines", output)
        self.assertEqual(next(research.OUTPUT.iterdir()).read_text(), "full response\n")

    def test_matching_lines_merge_context_and_keep_source_numbers(self):
        text = "a\nb\nmatch\nd\nmatch\nf\ng\nh\nmatch"
        self.assertEqual(
            research.matching_lines(text, re.compile("match"), 1),
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
        with patch.object(research, "cached_call", side_effect=["a" * 40, "b" * 40]):
            _, output = self.capture(research.fetch, args)
        self.assertIn("a" * 20, output)
        self.assertNotIn("b" * 20, output)
        self.assertIn("preview 0/40", output)
        self.assertEqual(len(list(research.OUTPUT.iterdir())), 2)
        self.assertEqual(
            {path.read_text() for path in research.OUTPUT.iterdir()},
            {"a" * 40, "b" * 40},
        )

    def test_unlimited_preview_is_explicit(self):
        args = self.args("web", "query", "--max-chars", "0")
        used, output = self.capture(research.emit_response, "a" * 5000, args, "test")
        self.assertEqual(used, 5000)
        self.assertNotIn("[saved:", output)

    def test_cache_hit_fresh_and_atomic_write(self):
        with patch.object(
            research, "request_tool", side_effect=["first", "second"]
        ) as call:
            self.assertEqual(research.cached_call("exa", "tool", {"q": "x"}), "first")
            self.assertEqual(research.cached_call("exa", "tool", {"q": "x"}), "first")
            self.assertEqual(
                research.cached_call("exa", "tool", {"q": "x"}, True), "second"
            )
        self.assertEqual(call.call_count, 2)
        self.assertEqual(len(list(research.CACHE.iterdir())), 1)

    def test_failed_response_is_not_cached(self):
        with patch.object(
            research, "request_tool", side_effect=research.ResearchError("failed")
        ):
            with self.assertRaises(research.ResearchError):
                research.cached_call("exa", "tool", {})
        self.assertEqual(list(research.CACHE.iterdir()), [])

    def test_raw_cache_preserves_line_endings(self):
        text = "first\r\nlast\r\n"
        with patch.object(research, "fetch_raw", return_value=text) as fetch:
            self.assertEqual(
                research.cached_call("raw", "fetch", {"url": "https://example.com"}),
                text,
            )
            self.assertEqual(
                research.cached_call("raw", "fetch", {"url": "https://example.com"}),
                text,
            )
        self.assertEqual(fetch.call_count, 1)

    def test_json_and_sse_tool_responses(self):
        response = json.dumps(
            {"id": 1, "result": {"content": [{"type": "text", "text": "ok"}]}}
        )
        for body in (
            response,
            'data: {"method":"notification"}\n\ndata: ' + response + "\n\n",
        ):
            self.assertEqual(research.parse_tool_response(body, "tool"), "ok")

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
                self.assertRaises(research.ResearchError),
            ):
                research.parse_tool_response(json.dumps(response), "tool")

    def test_timeout_does_not_repeat_expensive_call(self):
        with patch.object(
            research.httpx, "post", side_effect=httpx.ReadTimeout("timeout")
        ) as post:
            with self.assertRaisesRegex(research.ResearchError, "timeout"):
                research.request_tool("dw", "ask_wiki_question", {})
        self.assertEqual(post.call_count, 1)

    def test_raw_fetch_rejects_credentials_and_non_http(self):
        for url in ("file:///etc/passwd", "https://user:pass@example.com", "not-a-url"):
            with self.subTest(url=url), self.assertRaises(research.ResearchError):
                research.fetch_raw(url)

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
            research.httpx, "stream", return_value=contextlib.nullcontext(response)
        ):
            self.assertEqual(
                research.fetch_raw("https://example.com"), "  first\r\nlast\n\n"
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
                    research.httpx,
                    "stream",
                    return_value=contextlib.nullcontext(response),
                ),
                patch.object(research, "MAX_RAW_BYTES", limit),
            ):
                with self.assertRaises(research.ResearchError):
                    research.fetch_raw("https://example.com")

    def test_filesystem_errors_are_concise(self):
        stderr = io.StringIO()
        with (
            patch.object(research.sys, "argv", ["research", "web", "query"]),
            patch.object(
                research,
                "remove_expired_files",
                side_effect=PermissionError("no access"),
            ),
            contextlib.redirect_stderr(stderr),
        ):
            self.assertEqual(research.main(), 1)
        self.assertIn("error: no access | hint:", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_direct_docs_emit_selected_id(self):
        args = self.args("docs", "/encode/httpx", "timeout defaults")
        with patch.object(research, "cached_call", return_value="answer"):
            _, output = self.capture(research.docs, args)
        self.assertTrue(output.startswith("# Context7: /encode/httpx\n"))

    def test_wiki_normalizes_repository_list(self):
        args = self.args("wiki", "ask", "one/repo, two/repo", "question")
        with patch.object(research, "cached_call", return_value="answer") as call:
            self.capture(research.wiki, args)
        self.assertEqual(call.call_args.args[2]["repoName"], ["one/repo", "two/repo"])


if __name__ == "__main__":
    unittest.main()
