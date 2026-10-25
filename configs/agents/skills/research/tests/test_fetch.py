"""`fetch`: direct reads, site APIs, fallbacks, batches, and selectors."""

import json
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx2

from research_cli import config, transport
from support import ResearchTestCase, html_page, mcp_text, tool_call

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
ARTICLE = "<main><h1>Article</h1><p>" + "Readable content. " * 40 + "</p></main>"
SHELL = "<html><body><div id='root'></div><script>app()</script></body></html>"


def markdown(text: str = PAGE) -> httpx2.Response:
    return httpx2.Response(200, text=text, headers={"Content-Type": "text/markdown"})


class DirectFetchTests(ResearchTestCase):
    def test_markdown_passes_through_from_the_browser_client(self):
        self.web.serve("docs.test", markdown)
        result = self.ok("fetch", "https://docs.test/guide")
        self.assertIn(
            "URL: https://docs.test/guide [direct HTTP, markdown]", result.stdout
        )
        self.assertIn("Set trust_env to False", result.stdout)
        sent = self.web.sent[0]
        self.assertEqual(sent.transport, "browser")
        self.assertTrue(sent.headers["accept"].startswith("text/markdown"))

    def test_html_becomes_main_content_markdown_with_absolute_links(self):
        html = (
            "<nav><a href='/nav'>Navigation</a></nav><main><h1>Title</h1><p>"
            + "Body text. " * 30
            + "</p><a href='/guide'>guide</a> <a href='#frag'>frag</a> <a href>bare</a>"
            "<pre><code>print('hi')</code></pre><img src='x.png' alt='pic'></main>"
            "<footer>Copyright</footer><script>var x=1</script>"
        )
        self.web.serve("example.test", lambda: html_page(html, "t"))
        output = self.ok(
            "fetch", "https://example.test/docs/", "--max-chars", "0"
        ).stdout
        for expected in (
            "# Title",
            "(https://example.test/guide)",
            "(#frag)",
            "```",
            "bare",
        ):
            self.assertIn(expected, output)
        for noise in ("Navigation", "Copyright", "var x", "x.png"):
            self.assertNotIn(noise, output)

    def test_page_title_and_date_outside_the_article_lead_the_text(self):
        html = (
            "<header><h1>Redpanda 21.10.1</h1><div class=date>2022-04-29</div></header>"
            "<article><h1>1 Background</h1><p>" + "text " * 80 + "</p></article>"
        )
        self.web.serve(
            "jepsen.test", lambda: html_page(html, "Redpanda 21.10.1 | Jepsen")
        )
        output = self.ok("fetch", "https://jepsen.test/a").stdout
        self.assertIn(
            "# Redpanda 21.10.1 | Jepsen\n\nPublished: 2022-04-29\n\n# 1 Background",
            output,
        )

    def test_several_timestamps_are_flagged_as_the_first_of_many(self):
        post = "<article><time datetime='{}'>Oct</time><p>{}</p></article>"
        body = "".join(
            post.format(stamp, "text " * 80)
            for stamp in ("2026-10-07T05:09:04Z", "2026-10-07T05:09:04Z", "2026-10-01")
        )
        self.web.serve("feed.test", lambda: html_page(body, "Results"))
        self.assertIn(
            "Published: 2026-10-07T05:09:04Z (first of 2 timestamps on the page)",
            self.ok("fetch", "https://feed.test").stdout,
        )

    def test_json_is_pretty_printed_for_line_based_reading(self):
        self.web.serve("api.test", lambda: httpx2.Response(200, json={"a": {"b": 1}}))
        self.assertIn(
            '{\n  "a": {\n    "b": 1\n  }\n}',
            self.ok("fetch", "https://api.test/x").stdout,
        )

    def test_redirect_is_announced_and_relative_links_follow_the_destination(self):
        self.web.serve(
            "old.test",
            lambda: httpx2.Response(
                302, headers={"Location": "https://docs.test/v2/guide/"}
            ),
        )
        links = '<a href="../reference/">API</a> <a href="#section">Section</a></main>'
        body = ARTICLE.replace("</main>", links)
        self.web.serve("docs.test", lambda: html_page(body))
        self.web.serve("www.docs.test", lambda: html_page(body))
        output = self.ok("fetch", "https://old.test/start", "--max-chars", "0").stdout
        self.assertIn("[redirected to https://docs.test/v2/guide/;", output)
        self.assertIn("[API](https://docs.test/v2/reference/)", output)
        self.assertIn("[Section](#section)", output)
        self.assertNotIn(
            "redirected", self.ok("fetch", "https://www.docs.test/v2/guide/").stdout
        )

    def test_refused_browser_is_retried_with_the_plain_client(self):
        def picky(request, name):
            if name == "browser":
                return httpx2.Response(403, text="denied")
            return markdown()

        self.web.route("picky.test", picky)
        output = self.ok("fetch", "https://picky.test").stdout
        self.assertIn("Set trust_env", output)
        self.assertEqual(
            [sent.transport for sent in self.web.sent], ["browser", "plain"]
        )


class FallbackTests(ResearchTestCase):
    def exa_returns(self, text: str) -> list[dict]:
        calls: list[dict] = []

        def handler(request, name):
            tool, arguments = tool_call(request)
            calls.append({"tool": tool, **arguments})
            return mcp_text(text)

        self.web.route("mcp.exa.ai", handler)
        return calls

    def test_unrendered_pages_fall_back_to_exa(self):
        cases = {
            "shell": html_page(SHELL),
            "javascript": html_page(
                "<main><h1>Wheels</h1><p>"
                + "intro " * 60
                + "</p><p>This site requires JavaScript to be enabled.</p></main>"
            ),
            "challenge": html_page(
                "<main><h1>Just a moment...</h1><p>"
                + "Checking. " * 100
                + "</p></main>"
            ),
            "loading": html_page("A required part of this site couldn’t load. " * 3),
        }
        for name, response in cases.items():
            with self.subTest(name=name):
                self.web.serve(f"{name}.test", lambda response=response: response)
                calls = self.exa_returns(PAGE)
                output = self.ok("fetch", f"https://{name}.test", "--fresh").stdout
                self.assertIn("falling back to Exa", output)
                self.assertIn(f"URL: https://{name}.test [Exa]", output)
                self.assertEqual(calls[-1]["urls"], [f"https://{name}.test"])

    def test_sign_in_redirect_is_not_returned_as_the_page(self):
        self.web.serve(
            "app.test",
            lambda: httpx2.Response(302, headers={"Location": "/login?next=/thread"}),
        )
        self.web.serve("app.test/login", lambda: html_page(ARTICLE))
        self.exa_returns(PAGE)
        output = self.ok("fetch", "https://app.test/thread").stdout
        self.assertIn("redirected to a sign-in page", output)
        self.assertIn("[Exa]", output)

    def test_missing_page_skips_extraction_and_the_batch_continues(self):
        self.web.serve("gone.test", lambda: httpx2.Response(404))
        self.web.serve("live.test", markdown)
        output = self.ok("fetch", "https://gone.test/x", "https://live.test").stdout
        self.assertIn("[error: HTTP 404 | hint: not served now;", output)
        self.assertIn("Set trust_env", output)
        self.assertNotIn("mcp.exa.ai", " ".join(self.web.urls()))
        result = self.fails("fetch", "https://gone.test/x")
        self.assertIn("error: no URL could be fetched", result.stderr)

    def test_firecrawl_takes_over_when_exa_fails(self):
        self.set_key("firecrawl")
        self.web.serve("blocked.test", lambda: html_page(SHELL))
        self.web.serve("mcp.exa.ai", lambda: httpx2.Response(400, text="bad request"))
        self.web.serve(
            "api.firecrawl.dev",
            lambda: httpx2.Response(
                200, json={"success": True, "data": {"markdown": "# Rendered"}}
            ),
        )
        output = self.ok("fetch", "https://blocked.test", "--fresh").stdout
        self.assertIn("falling back to Firecrawl", output)
        self.assertIn("URL: https://blocked.test [Firecrawl]", output)
        firecrawl = next(sent for sent in self.web.sent if "firecrawl" in sent.url)
        self.assertEqual(firecrawl.json()["maxAge"], 0)
        self.assertEqual(firecrawl.headers["authorization"], "Bearer test-key")

    def test_thin_exa_text_tries_firecrawl_and_is_kept_if_firecrawl_fails(self):
        self.set_key("firecrawl")
        self.web.serve("app.test", lambda: html_page(SHELL))
        self.exa_returns("shell")
        for status, expected in ((200, "# Rendered"), (402, "shell")):
            with self.subTest(status=status):
                self.web.serve(
                    "api.firecrawl.dev",
                    lambda status=status: httpx2.Response(
                        status,
                        json={"success": True, "data": {"markdown": "# Rendered"}},
                    ),
                )
                output = self.ok("fetch", "https://app.test", "--fresh").stdout
                self.assertIn("[Exa returned only 5 chars; trying Firecrawl]", output)
                self.assertTrue(output.rstrip().endswith(expected))

    def test_unconfigured_firecrawl_reports_the_exa_failure(self):
        self.web.serve("blocked.test", lambda: html_page(SHELL))
        self.web.serve("mcp.exa.ai", lambda: httpx2.Response(400, text="bad"))
        output = self.fails("fetch", "https://blocked.test").stdout
        self.assertIn("[error: web_fetch_exa: HTTP 400 bad", output)
        self.assertNotIn("firecrawl", " ".join(self.web.urls()))

    def test_exa_flag_sends_one_deduplicated_batch(self):
        calls = self.exa_returns(PAGE)
        self.ok(
            "fetch", "--exa", "https://one.test", "https://one.test", "https://two.test"
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["urls"], ["https://one.test", "https://two.test"])

    def test_firecrawl_flag_reads_only_through_firecrawl(self):
        self.set_key("firecrawl")
        self.web.serve(
            "api.firecrawl.dev",
            lambda: httpx2.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "markdown": "guide",
                        "metadata": {"url": "https://docs.test/home"},
                    },
                },
            ),
        )
        output = self.ok("fetch", "--firecrawl", "https://docs.test/aio").stdout
        self.assertIn("[Firecrawl]", output)
        self.assertIn("[redirected to https://docs.test/home;", output)
        self.assertEqual(len(self.web.sent), 1)
        self.assertNotIn("maxAge", self.web.sent[0].json())

    def test_firecrawl_errors_are_actionable_and_never_echo_the_body(self):
        self.set_key("firecrawl", "secret-key")
        for status, hint in (
            (401, "FIRECRAWL_API_KEY"),
            (402, "credits"),
            (500, "another source"),
        ):
            with self.subTest(status=status):
                self.web.serve(
                    "api.firecrawl.dev",
                    lambda status=status: httpx2.Response(
                        status, text="echo secret-key"
                    ),
                )
                output = self.fails(
                    "fetch", "--firecrawl", "https://a.test", "--fresh"
                ).stdout
                self.assertIn(f"Firecrawl: HTTP {status} | hint:", output)
                self.assertIn(hint, output)
                self.assertNotIn("secret-key", output)

    def test_firecrawl_rejects_unsuccessful_and_empty_results(self):
        self.set_key("firecrawl")
        for body in (
            [],
            {"success": False},
            {"success": True, "data": []},
            {"success": True, "data": {"markdown": "  "}},
            {
                "success": True,
                "data": {"markdown": "x", "metadata": {"statusCode": 403}},
            },
        ):
            with self.subTest(body=body):
                self.web.serve(
                    "api.firecrawl.dev",
                    lambda body=body: httpx2.Response(200, json=body),
                )
                self.fails("fetch", "--firecrawl", "https://a.test", "--fresh")
        self.assertEqual(list(config.CACHE.iterdir()), [])

    def test_firecrawl_without_a_key_sends_nothing(self):
        result = self.fails("fetch", "--firecrawl", "https://a.test")
        self.assertIn("Firecrawl key not configured", result.stdout)
        self.assertEqual(self.web.sent, [])

    def test_invalid_urls_never_reach_the_network(self):
        for url in (
            "file:///etc/passwd",
            "https://user:secret@example.com",
            "https://[",
            "not-a-url",
        ):
            for mode in ((), ("--raw",), ("--exa",), ("--firecrawl",)):
                with self.subTest(url=url, mode=mode):
                    result = self.fails("fetch", url, *mode)
                    self.assertNotIn("Exa extraction", result.stdout)
        self.assertEqual(self.web.sent, [])


class SiteApiTests(ResearchTestCase):
    def test_github_blob_is_read_as_the_raw_file(self):
        self.web.serve(
            "raw.githubusercontent.com", lambda: httpx2.Response(200, text="print(1)\n")
        )
        output = self.ok("fetch", "https://github.com/o/r/blob/main/src/a.py").stdout
        self.assertIn("[GitHub raw file]", output)
        self.assertEqual(
            self.web.urls(), ["https://raw.githubusercontent.com/o/r/main/src/a.py"]
        )

    def test_comment_lines_in_source_files_are_not_headings(self):
        source = "# Copyright\n\nimport os\n\n# helpers\n" + "x = os.sep\n" * 300
        self.web.serve(
            "raw.githubusercontent.com", lambda: httpx2.Response(200, text=source)
        )
        python = "https://github.com/o/r/blob/main/a.py"
        output = self.ok("fetch", python, "--match", "os.sep", "--max-chars", "300")
        self.assertNotIn("§", output.stdout)
        self.assertNotIn(
            "Outline", self.ok("fetch", python, "--max-chars", "300").stdout
        )
        sections = self.ok("fetch", python, "--section", "helpers").stdout
        self.assertIn("It has no markdown headings; use --match.", sections)
        readme = "https://github.com/o/r/blob/main/README.md"
        matched = self.ok("fetch", readme, "--match", "import", "--context", "0")
        self.assertIn("§ Copyright (line 1)", matched.stdout)
        self.assertIn(
            "[lines 5-", self.ok("fetch", readme, "--section", "helpers").stdout
        )

    def test_missing_github_path_names_the_directory_listing(self):
        self.web.serve("raw.githubusercontent.com", lambda: httpx2.Response(404))
        self.web.serve("github.com", lambda: httpx2.Response(404))
        for url in (
            "https://raw.githubusercontent.com/tikv/pd/v8.5.0/pkg/tso/timestamp.go",
            "https://github.com/tikv/pd/blob/v8.5.0/pkg/tso/timestamp.go",
        ):
            with self.subTest(url=url):
                output = self.fails("fetch", url).stdout
                self.assertIn(
                    "api.github.com/repos/tikv/pd/contents/pkg/tso?ref=v8.5.0", output
                )
                self.assertIn("--repo tikv/pd", output)

    def test_github_threads_render_state_and_maintainer_comments(self):
        issue = {
            "title": "Fix resize race",
            "number": 7,
            "repository_url": "https://api.github.com/repos/o/r",
            "state": "closed",
            "created_at": "2026-01-02T03:04:05Z",
            "closed_at": "2026-06-14T00:00:00Z",
            "user": {"login": "alice"},
            "author_association": "CONTRIBUTOR",
            "labels": [{"name": "bug"}],
            "body": "# Steps\n\nBody text.",
            "comments": 2,
            "pull_request": {"merged_at": None},
        }
        comments = [
            {
                "user": {"login": "bob"},
                "author_association": "MEMBER",
                "created_at": "2026-06-14T01:00:00Z",
                "body": "## Why\nSuperseded.",
            },
            {
                "user": {"login": "carol"},
                "author_association": "NONE",
                "created_at": "2026-06-15T01:00:00Z",
                "body": "ok",
            },
        ]
        self.web.route(
            "api.github.com",
            lambda request, name: httpx2.Response(
                200, json=comments if request.url.path.endswith("/comments") else issue
            ),
        )
        with patch("research_cli.github.github_token", return_value="tok"):
            output = self.ok(
                "fetch", "https://github.com/o/r/pull/7", "--max-chars", "0"
            ).stdout
        self.assertIn(
            "Pull request #7 in o/r: closed without merging"
            " | opened 2026-01-02 by alice | closed 2026-06-14 | labels: bug",
            output,
        )
        self.assertIn(
            "## Comments (2 of 2); review comments on the diff are not included", output
        )
        self.assertIn("### bob (member) on 2026-06-14\n\n##### Why", output)
        self.assertIn("### Steps", output)  # body headings sit below the title
        self.assertEqual(
            {sent.headers["authorization"] for sent in self.web.sent}, {"Bearer tok"}
        )

    def test_rate_limited_github_api_falls_back_to_the_page(self):
        self.web.serve("api.github.com", lambda: httpx2.Response(403))
        self.web.serve("github.com/o/r/issues", lambda: html_page(ARTICLE))
        output = self.ok("fetch", "https://github.com/o/r/issues/5").stdout
        self.assertIn(
            "[GitHub API unavailable: GitHub API: HTTP 403 (rate limit)", output
        )
        self.assertIn("Readable content", output)

    def test_direct_github_api_rate_limit_is_final_with_a_token_hint(self):
        self.web.serve("api.github.com", lambda: httpx2.Response(403))
        output = self.fails(
            "fetch", "https://api.github.com/repos/o/r/git/trees/x"
        ).stdout
        self.assertIn("GITHUB_TOKEN", output)
        self.assertNotIn("Exa", output)

    def test_token_is_sent_only_to_the_api_host(self):
        from research_cli import github

        with patch.object(github, "github_token", return_value="tok"):
            self.assertEqual(github.api_headers("https://github.com/o/r"), {})
            self.assertEqual(github.api_headers("http://api.github.com/x"), {})
            self.assertEqual(
                github.api_headers("https://api.github.com/x"),
                {"Authorization": "Bearer tok"},
            )

    def stack_exchange(
        self, answers: list[dict], extra: list[dict] | None = None
    ) -> list[str]:
        question = {
            "question_id": 11,
            "title": "How &amp; why?",
            "score": 5,
            "answer_count": 3,
            "accepted_answer_id": 30,
            "creation_date": 1_700_000_000,
            "tags": ["python"],
            "owner": {"display_name": "Ann"},
            "body": "<p>Question body</p><h1>Context</h1>",
        }
        paths: list[str] = []

        def handler(request, name):
            paths.append(f"{request.url.path}?{request.url.query.decode()}")
            path = request.url.path
            if path.endswith("/answers"):
                return httpx2.Response(200, json={"items": answers})
            if path.startswith("/2.3/answers/"):
                return httpx2.Response(200, json={"items": extra or []})
            return httpx2.Response(200, json={"items": [question]})

        self.web.route("api.stackexchange.com", handler)
        return paths

    def answer(
        self, answer_id: int, score: int, *, body: bool = True, accepted: bool = False
    ) -> dict:
        item = {
            "answer_id": answer_id,
            "question_id": 11,
            "score": score,
            "is_accepted": accepted,
            "creation_date": 1_700_100_000,
            "owner": {"display_name": f"user{answer_id}"},
        }
        if body:
            item["body"] = f"<p>Answer {answer_id} text</p><h2>Detail</h2>"
        return item

    def test_stack_exchange_question_renders_votes_acceptance_and_dates(self):
        self.stack_exchange([self.answer(20, 9), self.answer(30, 4, accepted=True)])
        output = self.ok(
            "fetch",
            "https://stackoverflow.com/questions/11/how-why",
            "--max-chars",
            "0",
        ).stdout
        self.assertIn(
            "URL: https://stackoverflow.com/questions/11/how-why [Stack Exchange API]",
            output,
        )
        self.assertIn("# How & why?", output)
        self.assertIn(
            "Question 11 on stackoverflow.com | score 5 | asked 2023-11-14 by Ann",
            output,
        )
        self.assertIn("## Answers (2 of 3, highest score first)", output)
        self.assertIn(
            "### Answer 30: score 4, accepted | answered 2023-11-16 by user30", output
        )
        self.assertIn("### Context", output)
        self.assertIn("##### Detail", output)
        self.assertLess(output.index("Answer 20:"), output.index("Answer 30:"))

    def test_answer_links_mark_the_linked_answer_and_refetch_missing_bodies(self):
        paths = self.stack_exchange(
            [self.answer(20, 9, body=False)],
            extra=[
                self.answer(20, 9),
                self.answer(30, 4, accepted=True),
                self.answer(40, 1),
            ],
        )
        linked = {"items": [{"answer_id": 40, "question_id": 11}]}
        self.web.serve(
            "api.stackexchange.com/2.3/answers/40",
            lambda: httpx2.Response(200, json=linked),
        )
        output = self.ok(
            "fetch", "https://unix.stackexchange.com/a/40", "--max-chars", "0"
        ).stdout
        self.assertIn("Answer 20 text", output)
        self.assertIn("### Answer 40: score 1, the linked answer", output)
        self.assertTrue(any("answers/20;30;40" in path for path in paths), paths)
        self.assertTrue(all("site=unix.stackexchange.com" in path for path in paths))

    def test_stack_exchange_failure_falls_back_to_the_page(self):
        self.web.serve(
            "api.stackexchange.com",
            lambda: httpx2.Response(400, json={"error_name": "throttle_violation"}),
        )
        self.web.serve("serverfault.com", lambda: html_page(ARTICLE))
        output = self.ok("fetch", "https://serverfault.com/questions/5").stdout
        self.assertIn("[Stack Exchange API: HTTP 400", output)
        self.assertIn("Readable content", output)

    def test_non_question_stack_exchange_pages_are_read_directly(self):
        self.web.serve("stackexchange.com", lambda: html_page(ARTICLE))
        self.web.serve("stackoverflow.com", lambda: html_page(ARTICLE))
        self.ok(
            "fetch",
            "https://stackexchange.com/questions/5",
            "https://stackoverflow.com/users/1",
        )
        self.assertNotIn("api.stackexchange.com", " ".join(self.web.urls()))


class BatchTests(ResearchTestCase):
    def test_batch_runs_concurrently_bounded_and_prints_in_order(self):
        urls = [f"https://site{n}.test" for n in range(12)]
        lock = threading.Condition()
        active = peak = 0
        release = threading.Event()

        def slow(request, name):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
                lock.notify_all()
            if not release.wait(5):
                raise AssertionError("fetches did not overlap")
            with lock:
                active -= 1
            return markdown(f"# Page {request.url.host}\n")

        for url in urls:
            self.web.route(url.removeprefix("https://"), slow)
        with lock:
            pass

        def open_gate():
            with lock:
                lock.wait_for(lambda: active == config.MAX_WORKERS, timeout=5)
            release.set()

        threading.Thread(target=open_gate).start()
        output = self.ok("fetch", *urls).stdout
        self.assertEqual(peak, config.MAX_WORKERS)
        order = [
            line.split()[1] for line in output.splitlines() if line.startswith("URL:")
        ]
        self.assertEqual(order, urls)
        self.assertEqual(len(self.browsers), 1)
        self.assertTrue(self.browsers[0].closed)

    def test_duplicates_are_fetched_once_and_printed_each_time(self):
        self.web.serve("one.test", lambda: markdown("one"))
        self.web.serve("two.test", lambda: markdown("two"))
        output = self.ok(
            "fetch",
            "https://one.test",
            "https://two.test",
            "https://one.test",
            "--fresh",
        ).stdout
        self.assertEqual(output.count("URL: https://one.test"), 2)
        self.assertEqual(len(self.web.sent), 2)

    def test_failed_duplicates_share_one_attempt(self):
        self.web.serve("bad.test", lambda: httpx2.Response(404))
        output = self.fails("fetch", *["https://bad.test"] * 3).stdout
        self.assertEqual(output.count("[error: HTTP 404"), 3)
        self.assertEqual(len(self.web.sent), 1)

    def test_cached_batch_opens_no_client(self):
        self.web.serve("one.test", lambda: markdown("cached one"))
        first = self.ok("fetch", "https://one.test").stdout
        with (
            patch.object(transport, "new_browser_session", side_effect=AssertionError),
            patch.object(transport, "new_api_client", side_effect=AssertionError),
        ):
            self.assertEqual(self.ok("fetch", "https://one.test").stdout, first)

    def test_raw_batch_splits_the_inline_budget_and_saves_exact_bodies(self):
        self.web.serve("one.test", lambda: httpx2.Response(200, text="a" * 40))
        self.web.serve("two.test", lambda: httpx2.Response(200, text="b\r\n" * 20))
        output = self.ok(
            "fetch",
            "--raw",
            "https://one.test",
            "https://two.test",
            "--max-chars",
            "20",
        ).stdout
        self.assertIn("\n" + "a" * 10 + "\n", output)
        self.assertEqual(output.count("preview 10/"), 1)
        saved = {path.read_bytes() for path in config.OUTPUT.iterdir()}
        self.assertEqual(saved, {b"a" * 40, b"b\r\n" * 20})

    def test_json_emits_one_record_per_url_including_failures(self):
        self.web.serve("a.test", markdown)
        self.web.serve("b.test", lambda: httpx2.Response(404))
        first, second = map(
            json.loads,
            self.ok("fetch", "https://a.test", "https://b.test", "--json").lines,
        )
        self.assertEqual(Path(first["saved"]).read_text(), PAGE)
        self.assertEqual(
            (first["lines"], first["source"]), (20, "direct HTTP, markdown")
        )
        self.assertEqual(second["url"], "https://b.test")
        self.assertEqual(second["error"], "HTTP 404")
        self.assertIn("not served now", second["hint"])


class SelectorTests(ResearchTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.web.serve("a.test", markdown)

    def test_query_returns_relevant_passages_with_line_labels(self):
        output = self.ok(
            "fetch", "https://a.test", "--query", "ignore proxy variables"
        ).stdout
        self.assertIn("[lines 16-16 | Proxies]", output)
        self.assertIn("| excerpt", output)

    def test_section_returns_whole_sections(self):
        output = self.ok("fetch", "https://a.test", "--section", "install").stdout
        self.assertIn("[lines 5-13]", output)
        self.assertNotIn("trust_env", output)

    def test_lines_print_the_cited_range(self):
        self.assertIn(
            "14: ## Proxies\n15: \n16: Set trust_env",
            self.ok("fetch", "https://a.test", "--lines", "14-16").stdout,
        )
        self.assertIn(
            "No such lines; this response has 20.",
            self.ok("fetch", "https://a.test", "--lines", "90-95").stdout,
        )

    def test_long_page_preview_leads_with_its_outline(self):
        self.web.serve("long.test", lambda: markdown(PAGE + "filler line\n" * 200))
        output = self.ok("fetch", "https://long.test", "--max-chars", "600").stdout
        self.assertIn("Outline (line: heading)", output)
        self.assertIn("14: ## Proxies", output)

    def test_no_match_saves_the_full_response_and_says_so(self):
        output = self.ok("fetch", "https://a.test", "--match", "absent").stdout
        self.assertIn("--match: 0 matching lines; full response saved", output)
        self.assertEqual(self.saved(output), PAGE)


if __name__ == "__main__":
    unittest.main()
