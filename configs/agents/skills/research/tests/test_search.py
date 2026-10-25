"""`web`: provider requests, fallback, fusion, query interleaving, and layout."""

import json
import re
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import httpx2

from research_cli.layout import layout_results
from research_cli.models import SearchResult
from research_cli.search import fuse
from support import ResearchTestCase, mcp_text, tool_call

LISTING = (
    "Title: First\nURL: https://one.test/a\nPublished: 2026-01-02T00:00:00.000Z\n"
    "Author: N/A\nHighlights:\nalpha passage\n...\nTitle: not a result\n\n"
    "Title: N/A\nURL: https://two.test/b\nPublished: N/A\nHighlights:\nbeta passage"
)
PAGE = "# Guide\n\n## Proxies\n\nSet trust_env to False to ignore proxy variables.\n"
Hits = Callable[[str, str], list[dict[str, Any]]]


def hit(url: str, text: str = "text", title: str = "T") -> dict[str, Any]:
    return {"title": title, "url": url, "text": text}


class SearchTestCase(ResearchTestCase):
    """Every REST provider configured; each answers with `hits(provider, query)`."""

    def setUp(self) -> None:
        super().setUp()
        for name in ("parallel", "brave", "tavily"):
            self.set_key(name)
        self.requests: dict[str, list[dict[str, Any]]] = {}

    def providers(
        self, hits: Hits, *, exa: Callable[[str, dict], str] | None = None
    ) -> None:
        def record(name: str, payload: dict[str, Any]) -> None:
            self.requests.setdefault(name, []).append(payload)

        def parallel(request, transport):
            payload = json.loads(request.content)
            record("parallel", payload)
            items = [
                {"title": h["title"], "url": h["url"], "excerpts": [h["text"]]}
                for h in hits("parallel", payload["search_queries"][0])
            ]
            return httpx2.Response(200, json={"results": items})

        def brave(request, transport):
            params = {
                key: values[0]
                for key, values in parse_qs(request.url.query.decode()).items()
            }
            record("brave", params)
            items = [
                {"title": h["title"], "url": h["url"], "description": h["text"]}
                for h in hits("brave", params["q"])
            ]
            return httpx2.Response(200, json={"web": {"results": items}})

        def tavily(request, transport):
            payload = json.loads(request.content)
            record("tavily", payload)
            items = [
                {"title": h["title"], "url": h["url"], "content": h["text"]}
                for h in hits("tavily", payload["query"])
            ]
            return httpx2.Response(200, json={"results": items})

        def exa_handler(request, transport):
            tool, arguments = tool_call(request)
            record("exa", {"tool": tool, **arguments})
            if exa is not None:
                return mcp_text(exa(tool, arguments))
            if tool == "web_search_exa":  # the basic search answers in a text listing
                return mcp_text(
                    "\n\n".join(
                        f"Title: {h['title']}\nURL: {h['url']}\n"
                        f"Highlights:\n{h['text']}"
                        for h in hits("exa", arguments["query"])
                    )
                )
            items = [
                {"title": h["title"], "url": h["url"], "highlights": [h["text"]]}
                for h in hits("exa", arguments["query"])
            ]
            return mcp_text(json.dumps({"results": items}))

        self.web.route("api.parallel.ai", parallel)
        self.web.route("api.search.brave.com", brave)
        self.web.route("api.tavily.com", tavily)
        self.web.route("mcp.exa.ai", exa_handler)


class ProviderTests(SearchTestCase):
    def test_exa_basic_listing_parses_without_splitting_on_passage_text(self):
        self.providers(lambda name, query: [], exa=lambda tool, arguments: LISTING)
        output = self.ok("web", "query", "--backend", "exa").stdout
        self.assertIn(
            "1. First (2026-01-02)\nhttps://one.test/a\nalpha passage", output
        )
        self.assertIn("Title: not a result", output)
        self.assertIn("2. https://two.test/b\nbeta passage", output)
        self.assertEqual(self.requests["exa"][0]["tool"], "web_search_exa")

    def test_exa_objective_filters_and_chars_select_its_search_tool(self):
        self.providers(lambda name, query: [hit("https://x.test")])
        self.ok("web", "query", "--backend", "exa", "--objective", "goal")
        self.ok("web", "query", "--backend", "exa", "--domain", "example.com")
        self.ok("web", "query", "--backend", "exa", "--chars", "321")
        basic, filtered, chars = self.requests["exa"]
        self.assertEqual(
            (basic["tool"], basic["objective"]), ("web_search_exa", "goal")
        )
        self.assertEqual(filtered["tool"], "web_search_advanced_exa")
        self.assertEqual(filtered["textMaxCharacters"], 1500)
        self.assertEqual(filtered["includeDomains"], ["example.com"])
        self.assertEqual(
            (chars["textMaxCharacters"], chars["enableHighlights"]), (321, False)
        )

    def test_brave_builds_site_operators_and_unescapes_entities(self):
        self.providers(
            lambda name, query: [
                hit("https://a.test", "say &quot;hi&quot;", "A &amp; B")
            ]
        )
        output = self.ok(
            "web",
            "q",
            "--backend",
            "brave",
            "-n",
            "50",
            "--domain",
            "a.test",
            "--domain",
            "b.test",
            "--exclude",
            "c.test",
            "--after",
            "2026-01-01",
            "--before",
            "2026-02-01",
        ).stdout
        sent = self.requests["brave"][0]
        self.assertEqual(sent["q"], "(site:a.test OR site:b.test) q -site:c.test")
        self.assertEqual(
            (sent["count"], sent["freshness"]), ("20", "2026-01-01to2026-02-01")
        )
        self.assertIn('1. A & B\nhttps://a.test\nsay "hi"', output)
        brave = next(s for s in self.web.sent if "brave" in s.url)
        self.assertEqual(brave.headers["x-subscription-token"], "test-key")

    def test_parallel_and_tavily_map_filters_onto_their_apis(self):
        self.providers(lambda name, query: [hit(f"https://{name}.test")])
        self.ok(
            "web",
            "a",
            "--backend",
            "parallel",
            "-n",
            "4",
            "--chars",
            "700",
            "--domain",
            "p.test",
            "--after",
            "2026-01-01",
        )
        self.ok("web", "a", "--backend", "tavily", "--before", "2026-02-01")
        parallel = self.requests["parallel"][0]
        self.assertEqual(
            parallel["advanced_settings"],
            {
                "max_results": 4,
                "excerpt_settings": {"max_chars_per_result": 700},
                "source_policy": {
                    "include_domains": ["p.test"],
                    "after_date": "2026-01-01",
                },
            },
        )
        tavily = self.requests["tavily"][0]
        self.assertEqual((tavily["query"], tavily["end_date"]), ("a", "2026-02-01"))
        auth = next(s for s in self.web.sent if "tavily" in s.url).headers[
            "authorization"
        ]
        self.assertEqual(auth, "Bearer test-key")

    def test_site_operators_become_domain_filters_except_for_brave(self):
        self.providers(lambda name, query: [hit("https://x.test")])
        self.ok("web", "site:github.com/ijl/orjson free threading", "--backend", "all")
        exa = self.requests["exa"][0]
        self.assertEqual(
            (exa["includeDomains"], exa["query"]),
            (["github.com"], "free threading ijl orjson"),
        )
        parallel = self.requests["parallel"][0]
        self.assertEqual(parallel["search_queries"], ["free threading"])
        self.assertEqual(
            parallel["advanced_settings"]["source_policy"]["include_domains"],
            ["github.com/ijl/orjson"],
        )
        self.assertEqual(self.requests["tavily"][0]["include_domains"], ["github.com"])
        self.assertEqual(
            self.requests["brave"][0]["q"], "site:github.com/ijl/orjson free threading"
        )

    def test_provider_errors_name_the_key_or_suggest_another_backend(self):
        for status, hint in (
            (401, "~/.secrets/tavily-api-key"),
            (429, "another --backend"),
        ):
            with self.subTest(status=status):
                self.web.serve(
                    "api.tavily.com",
                    lambda status=status: httpx2.Response(status, json={}),
                )
                result = self.fails("web", "q", "--backend", "tavily", "--fresh")
                self.assertIn(hint, result.stderr)
                self.assertIn("error: every provider failed:", result.stderr)
                self.assertNotIn("rephrase", result.stderr)

    def test_brave_retries_rate_limits_then_gives_up(self):
        responses = [
            httpx2.Response(429, json={}),
            httpx2.Response(
                200,
                json={
                    "web": {
                        "results": [
                            {
                                "title": "B",
                                "url": "https://b.test",
                                "description": "found",
                            }
                        ]
                    }
                },
            ),
        ]
        self.web.serve("api.search.brave.com", lambda: responses.pop(0))
        self.assertIn("found", self.ok("web", "q", "--backend", "brave").stdout)
        responses.extend(httpx2.Response(429, json={}) for _ in range(3))
        result = self.fails("web", "q", "--backend", "brave", "--fresh")
        self.assertIn("brave: HTTP 429", result.stderr)
        self.assertEqual(responses, [])

    def test_backend_selection_errors_are_actionable(self):
        self.assertIn(
            "unknown backend 'bing'", self.fails("web", "q", "--backend", "bing").stderr
        )
        self.assertIn(
            "Exa-only",
            self.fails("web", "q", "--backend", "all", "--category", "news").stderr,
        )
        import os

        del os.environ["BRAVE_API_KEY"]
        result = self.fails("web", "q", "--backend", "brave")
        self.assertIn(
            "brave key not configured | hint: set $BRAVE_API_KEY", result.stderr
        )


class CombinationTests(SearchTestCase):
    def test_auto_falls_back_and_reports_the_failure(self):
        self.providers(
            lambda name, query: [hit("https://docs.test/page", "from parallel")]
        )
        self.web.serve("mcp.exa.ai", lambda: httpx2.Response(429, text="slow down"))
        output = self.ok("web", "query").stdout
        self.assertIn(
            "[exa failed: web_search_exa: HTTP 429 slow down; rate limited", output
        )
        self.assertIn("[web: 1 results via parallel]", output)
        self.assertNotIn("brave", self.requests)

    def test_every_provider_failing_lists_each_reason(self):
        for host in (
            "mcp.exa.ai",
            "api.parallel.ai",
            "api.search.brave.com",
            "api.tavily.com",
        ):
            self.web.serve(host, lambda: httpx2.Response(500, text="down"))
        result = self.fails("web", "query")
        self.assertRegex(result.stderr, r"exa.*parallel.*brave.*tavily")

    def test_fusion_merges_one_page_across_providers_and_ranks_agreement_first(self):
        def hits(name: str, query: str) -> list[dict[str, Any]]:
            if name == "exa":
                return [
                    hit("https://solo.test", "x", "Only Exa"),
                    hit(
                        "https://www.shared.test/doc/?utm_source=a",
                        "exa text",
                        "Shared",
                    ),
                ]
            return [hit("https://shared.test/doc", "brave text", "Shared")]

        self.providers(hits)
        output = self.ok("web", "query", "--backend", "exa,brave").stdout
        self.assertIn("[web: 2 results via exa, brave]", output)
        self.assertLess(output.index("Shared [exa, brave]"), output.index("Only Exa"))
        self.assertIn("exa text", output)
        self.assertNotIn("brave text", output)

    def test_garbled_text_is_replaced_by_another_providers_copy(self):
        garbled = SearchResult("T", "https://a.test", "", "�\x01" * 40)
        clean = SearchResult("T", "https://a.test", "", "clean")
        (merged,) = fuse([("exa", [garbled]), ("brave", [clean])], 5)
        self.assertEqual((merged.text, merged.providers), ("clean", ["exa", "brave"]))

    def test_several_queries_alternate_and_keep_their_ids(self):
        def hits(name: str, query: str) -> list[dict[str, Any]]:
            shared = [hit("https://shared.test")] if query == "two" else []
            return [
                hit(f"https://{query}.test/{n}", title=f"{query}{n}") for n in range(3)
            ] + shared

        self.providers(hits)
        output = self.ok(
            "web", "one", "two", "--backend", "parallel,brave", "-n", "4"
        ).stdout
        self.assertEqual(
            re.findall(r"^\d\. (\w+)", output, re.MULTILINE),
            ["one0", "two0", "one1", "two1"],
        )
        self.assertIn('Queries:\nQ1: "one"\nQ2: "two"', output)
        self.assertIn("one0 [parallel, brave] [queries: Q1]", output)
        self.assertEqual(len(self.requests["brave"]), 2)

    def test_shared_results_keep_every_query_id_in_text_file_and_json(self):
        def hits(name: str, query: str) -> list[dict[str, Any]]:
            return [
                hit("https://shared.test", "shared passage " * 100, "Shared"),
                hit(f"https://{query}.test", title=query),
            ]

        self.providers(hits)
        args = ("web", "one", "one", "two", "--backend", "brave", "--max-chars", "500")
        record = json.loads(self.ok(*args, "--json").stdout)
        self.assertEqual(record["queries"], ["one", "two"])
        self.assertEqual(
            [r["query_ids"] for r in record["results"]], [[1, 2], [1], [2]]
        )
        self.assertIn("Shared [queries: Q1, Q2]", Path(record["saved"]).read_text())
        text = self.ok(*args).stdout
        self.assertIn("Shared [queries: Q1, Q2]", text)
        self.assertTrue(self.saved(text).startswith('Queries:\nQ1: "one"\nQ2: "two"'))

    def test_a_query_without_results_is_reported_and_keeps_its_id(self):
        self.providers(
            lambda name, query: [] if "one" in query else [hit("https://two.test")]
        )
        output = self.ok("web", "one", "two", "--backend", "brave").stdout
        self.assertIn("[brave (query 1): no results]", output)
        self.assertIn("[queries: Q2]", output)

    def test_result_count_scales_with_the_number_of_queries(self):
        self.providers(
            lambda name, query: [hit(f"https://{query}.test/{n}") for n in range(9)]
        )
        self.ok("web", "a", "b", "c", "d", "e", "--backend", "tavily")
        self.assertEqual(self.requests["tavily"][0]["max_results"], 15)

    def test_read_swaps_snippets_for_passages_from_the_saved_page(self):
        self.providers(
            lambda name, query: [
                hit("https://a.test", "snippet"),
                hit("https://b.test"),
            ]
        )
        self.web.serve(
            "a.test",
            lambda: httpx2.Response(
                200, text=PAGE, headers={"Content-Type": "text/markdown"}
            ),
        )
        output = self.ok(
            "web", "trust_env proxy", "--backend", "brave", "--read", "1"
        ).stdout
        self.assertIn("[lines 5-5 | Proxies]\nSet trust_env to False", output)
        self.assertNotIn("snippet", output)
        folder = re.search(r"pages saved in (\S+)\]", output)
        page = re.search(r"page saved: (\S+)", output)
        assert folder
        assert page
        self.assertEqual(Path(folder.group(1), page.group(1)).read_text(), PAGE)
        self.assertNotIn("b.test", self.web.urls("b.test"))

    def test_json_reports_fitted_text_and_the_saved_path(self):
        self.providers(
            lambda name, query: [
                hit("https://a.test", "x" * 900),
                hit("https://b.test"),
            ]
        )
        data = json.loads(
            self.ok(
                "web", "q", "--backend", "tavily", "--json", "--max-chars", "400"
            ).stdout
        )
        self.assertEqual(data["providers"], ["tavily"])
        self.assertEqual(data["results"][0]["chars"], 900)
        self.assertLess(len(data["results"][0]["text"]), 400)
        self.assertIn("x" * 900, Path(data["saved"]).read_text())

    def test_provider_answers_are_cached_per_request(self):
        self.providers(lambda name, query: [hit("https://a.test")])
        self.ok("web", "q", "--backend", "brave")
        self.ok("web", "q", "--backend", "brave")
        self.ok("web", "q", "--backend", "brave", "--fresh")
        self.assertEqual(len(self.requests["brave"]), 2)


class LayoutTests(unittest.TestCase):
    def results(self, *texts: str) -> list[SearchResult]:
        return [
            SearchResult("", f"https://{n}.test", "", text)
            for n, text in enumerate(texts)
        ]

    def test_tight_preview_keeps_every_result_and_points_into_the_saved_file(self):
        results = self.results("zero " + "word " * 300, "short", "two " + "word " * 300)
        layout = layout_results(results, 900, show_providers=False, queries=["q"])
        self.assertLessEqual(len(layout.compact), 900)
        for n in range(3):
            self.assertIn(f"https://{n}.test", layout.compact)
        self.assertEqual(layout.fitted[1], "short")
        line = int(re.findall(r"saved line (\d+)", layout.compact)[-1])
        self.assertTrue(layout.full.splitlines()[line - 2].startswith("two word"))

    def test_query_map_keeps_saved_line_references_exact(self):
        doc = " ".join(f"word{n}" for n in range(60))
        results = self.results(doc, doc[::-1])
        results[1].query_ids = [2]
        layout = layout_results(
            results, 300, show_providers=False, queries=["one", "two"]
        )
        cited = re.search(r"saved line (\d+)", layout.fitted[1])
        assert cited
        line = int(cited.group(1))
        self.assertEqual(layout.full.splitlines()[line - 1], doc[::-1][: len(doc)])

    def test_a_result_repeating_an_earlier_one_is_collapsed(self):
        doc = " ".join(f"word{n}" for n in range(60))
        results = self.results(
            doc, f"[lines 30-41 | H]\n[a](https://x.test) {doc}", doc[::-1]
        )
        layout = layout_results(results, None, show_providers=False, queries=["q"])
        self.assertEqual(layout.full.count("word59"), 2)
        self.assertEqual(layout.fitted[1], "[same text as result 1; saved line 5]")
        self.assertEqual(layout.full.splitlines()[4], "[lines 30-41 | H]")


if __name__ == "__main__":
    unittest.main()
