"""Argument validation, the Context7/DeepWiki/grep.app commands, MCP, and the cache."""

import json
import os
import unittest
from unittest.mock import patch

import httpx2

from research_cli import cache, cli, config, credentials, mcp
from research_cli.errors import ResearchError
from support import ResearchTestCase, mcp_text, tool_call


def library(index: int = 0, versions: str = "v14.0.0, v15.0.0") -> str:
    return (
        f"- Title: Next.js {index}\n"
        f"- Context7-compatible library ID: /vercel/next{index}\n"
        "- Description: Full-stack React framework\n"
        "- Code Snippets: 5115\n"
        "- Source Reputation: High\n"
        "- Benchmark Score: 89.01\n"
        f"- Versions: {versions}\n----------"
    )


class ValidationTests(ResearchTestCase):
    def test_invalid_arguments_fail_before_any_request(self):
        cases = [
            ("docs", "/encode/httpx"),
            ("docs", "/encode/httpx", "question", "--list"),
            ("web", "q", "-n", "0"),
            ("web", "q", "-n", "101"),
            ("web", "q", "--chars", "0"),
            ("web", "q", "--read", "6"),
            ("web", " "),
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
            ("fetch", "https://a.test", "--match", "x", "--section", "y"),
            ("fetch", "https://a.test", "--lines", "5"),
            ("fetch", "https://a.test", "--lines", "9-3"),
            ("fetch", "https://a.test", "--lines", "0-4"),
        ]
        for argv in cases:
            with self.subTest(argv=argv):
                result = self.fails(*argv)
                self.assertTrue(result.stderr.startswith("error: "), result.stderr)
        self.assertEqual(self.web.sent, [])

    def test_raw_fetch_ignores_the_extraction_limit(self):
        self.web.serve("a.test", lambda: httpx2.Response(200, text="body"))
        self.ok("fetch", "--raw", "https://a.test", "--chars", "0")

    def test_common_options_work_before_and_after_the_command(self):
        parser = cli.build_parser()
        args = parser.parse_args(["--max-chars", "12", "web", "q", "--context", "1"])
        self.assertEqual((args.max_chars, args.context), (12, 1))
        self.assertEqual(
            parser.parse_args(["web", "q"]).max_chars, config.DEFAULT_MAX_CHARS
        )

    def test_fetch_modes_are_mutually_exclusive(self):
        for modes in (
            ("--raw", "--exa"),
            ("--firecrawl", "--raw"),
            ("--firecrawl", "--exa"),
        ):
            with self.subTest(modes=modes), self.assertRaises(SystemExit):
                cli.build_parser().parse_args(["fetch", *modes, "https://a.test"])

    def test_current_exa_categories_are_accepted(self):
        for category in ("publication", "people", "financial report", "github"):
            cli.build_parser().parse_args(["web", "q", "--category", category])

    def test_filesystem_errors_are_one_line_with_a_hint(self):
        with patch.object(
            cli, "remove_expired_files", side_effect=PermissionError("no access")
        ):
            result = self.fails("web", "query")
        self.assertEqual(
            result.stderr,
            "error: no access | hint: check local cache/output permissions\n",
        )


class DocsTests(ResearchTestCase):
    def context7(self, *responses: str) -> list[tuple[str, dict]]:
        calls: list[tuple[str, dict]] = []
        answers = list(responses)

        def handler(request, name):
            calls.append(tool_call(request))
            return mcp_text(answers.pop(0))

        self.web.route("mcp.context7.com", handler)
        return calls

    def test_library_id_is_queried_directly_and_named(self):
        calls = self.context7("answer")
        output = self.ok("docs", "/encode/httpx", "timeout defaults").stdout
        self.assertTrue(output.startswith("# Context7: /encode/httpx\n"))
        self.assertIn("Version: unpinned", output)
        self.assertEqual(
            calls,
            [
                (
                    "query-docs",
                    {"libraryId": "/encode/httpx", "query": "timeout defaults"},
                )
            ],
        )

    def test_versioned_id_passes_through_without_resolution_or_warning(self):
        calls = self.context7("answer")
        output = self.ok("docs", "/vercel/next.js/v14.0.0", "authentication").stdout
        self.assertEqual(len(calls), 1)
        self.assertNotIn("unpinned", output)

    def test_listing_keeps_every_candidate_and_its_ranking_signals(self):
        calls = self.context7("\n".join(library(i) for i in range(10)))
        output = self.ok(
            "docs", "Next.js", "Next.js 14 auth", "--list", "--max-chars", "500"
        ).stdout
        self.assertEqual(calls[0][1]["query"], "Next.js 14 auth")
        saved = self.saved(output)
        for expected in (
            "/vercel/next9",
            "reputation: High; snippets: 5115; score: 89.01",
            "Versions: v14.0.0, v15.0.0",
        ):
            self.assertIn(expected, saved)

    def test_listing_without_a_question_shows_the_next_step_once(self):
        self.context7(library())
        output = self.ok("docs", "Next.js").stdout
        self.assertTrue(output.startswith("# Context7 candidates (1)\nNext:"))
        self.assertEqual(output.count('docs <id> "<question>"'), 1)

    def test_missing_metadata_is_not_invented(self):
        self.context7(
            "- Title: Example\n- Context7-compatible library ID: /org/example"
        )
        output = self.ok("docs", "Example", "--list").stdout
        self.assertIn("Versions: not listed", output)
        self.assertNotIn("score:", output)

    def test_auto_selection_is_explicit_and_saves_the_full_answer(self):
        body = "### Example\n\n" + "example body\n" * 100
        calls = self.context7(library(), body)
        output = self.ok("docs", "Next.js", "auth", "--max-chars", "250").stdout
        self.assertEqual(calls[1][1]["libraryId"], "/vercel/next0")
        self.assertIn("Selection: first match of 1; use --list to compare.", output)
        self.assertNotIn("snippets:", output)
        self.assertTrue(self.saved(output).endswith(body))

    def test_unknown_names_and_ids_are_actionable(self):
        self.context7("No libraries found.")
        self.assertIn(
            "no library matches 'Nope'", self.fails("docs", "Nope", "q").stderr
        )
        self.context7('Library "/x/y" not found')
        self.assertIn("docs <name> --list", self.fails("docs", "/x/y", "q").stderr)


class RepositoryToolTests(ResearchTestCase):
    def test_wiki_ask_sends_a_repository_list_only_for_several(self):
        calls = []
        self.web.route(
            "mcp.deepwiki.com",
            lambda request, name: (
                calls.append(tool_call(request)),
                mcp_text("answer"),
            )[1],
        )
        self.ok("wiki", "ask", "one/repo, two/repo", "question")
        self.ok("wiki", "outline", "one/repo")
        self.assertEqual(
            calls[0],
            (
                "ask_wiki_question",
                {"repoName": ["one/repo", "two/repo"], "question": "question"},
            ),
        )
        self.assertEqual(calls[1], ("read_wiki_structure", {"repoName": "one/repo"}))
        deepwiki = self.web.sent[0]
        self.assertNotIn("x-api-key", deepwiki.headers)

    def test_code_search_prepends_an_index_of_every_hit(self):
        hit = (
            "Repository: o/{n}\nPath: src/{n}.tsx\nURL: u\nLicense: MIT\n\n"
            "Snippets:\n--- Snippet 1 (Line {line}) ---\n  code\n\n"
        )
        result = hit.format(n="a", line=5) + hit.format(n="b", line=9)
        calls = []
        self.web.route(
            "mcp.grep.app",
            lambda request, name: (calls.append(tool_call(request)), mcp_text(result))[
                1
            ],
        )
        output = self.ok(
            "code", "useState(", "--lang", "TypeScript", "--lang", "TSX", "--word"
        ).stdout
        self.assertIn("Index (2 hits):\no/a src/a.tsx:5\no/b src/b.tsx:9", output)
        self.assertEqual(
            calls[0][1],
            {
                "query": "useState(",
                "matchWholeWords": True,
                "language": ["TypeScript", "TSX"],
            },
        )

    def test_code_search_without_matches_suggests_dropping_a_filter(self):
        self.web.serve(
            "mcp.grep.app", lambda: mcp_text("No results found for your query.\n")
        )
        result = self.fails("code", "nope(", "--repo", "a/b")
        self.assertIn("error: no matches | hint:", result.stderr)
        self.assertIn("drop --repo", result.stderr)

    def test_examples_ask_exa_for_the_requested_count(self):
        calls = []
        self.web.route(
            "mcp.exa.ai",
            lambda request, name: (
                calls.append(tool_call(request)),
                mcp_text("example"),
            )[1],
        )
        self.assertIn("example", self.ok("examples", "httpx retries", "-n", "5").stdout)
        self.assertEqual(
            calls,
            [("get_code_context_exa", {"query": "httpx retries", "numResults": 5})],
        )


class McpTests(ResearchTestCase):
    def test_json_and_sse_responses_are_both_read(self):
        body = json.dumps(
            {"id": 1, "result": {"content": [{"type": "text", "text": "ok"}]}}
        )
        for text in (body, 'data: {"method":"notification"}\n\ndata: ' + body + "\n\n"):
            self.assertEqual(mcp.parse_tool_response(text, "tool"), "ok")

    def test_tool_errors_and_empty_results_raise(self):
        for response in (
            {"id": 1, "error": {"message": "failed"}},
            {
                "id": 1,
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": "failed"}],
                },
            },
            {"id": 1, "result": {"content": []}},
            {
                "id": 2,
                "result": {"content": [{"type": "text", "text": "other request"}]},
            },
        ):
            with self.subTest(response=response), self.assertRaises(ResearchError):
                mcp.parse_tool_response(json.dumps(response), "tool")

    def test_key_is_sent_and_cross_origin_redirects_are_refused(self):
        self.set_key("exa", "secret")
        for target in (
            "https://other.test/mcp",
            "http://mcp.exa.ai/mcp",
            "https://mcp.exa.ai:8443/mcp",
        ):
            with self.subTest(target=target):
                self.web.sent.clear()
                self.web.serve(
                    "mcp.exa.ai",
                    lambda target=target: httpx2.Response(
                        307, headers={"Location": target}
                    ),
                )
                result = self.fails("examples", "q", "--fresh")
                self.assertIn("cross-origin redirect refused", result.stderr)
                self.assertEqual(len(self.web.sent), 1)
                self.assertEqual(self.web.sent[0].headers["x-api-key"], "secret")

    def test_same_origin_redirect_repeats_the_post_with_its_key(self):
        self.set_key("context7", "secret")
        self.web.serve(
            "mcp.context7.com/mcp",
            lambda: httpx2.Response(307, headers={"Location": "/canonical"}),
        )
        self.web.serve("mcp.context7.com/canonical", lambda: mcp_text("docs"))
        self.ok("docs", "/a/b", "q")
        first, second = self.web.sent
        self.assertEqual((first.method, second.method), ("POST", "POST"))
        self.assertEqual(first.body, second.body)
        self.assertEqual(
            {first.headers["context7_api_key"], second.headers["context7_api_key"]},
            {"secret"},
        )

    def test_rate_limits_are_retried_but_timeouts_are_not(self):
        responses = [
            httpx2.Response(429, headers={"Retry-After": "1"}),
            mcp_text("answer"),
        ]
        self.web.serve("mcp.grep.app", lambda: responses.pop(0))
        self.ok("code", "x")
        self.assertEqual(len(self.web.sent), 2)

        def timeout(request, name):
            raise httpx2.ReadTimeout("slow", request=request)

        self.web.route("mcp.deepwiki.com", timeout)
        result = self.fails("wiki", "ask", "o/r", "q")
        self.assertIn("ask_wiki_question: timeout", result.stderr)
        self.assertEqual(len(self.web.urls("deepwiki")), 1)

    def test_unkeyed_rate_limit_suggests_a_key(self):
        self.web.serve("mcp.exa.ai", lambda: httpx2.Response(429, text="limited"))
        result = self.fails("examples", "q")
        self.assertIn("no API key loaded; keys lift limits", result.stderr)

    def test_service_read_budgets(self):
        self.web.serve("mcp.deepwiki.com", lambda: mcp_text("answer"))
        seen = []
        original = self.web.handle

        def spy(request, name):
            seen.append(request.extensions["timeout"])
            return original(request, name)

        with patch.object(self.web, "handle", side_effect=spy):
            self.ok("wiki", "outline", "o/r")
        self.assertEqual((seen[0]["connect"], seen[0]["read"]), (5, 240))


class CacheAndCredentialTests(ResearchTestCase):
    def test_cache_hits_fresh_bypass_and_failures_are_not_kept(self):
        values = iter(["first", "second"])
        self.assertEqual(cache.cached("exa", {"q": 1}, lambda: next(values)), "first")
        self.assertEqual(cache.cached("exa", {"q": 1}, lambda: next(values)), "first")
        self.assertEqual(
            cache.cached("exa", {"q": 1}, lambda: next(values), fresh=True), "second"
        )
        self.assertEqual(len(list(config.CACHE.iterdir())), 1)

        def fail() -> str:
            raise ResearchError("failed")

        with self.assertRaises(ResearchError):
            cache.cached("exa", {"q": 2}, fail)
        self.assertEqual(len(list(config.CACHE.iterdir())), 1)

    def test_cache_preserves_line_endings(self):
        cache.cached("raw", "u", lambda: "first\r\nlast\r\n")
        self.assertEqual(cache.cached("raw", "u", lambda: "other"), "first\r\nlast\r\n")

    def test_environment_key_wins_over_the_secrets_file(self):
        (self.secrets / "exa-api-key").write_text(" file-key\n")
        for value, expected in (
            (" env-key ", "env-key"),
            ("  ", "file-key"),
            ("", "file-key"),
        ):
            with (
                self.subTest(value=value),
                patch.dict(os.environ, {"EXA_API_KEY": value}),
            ):
                self.assertEqual(credentials.api_key("exa"), expected)
        self.assertIsNone(credentials.api_key("brave"))


if __name__ == "__main__":
    unittest.main()
