import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from research_cli import (
    cache,
    cli,
    commands,
    config,
    firecrawl,
    github,
    pages,
    providers,
    search,
)
from research_cli import output as out

LISTING = (
    "Title: First\nURL: https://one.test/a\nPublished: 2026-01-02T00:00:00.000Z\n"
    "Author: N/A\nHighlights:\nalpha passage\n...\nTitle: not a result\n\n"
    "Title: N/A\nURL: https://two.test/b\nPublished: N/A\nHighlights:\nbeta passage"
)
PAGE = """# Guide

Intro paragraph about nothing in particular.

## Install

Run the installer and wait.

```sh
# not a heading
make install
```

## Proxies

Set trust_env to False to ignore proxy variables.

### Details

Unrelated closing words.
"""


def hit(url, text="text", title="T"):
    return {"title": title, "url": url, "date": "", "text": text}


class SearchTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        patches = [
            patch.object(
                httpx.HTTPTransport,
                "handle_request",
                side_effect=AssertionError("unit tests must not make live requests"),
            ),
            patch.object(search, "configured", return_value=list(search.PROVIDERS)),
        ]
        for name in ("CACHE", "OUTPUT"):
            directory = Path(temp.name) / name.lower()
            directory.mkdir()
            patches.append(patch.object(config, name, directory))
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def args(self, *tokens):
        args = cli.build_parser().parse_args(tokens)
        cli.validate_args(args)
        return args

    def run_web(self, *tokens, respond):
        output = io.StringIO()
        with (
            patch.object(search, "cached_call", side_effect=respond) as call,
            contextlib.redirect_stdout(output),
        ):
            commands.web(self.args("web", *tokens))
        return output.getvalue(), call

    def test_exa_listing_parses_results_without_splitting_on_passage_text(self):
        first, second = search.parse_exa_listing(LISTING)
        self.assertEqual(
            (first["title"], first["url"], first["date"]),
            ("First", "https://one.test/a", "2026-01-02"),
        )
        self.assertIn("Title: not a result", first["text"])
        self.assertEqual((second["title"], second["text"]), ("", "beta passage"))

    def test_auto_falls_back_to_the_next_provider_and_reports_the_failure(self):
        def respond(service, tool, arguments, fresh, **options):
            if service == "exa":
                raise config.ResearchError("web_search_exa: HTTP 429")
            return json.dumps([hit("https://docs.test/page", "from parallel")])

        output, call = self.run_web("query", respond=respond)
        self.assertEqual([c.args[0] for c in call.call_args_list], ["exa", "parallel"])
        self.assertIn("[exa failed: web_search_exa: HTTP 429]", output)
        self.assertIn("[web: 1 results via parallel]", output)
        self.assertIn("from parallel", output)

    def test_every_provider_failing_raises_with_each_reason(self):
        def respond(service, tool, arguments, fresh, **options):
            raise config.ResearchError(f"{service}: down")

        with self.assertRaisesRegex(config.ResearchError, "exa: down.*tavily: down"):
            self.run_web("query", respond=respond)

    def test_fusion_merges_one_page_across_providers_and_ranks_agreement_first(self):
        def respond(service, tool, arguments, fresh, **options):
            if service == "exa":
                return "Title: Only Exa\nURL: https://solo.test\nHighlights:\nx\n\n" + (
                    "Title: Shared\nURL: https://www.shared.test/doc/?utm_source=a\n"
                    "Highlights:\nexa text"
                )
            return json.dumps([hit("https://shared.test/doc", "brave text", "Shared")])

        output, _ = self.run_web("query", "--backend", "exa,brave", respond=respond)
        self.assertIn("[web: 2 results via exa, brave]", output)
        self.assertLess(output.index("Shared [exa, brave]"), output.index("Only Exa"))
        self.assertIn("exa text", output)
        self.assertNotIn("brave text", output)

    def test_several_queries_alternate_so_each_is_represented(self):
        def respond(service, tool, arguments, fresh, **options):
            query = arguments["queries"][0]
            if query == "two" and service == "brave":
                raise config.ResearchError("brave: HTTP 429")
            shared = [hit("https://shared.test")] if query == "two" else []
            return json.dumps(
                [
                    hit(f"https://{query}.test/{n}", title=f"{query}{n}")
                    for n in range(3)
                ]
                + shared
            )

        output, call = self.run_web(
            "one", "two", "--backend", "parallel,brave", "-n", "4", respond=respond
        )
        self.assertEqual(call.call_count, 4)
        self.assertEqual(len(call.call_args.args[2]["queries"]), 1)
        self.assertEqual(
            re.findall(r"^\d\. (\w+)", output, re.MULTILINE),
            ["one0", "two0", "one1", "two1"],
        )
        self.assertIn("[brave (query 2) failed: brave: HTTP 429]", output)
        self.assertIn("one0 [parallel, brave]", output)
        self.assertIn("two0 [parallel]", output)

    def test_site_operators_become_domain_filters_except_for_brave(self):
        seen = {}

        def respond(service, tool, arguments, fresh, **options):
            seen[service] = arguments
            if service == "exa":
                return json.dumps(
                    {"results": [{"url": "https://x.test", "title": "X"}]}
                )
            return json.dumps([hit("https://x.test")])

        self.run_web(
            "site:github.com/ijl/orjson free threading",
            "--backend",
            "all",
            respond=respond,
        )
        self.assertEqual(seen["exa"]["includeDomains"], ["github.com"])
        self.assertEqual(seen["exa"]["query"], "free threading ijl orjson")
        self.assertEqual(seen["parallel"]["domains"], ["github.com/ijl/orjson"])
        self.assertEqual(seen["parallel"]["queries"], ["free threading"])
        self.assertEqual(seen["tavily"]["domains"], ["github.com"])
        self.assertNotIn("domains", seen["brave"])
        self.assertEqual(
            seen["brave"]["queries"], ["site:github.com/ijl/orjson free threading"]
        )
        self.assertEqual(
            search.split_sites("site:a.test/x/1", paths=False), ("x 1", ["a.test"])
        )

    def test_unsupported_and_unconfigured_backends_are_actionable(self):
        with (
            patch.object(search, "configured", return_value=["exa"]),
            self.assertRaisesRegex(config.ResearchError, "brave key not"),
        ):
            search.select_providers(self.args("web", "q", "--backend", "brave"))
        with self.assertRaisesRegex(config.ResearchError, "unknown backend"):
            search.select_providers(self.args("web", "q", "--backend", "bing"))
        with self.assertRaisesRegex(config.ResearchError, "Exa-only"):
            search.select_providers(
                self.args("web", "q", "--backend", "all", "--category", "news")
            )

    def test_tight_preview_keeps_every_result_and_points_into_the_saved_file(self):
        results = [
            {**hit(f"https://{n}.test", f"{n} " + "word " * 300), "providers": ["exa"]}
            for n in ("one", "two", "three")
        ]
        results[1]["text"] = "short"
        full, compact, fitted = search.layout_results(results, 900, False)
        self.assertLessEqual(len(compact), 900)
        for name in ("one", "two", "three"):
            self.assertIn(f"https://{name}.test", compact)
        self.assertEqual(fitted[1], "short")
        line = int(re.findall(r"saved line (\d+)", compact)[-1])
        self.assertTrue(full.splitlines()[line - 2].startswith("three word"))

    def test_json_output_reports_fitted_text_and_the_saved_path(self):
        def respond(service, tool, arguments, fresh, **options):
            return json.dumps([hit("https://a.test", "x" * 900), hit("https://b.test")])

        output, _ = self.run_web(
            "q", "--backend", "tavily", "--json", "--max-chars", "400", respond=respond
        )
        data = json.loads(output)
        self.assertEqual(data["providers"], ["tavily"])
        self.assertEqual(
            [r["url"] for r in data["results"]], ["https://a.test", "https://b.test"]
        )
        self.assertEqual(data["results"][0]["chars"], 900)
        self.assertLess(len(data["results"][0]["text"]), 400)
        self.assertIn("x" * 900, Path(data["saved"]).read_text())

    def test_read_replaces_the_snippet_with_passages_from_the_saved_page(self):
        def respond(service, tool, arguments, fresh, **options):
            return json.dumps([hit("https://a.test", "snippet"), hit("https://b.test")])

        page = commands.FetchResult(text=PAGE, source="direct HTTP, markdown")
        with patch.object(commands, "fetch_result", return_value=page) as fetched:
            output, _ = self.run_web(
                "trust_env proxy", "--backend", "brave", "--read", "1", respond=respond
            )
        self.assertEqual(fetched.call_count, 1)
        self.assertIn("[lines 16-16 | Proxies]\nSet trust_env to False", output)
        self.assertNotIn("snippet", output)
        saved = re.search(r"page saved: (\S+)", output).group(1)
        self.assertEqual(Path(saved).read_text(), PAGE)

    def test_outline_lists_numbered_headings_outside_code_fences(self):
        outline = out.page_outline(PAGE, 1000)
        self.assertIn("5: ## Install", outline)
        self.assertIn("18: ### Details", outline)
        self.assertNotIn("not a heading", outline)
        shallow = out.page_outline(PAGE, 110)
        self.assertNotIn("Details", shallow)
        self.assertIn("more headings", shallow)

    def test_section_returns_the_whole_section_or_lists_the_headings(self):
        section = out.matching_sections(PAGE, re.compile("prox", re.IGNORECASE))
        self.assertTrue(section.startswith("[lines 14-20]\n## Proxies"))
        self.assertIn("Unrelated closing words.", section)
        missing = out.matching_sections(PAGE, re.compile("absent"))
        self.assertIn("No heading matches", missing)
        self.assertIn("14: ## Proxies", missing)

    def test_ranked_passages_choose_relevant_paragraphs_in_document_order(self):
        passages = out.ranked_passages(PAGE, "how to install", 400)
        self.assertLess(
            passages.index("Run the installer"), passages.index("make install")
        )
        self.assertNotIn("trust_env", passages)
        self.assertEqual(out.ranked_passages(PAGE, "kubernetes", 400), out.NO_PASSAGES)

    def fetch(self, *tokens, pages):
        output = io.StringIO()
        with (
            patch.object(
                commands,
                "cached_call",
                side_effect=lambda s, t, a, f, **o: pages[a["url"]],
            ),
            contextlib.redirect_stdout(output),
        ):
            commands.fetch(self.args("fetch", *tokens))
        return output.getvalue()

    def test_long_page_preview_starts_with_its_outline(self):
        pages = {"https://a.test": PAGE + "filler line\n" * 200}
        output = self.fetch("https://a.test", "--max-chars", "600", pages=pages)
        self.assertIn("Outline (line: heading)", output)
        self.assertIn("14: ## Proxies", output)

    def test_fetch_query_and_section_select_from_the_page(self):
        pages = {"https://a.test": PAGE}
        self.assertIn(
            "[lines 16-16 | Proxies]",
            self.fetch(
                "https://a.test", "--query", "ignore proxy variables", pages=pages
            ),
        )
        section = self.fetch("https://a.test", "--section", "install", pages=pages)
        self.assertIn("[lines 5-13]", section)
        self.assertNotIn("trust_env", section)
        with self.assertRaisesRegex(config.ResearchError, "only one of"):
            self.args("fetch", "https://a.test", "--match", "x", "--section", "y")

    def test_fetch_json_emits_one_record_per_url_including_failures(self):
        def retrieve(args, url, client):
            if url.endswith("b.test"):
                return commands.FetchResult(
                    error=config.ResearchError("raw fetch: HTTP 404", "fix the URL")
                )
            return commands.FetchResult(text=PAGE, source="direct HTTP, markdown")

        output = io.StringIO()
        with (
            patch.object(commands, "fetch_result", side_effect=retrieve),
            contextlib.redirect_stdout(output),
        ):
            commands.fetch(
                self.args("fetch", "https://a.test", "https://b.test", "--json")
            )
        first, second = map(json.loads, output.getvalue().splitlines())
        self.assertEqual(Path(first["saved"]).read_text(), PAGE)
        self.assertEqual(
            (first["lines"], first["source"]), (20, "direct HTTP, markdown")
        )
        self.assertEqual(
            second,
            {
                "url": "https://b.test",
                "error": "raw fetch: HTTP 404",
                "hint": "fix the URL",
                "notices": [],
            },
        )

    def provider_client(self, body, status=200):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(status, json=body)

        return httpx.Client(transport=httpx.MockTransport(handler)), requests

    def test_brave_builds_operators_and_unescapes_entities(self):
        body = {
            "web": {
                "results": [
                    {
                        "title": "A &amp; B",
                        "url": "https://a.test",
                        "description": "say &quot;hi&quot;",
                        "page_age": "2026-05-06T01:02:03",
                    }
                ]
            }
        }
        client, requests = self.provider_client(body)
        arguments = {
            "queries": ["q"],
            "n": 50,
            "chars": 1500,
            "domains": ["a.test", "b.test"],
            "exclude": ["c.test"],
            "after": "2026-01-01",
            "before": "2026-02-01",
        }
        with patch.object(providers, "provider_key", return_value="secret"):
            results = json.loads(providers.search_brave(arguments, client=client))
        params = requests[0].url.params
        self.assertEqual(params["q"], "(site:a.test OR site:b.test) q -site:c.test")
        self.assertEqual(
            (params["count"], params["freshness"]), ("20", "2026-01-01to2026-02-01")
        )
        self.assertEqual(requests[0].headers["X-Subscription-Token"], "secret")
        self.assertEqual(
            results,
            [
                {
                    "title": "A & B",
                    "url": "https://a.test",
                    "date": "2026-05-06",
                    "text": 'say "hi"',
                }
            ],
        )

    def test_parallel_and_tavily_send_filters_and_normalize_results(self):
        client, requests = self.provider_client(
            {
                "results": [
                    {
                        "title": "P",
                        "url": "https://p.test",
                        "publish_date": None,
                        "excerpts": ["one", "two"],
                    }
                ]
            }
        )
        arguments = {
            "queries": ["a", "b"],
            "n": 4,
            "chars": 700,
            "domains": ["p.test"],
            "after": "2026-01-01",
        }
        with patch.object(providers, "provider_key", return_value="secret"):
            results = json.loads(providers.search_parallel(arguments, client=client))
        sent = json.loads(requests[0].content)
        self.assertEqual((sent["search_queries"], sent["objective"]), (["a", "b"], "a"))
        self.assertEqual(
            sent["advanced_settings"],
            {
                "max_results": 4,
                "excerpt_settings": {"max_chars_per_result": 700},
                "source_policy": {
                    "include_domains": ["p.test"],
                    "after_date": "2026-01-01",
                },
            },
        )
        self.assertEqual(
            results,
            [
                {
                    "title": "P",
                    "url": "https://p.test",
                    "date": "",
                    "text": "one\n...\ntwo",
                }
            ],
        )

        client, requests = self.provider_client(
            {
                "results": [
                    {
                        "title": "T",
                        "url": "https://t.test",
                        "content": "c",
                        "published_date": "2026-03-04",
                    }
                ]
            }
        )
        with patch.object(providers, "provider_key", return_value="secret"):
            results = json.loads(
                providers.search_tavily(
                    {"queries": ["a"], "n": 3, "chars": 1, "before": "2026-02-01"},
                    client=client,
                )
            )
        sent = json.loads(requests[0].content)
        self.assertEqual(
            (sent["query"], sent["max_results"], sent["end_date"]),
            ("a", 3, "2026-02-01"),
        )
        self.assertEqual(requests[0].headers["Authorization"], "Bearer secret")
        self.assertEqual(results[0]["date"], "2026-03-04")

    def test_provider_http_errors_name_the_key_or_suggest_another_backend(self):
        for status, hint in (
            (401, "~/.secrets/tavily-api-key"),
            (429, "another --backend"),
        ):
            client, _ = self.provider_client({"detail": "no"}, status)
            with (
                self.subTest(status=status),
                self.assertRaises(config.ResearchError) as raised,
            ):
                providers.search_tavily(
                    {"queries": ["a"], "n": 3, "chars": 1}, client=client
                )
            self.assertIn(hint, raised.exception.hint)

    def test_cache_dispatches_and_reuses_provider_searches(self):
        searcher = unittest.mock.Mock(return_value="[]")
        with patch.dict(cache.SEARCHERS, {"brave": searcher}):
            for _ in range(2):
                self.assertEqual(
                    cache.cached_call("brave", "search", {"queries": ["q"]}), "[]"
                )
        searcher.assert_called_once_with({"queries": ["q"]})

    def test_short_hit_brings_the_paragraph_that_explains_it(self):
        text = "## API\n\nshutdown(immediate=False)\n\nStops the queue.\n\nOther words."
        self.assertEqual(
            out.ranked_passages(text, "shutdown", 400),
            "[lines 3-5 | API]\nshutdown(immediate=False)\n\nStops the queue.",
        )

    def test_heading_labels_drop_permalinks_and_link_targets(self):
        lines = [
            '## Queue[¶](#queue "Link to this heading")',
            "## [Docs](https://x.test)",
        ]
        self.assertEqual([name for *_, name in out.headings(lines)], ["Queue", "Docs"])

    def test_garbled_snippet_is_dropped_and_filled_by_another_provider(self):
        garbled = hit("https://a.test", "\ufffd\x01" * 40)
        (merged,) = search.fuse(
            [("exa", [garbled]), ("brave", [hit("https://a.test", "clean")])], 5
        )
        self.assertEqual(
            (merged["text"], merged["providers"]), ("clean", ["exa", "brave"])
        )

    def test_dates_normalize_to_iso_or_empty(self):
        cases = {
            "2026-05-06T01:02:03Z": "2026-05-06",
            "Mon, 05 Oct 2026 10:00:00 GMT": "2026-10-05",
            "3 days ago": "",
            None: "",
        }
        for value, expected in cases.items():
            self.assertEqual(providers.iso_date(value), expected)

    def test_github_file_pages_are_read_as_raw_source_with_page_fallback(self):
        url = "https://github.com/o/r/blob/main/src/a.py"
        seen = []

        def download(target, *args, **kwargs):
            seen.append(target)
            if "raw.githubusercontent.com" in target and fail:
                raise config.ResearchError("raw fetch: HTTP 404")
            return "# not a heading\nprint(1)\n", "text/plain"

        for fail in (False, True):
            seen.clear()
            with patch.object(pages, "download", side_effect=download):
                self.assertIn("print(1)", pages.fetch_page(url))
            raw = "https://raw.githubusercontent.com/o/r/main/src/a.py"
            self.assertEqual(seen, [raw, url] if fail else [raw])

    def test_brave_retries_when_rate_limited_then_gives_up(self):
        responses = [
            httpx.Response(429, json={}),
            httpx.Response(200, json={"web": {}}),
        ]
        client = httpx.Client(transport=httpx.MockTransport(lambda r: responses.pop(0)))
        with (
            patch.object(providers, "provider_key", return_value="secret"),
            patch.object(providers, "BRAVE_INTERVAL_SECONDS", 0),
        ):
            self.assertEqual(
                providers.search_brave({"queries": ["q"], "n": 1}, client=client), "[]"
            )
            with self.assertRaises(config.ResearchError) as raised:
                responses.extend([httpx.Response(429, json={})] * 3)
                providers.search_brave({"queries": ["q"], "n": 1}, client=client)
        self.assertEqual(raised.exception.status, 429)

    def test_oversized_and_javascript_pages_fail_in_the_right_direction(self):
        with patch.object(config, "MAX_RAW_BYTES", 10):
            client = httpx.Client(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, text="x" * 50)
                )
            )
            with self.assertRaises(config.ResearchError) as raised:
                pages.download("https://big.test/api.json", client=client)
        self.assertTrue(raised.exception.final)
        shell = (
            "<main><h1>Wheels</h1><p>"
            + "intro " * 60
            + "</p><p>This site requires JavaScript to be enabled.</p></main>"
        )
        with (
            patch.object(pages, "download", return_value=(shell, "text/html")),
            self.assertRaisesRegex(config.ResearchError, "needs JavaScript") as raised,
        ):
            pages.fetch_page("https://shell.test")
        self.assertFalse(raised.exception.final)

    def test_broad_match_previews_the_rarest_alternative_first(self):
        text = "\n".join(
            [*(f"index entry {n}" for n in range(60)), "io_uring needs liburing"]
        )
        excerpt = out.matching_lines(text, re.compile("index|io_uring"), 2, 300)
        self.assertIn("61: io_uring needs liburing", excerpt)
        self.assertRegex(excerpt, r"^\[\d+ of 61 matching lines, rarest")
        self.assertLessEqual(len(excerpt), 300)
        self.assertNotIn(
            "matching lines,", out.matching_lines(text, re.compile("io_uring"), 0, 300)
        )

    def test_lines_selector_prints_the_cited_range(self):
        pages_ = {"https://a.test": PAGE}
        output = self.fetch("https://a.test", "--lines", "14-16", pages=pages_)
        self.assertIn("14: ## Proxies\n15: \n16: Set trust_env", output)
        self.assertIn(
            "No such lines; this response has 20.",
            self.fetch("https://a.test", "--lines", "90-95", pages=pages_),
        )
        for bad in ("5", "9-3", "0-4"):
            with self.subTest(bad=bad), self.assertRaises(config.ResearchError):
                self.args("fetch", "https://a.test", "--lines", bad)

    def test_page_title_and_date_outside_the_article_are_kept(self):
        html = (
            "<html><head><title>Redpanda 21.10.1 | Jepsen</title></head><body>"
            "<header><h1>Redpanda 21.10.1</h1><div class=date>2022-04-29</div></header>"
            "<article><h1>1 Background</h1><p>"
            + "text " * 80
            + "</p></article></body></html>"
        )
        markdown = pages.html_to_markdown(html, "https://jepsen.test/a")
        self.assertTrue(
            markdown.startswith(
                "# Redpanda 21.10.1 | Jepsen\n\nPublished: 2022-04-29\n\n# 1 Background"
            )
        )
        titled = html.replace("<h1>1 Background</h1>", "<h1>Redpanda 21.10.1</h1>")
        self.assertTrue(
            pages.html_to_markdown(titled, "https://jepsen.test/a").startswith(
                "Published: 2022-04-29\n\n# Redpanda"
            )
        )

    def test_redirected_pages_say_where_they_came_from(self):
        def handler(request):
            if request.url.path == "/old":
                return httpx.Response(
                    302, headers={"Location": "https://docs.test/landing"}
                )
            return httpx.Response(
                200, html="<main><h1>Landing</h1><p>" + "x " * 150 + "</p></main>"
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        page = pages.fetch_page("https://docs.test/old", client=client)
        self.assertTrue(page.startswith("[redirected to https://docs.test/landing;"))
        self.assertNotIn(
            "redirected",
            pages.fetch_page("https://www.docs.test/landing/", client=client),
        )
        body = {
            "success": True,
            "data": {
                "markdown": "generic guide",
                "metadata": {"url": "https://docs.test/home", "statusCode": 200},
            },
        }
        client = httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body))
        )
        with patch.object(firecrawl, "api_key", return_value="k"):
            self.assertTrue(
                firecrawl.scrape_page(
                    "https://docs.test/aio", client=client
                ).startswith("[redirected to https://docs.test/home;")
            )

    def test_missing_github_path_hint_names_the_directory_listing(self):
        client = httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(404))
        )
        for url in (
            "https://raw.githubusercontent.com/tikv/pd/v8.5.0/pkg/tso/timestamp.go",
            "https://github.com/tikv/pd/blob/v8.5.0/pkg/tso/timestamp.go",
        ):
            with (
                self.subTest(url=url),
                self.assertRaises(config.ResearchError) as raised,
            ):
                pages.fetch_page(url, client=client)
            self.assertIn(
                "api.github.com/repos/tikv/pd/contents/pkg/tso?ref=v8.5.0",
                raised.exception.hint,
            )
            self.assertIn("--repo tikv/pd", raised.exception.hint)

    def test_result_count_scales_with_the_number_of_queries(self):
        def respond(service, tool, arguments, fresh, **options):
            return json.dumps(
                [hit(f"https://{arguments['queries'][0]}.test/{n}") for n in range(9)]
            )

        _, call = self.run_web(
            "a", "b", "c", "d", "e", "--backend", "tavily", respond=respond
        )
        self.assertEqual(call.call_args.args[2]["n"], 15)

    def test_matches_are_labelled_with_their_governing_heading(self):
        text = "# Notes\n\n## September 4, 2025\n\nIn-place resize is available.\n\n## October 1, 2025\n\nfiller\n\nResize limits changed."
        self.assertEqual(
            out.matching_lines(text, re.compile("(?i)resize"), 0),
            "§ September 4, 2025 (line 3)\n5: In-place resize is available.\n"
            "§ October 1, 2025 (line 7)\n...\n11: Resize limits changed.",
        )
        self.assertEqual(
            out.matching_lines(text, re.compile("October"), 0), "7: ## October 1, 2025"
        )

    def test_github_threads_render_state_dates_and_maintainer_comments(self):
        issue = {
            "title": "Fix resize race",
            "number": 136160,
            "repository_url": "https://api.github.com/repos/kubernetes/kubernetes",
            "state": "closed",
            "created_at": "2026-01-02T03:04:05Z",
            "closed_at": "2026-06-14T00:00:00Z",
            "user": {"login": "alice"},
            "author_association": "CONTRIBUTOR",
            "labels": [{"name": "sig/node"}],
            "body": "Body text.",
            "comments": 2,
            "pull_request": {"merged_at": None},
        }
        comments = [
            {
                "user": {"login": "bob"},
                "author_association": "MEMBER",
                "created_at": "2026-06-14T01:00:00Z",
                "body": "Closing: superseded.",
            },
            {
                "user": {"login": "carol"},
                "author_association": "NONE",
                "created_at": "2026-06-15T01:00:00Z",
                "body": "ok",
            },
        ]
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(
                200, json=comments if request.url.path.endswith("/comments") else issue
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        with patch.object(github, "github_token", return_value="tok"):
            page = pages.fetch_page(
                "https://github.com/kubernetes/kubernetes/pull/136160", client=client
            )
        self.assertTrue(
            page.startswith(
                "# Fix resize race\n\nPull request #136160 in kubernetes/kubernetes: closed without merging | opened 2026-01-02 by alice | closed 2026-06-14 | labels: sig/node"
            )
        )
        self.assertIn(
            "## Comments (2 of 2); review comments on the diff are not included", page
        )
        self.assertIn("### bob (member) on 2026-06-14\n\nClosing: superseded.", page)
        self.assertIn("### carol on 2026-06-15", page)
        self.assertEqual({r.url.host for r in requests}, {"api.github.com"})
        self.assertEqual(requests[0].headers["Authorization"], "Bearer tok")

    def test_github_token_stays_on_the_api_host_and_rate_limits_are_final(self):
        with patch.object(github, "github_token", return_value="tok"):
            self.assertEqual(github.api_headers("https://github.com/o/r"), {})
            self.assertEqual(github.api_headers("http://api.github.com/x"), {})
            self.assertEqual(
                github.api_headers("https://raw.githubusercontent.com/o/r/m/f"), {}
            )
            client = httpx.Client(
                transport=httpx.MockTransport(lambda r: httpx.Response(403))
            )
            with self.assertRaises(config.ResearchError) as raised:
                pages.download(
                    "https://api.github.com/repos/o/r/git/trees/x", client=client
                )
            self.assertTrue(raised.exception.final)
            self.assertIn("GITHUB_TOKEN", raised.exception.hint)
            html = "<main><h1>Issue page</h1><p>" + "words " * 100 + "</p></main>"

            def handler(request):
                if request.url.host == "api.github.com":
                    return httpx.Response(403)
                return httpx.Response(200, html=html)

            client = httpx.Client(transport=httpx.MockTransport(handler))
            self.assertIn(
                "Issue page",
                pages.fetch_page("https://github.com/o/r/issues/5", client=client),
            )

    def test_thin_exa_extraction_tries_firecrawl_and_keeps_exa_if_that_fails(self):
        def retrieve(fail):
            def respond(service, tool, arguments, fresh, **options):
                if service == "page":
                    raise config.ResearchError("page has little static content")
                if service == "exa":
                    return "shell"
                if fail:
                    raise config.ResearchError("Firecrawl: HTTP 402")
                return "rendered page"

            return respond

        for fail, expected in ((False, "rendered page"), (True, "shell")):
            output = io.StringIO()
            with (
                patch.object(commands, "cached_call", side_effect=retrieve(fail)),
                patch.object(commands, "api_key", return_value="key"),
                contextlib.redirect_stdout(output),
            ):
                commands.fetch(self.args("fetch", "https://app.test"))
            self.assertIn(
                "[Exa returned only 5 chars; trying Firecrawl]", output.getvalue()
            )
            self.assertTrue(output.getvalue().rstrip().endswith(expected))

    def test_same_content_from_two_urls_is_saved_to_two_paths(self):
        first = out.save_text("same", "fetch-https://github.com/o/r/blob/v1/a.rs")
        second = out.save_text("same", "fetch-https://github.com/o/r/blob/v2/a.rs")
        self.assertNotEqual(first, second)
