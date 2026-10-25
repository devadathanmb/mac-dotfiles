"""Pure text selection, rendering, and date normalisation."""

import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_cli import config
from research_cli.config import work_directory
from research_cli.dates import iso_timestamp
from research_cli.excerpts import (
    NO_PASSAGES,
    demote_headings,
    headings,
    matching_lines,
    matching_sections,
    page_outline,
    ranked_passages,
    terms,
)
from research_cli.extract import require_rendered
from research_cli.output import Selection, render, save_text

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


class ExcerptTests(unittest.TestCase):
    def test_outline_numbers_headings_outside_fences_and_drops_depth_to_fit(self):
        outline = page_outline(PAGE, 1000)
        self.assertIn("5: ## Install", outline)
        self.assertIn("18: ### Details", outline)
        self.assertNotIn("not a heading", outline)
        shallow = page_outline(PAGE, 110)
        self.assertNotIn("Details", shallow)
        self.assertIn("more headings", shallow)

    def test_sections_run_to_the_next_peer_heading_or_list_headings(self):
        section = matching_sections(PAGE, re.compile("prox", re.IGNORECASE))
        self.assertTrue(section.startswith("[lines 14-20]\n## Proxies"))
        self.assertIn("Unrelated closing words.", section)
        missing = matching_sections(PAGE, re.compile("absent"))
        self.assertIn("No heading matches", missing)
        self.assertIn("14: ## Proxies", missing)

    def test_ranked_passages_are_relevant_and_in_document_order(self):
        passages = ranked_passages(PAGE, "how to install", 400)
        self.assertLess(
            passages.index("Run the installer"), passages.index("make install")
        )
        self.assertNotIn("trust_env", passages)
        self.assertEqual(ranked_passages(PAGE, "kubernetes", 400), NO_PASSAGES)

    def test_a_short_hit_brings_the_paragraph_that_explains_it(self):
        text = "## API\n\nshutdown(immediate=False)\n\nStops the queue.\n\nOther words."
        self.assertEqual(
            ranked_passages(text, "shutdown", 400),
            "[lines 3-5 | API]\nshutdown(immediate=False)\n\nStops the queue.",
        )

    def test_separators_are_never_passages_even_under_a_matching_heading(self):
        text = "## Weights\n\n\\--\n\nWeights are learned from data."
        self.assertEqual(
            ranked_passages(text, "weights", 400),
            "[lines 5-5 | Weights]\nWeights are learned from data.",
        )

    def test_matches_merge_context_and_keep_source_line_numbers(self):
        text = "a\nb\nmatch\nd\nmatch\nf\ng\nh\nmatch"
        self.assertEqual(
            matching_lines(text, re.compile("match"), 1),
            "2: b\n3: match\n4: d\n5: match\n6: f\n...\n8: h\n9: match",
        )

    def test_matches_are_labelled_with_their_governing_heading(self):
        text = (
            "# Notes\n\n## September 4, 2025\n\nIn-place resize is available.\n\n"
            "## October 1, 2025\n\nfiller\n\nResize limits changed."
        )
        self.assertEqual(
            matching_lines(text, re.compile("(?i)resize"), 0),
            "§ September 4, 2025 (line 3)\n5: In-place resize is available.\n"
            "§ October 1, 2025 (line 7)\n...\n11: Resize limits changed.",
        )

    def test_broad_matches_preview_the_rarest_alternative_first(self):
        text = "\n".join(
            [*(f"index entry {n}" for n in range(60)), "io_uring needs liburing"]
        )
        excerpt = matching_lines(text, re.compile("index|io_uring"), 2, 300)
        self.assertIn("61: io_uring needs liburing", excerpt)
        self.assertRegex(excerpt, r"^\[\d+ of 61 matching lines, rarest")
        self.assertLessEqual(len(excerpt), 300)

    def test_heading_labels_drop_permalinks_and_link_targets(self):
        lines = [
            '## Queue[¶](#queue "Link to this heading")',
            "## [Docs](https://x.test)",
        ]
        self.assertEqual([name for *_, name in headings(lines)], ["Queue", "Docs"])

    def test_identifiers_are_also_split_into_their_words(self):
        self.assertEqual(
            terms("use_thread_local maxRetries HTTPClient2"),
            [
                "use_thread_local",
                "use",
                "thread",
                "local",
                "maxretries",
                "max",
                "retries",
                "httpclient2",
                "http",
                "client",
            ],
        )

    def test_query_reaches_code_through_identifier_parts(self):
        text = "Intro words.\n\n    self.use_thread_local_curl = True\n\nOther words."
        self.assertIn(
            "use_thread_local_curl", ranked_passages(text, "thread local", 400)
        )

    def test_underlined_headings_count_in_outline_and_sections(self):
        text = (
            "=====\nGuide\n=====\n\nIntro text here.\n\nInstall\n-------\n\n"
            "Run it.\n\nThreads\n-------\n\nOne handle per thread.\n"
        )
        outline = page_outline(text, 1000)
        self.assertIn("2: # Guide", outline)
        self.assertIn("12: ## Threads", outline)
        section = matching_sections(text, re.compile("install", re.IGNORECASE))
        self.assertEqual(section, "[lines 7-11]\nInstall\n-------\n\nRun it.")
        passages = ranked_passages(text, "handle thread", 400)
        self.assertEqual(passages, "[lines 15-15 | Threads]\nOne handle per thread.")

    def test_front_matter_and_rules_under_long_lines_are_not_headings(self):
        text = (
            "---\ndescription: Build serverless apps on the edge\n---\n\n"
            "Body\n\nA long paragraph line\n---\n"
        )
        self.assertEqual(headings(text.splitlines()), [])

    def test_demoted_headings_nest_below_their_container_but_not_in_code(self):
        text = "# Title\n\n```\n# comment\n```\n\n##### Deep"
        self.assertEqual(
            demote_headings(text, 3), "#### Title\n\n```\n# comment\n```\n\n###### Deep"
        )

    def test_challenge_headings_only_count_as_the_first_line(self):
        with self.assertRaisesRegex(Exception, "bot challenge"):
            require_rendered("# Just a moment...\n\n" + "Checking. " * 100)
        require_rendered(
            "# Handling bot challenges\n\n"
            + "A guide. " * 100
            + "\n\n## Client Challenge"
        )


class RenderTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        patcher = patch.object(config, "OUTPUT", Path(temp.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_short_text_stays_inline_without_a_file(self):
        rendered = render("short", "label", limit=100)
        self.assertEqual(
            (str(rendered), rendered.used, rendered.path), ("short", 5, None)
        )
        self.assertEqual(list(config.OUTPUT.iterdir()), [])

    def test_long_text_is_saved_whole_with_a_bounded_preview_first(self):
        rendered = render("a" * 100, "label", limit=20)
        self.assertEqual(rendered.used, 20)
        self.assertTrue(str(rendered).startswith("[saved:"))
        self.assertTrue(str(rendered).endswith("a" * 20))
        assert rendered.path
        self.assertEqual(rendered.path.read_text(), "a" * 100 + "\n")

    def test_unlimited_and_exhausted_budgets_differ(self):
        self.assertEqual(render("a" * 5000, "l", limit=None).used, 5000)
        exhausted = render("a" * 50, "l", limit=0)
        self.assertEqual((exhausted.shown, exhausted.used), ("", 0))
        self.assertIn("preview 0/50", exhausted.notice)

    def test_selection_saves_even_when_nothing_matches(self):
        rendered = render(
            "full response", "l", limit=100, selection=Selection(match=re.compile("x"))
        )
        self.assertIn("13 chars, 1 lines | --match: 0 matching lines", rendered.notice)
        assert rendered.path
        self.assertEqual(rendered.path.read_text(), "full response\n")

    def test_same_text_from_two_sources_is_saved_twice(self):
        first = save_text("same", "fetch-https://github.com/o/r/blob/v1/a.rs")
        second = save_text("same", "fetch-https://github.com/o/r/blob/v2/a.rs")
        self.assertNotEqual(first, second)


class WorkDirectoryTests(unittest.TestCase):
    def test_a_requested_tmpdir_is_used_even_before_it_exists(self):
        with tempfile.TemporaryDirectory() as root:
            missing = Path(root, "not-yet")
            with patch.dict("os.environ", {"TMPDIR": str(missing)}):
                self.assertEqual(work_directory().parent, missing)


class DateTests(unittest.TestCase):
    def test_dates_normalise_to_iso_keeping_stated_time_and_offset(self):
        cases = {
            "2026-05-06T01:02:03Z": "2026-05-06T01:02:03Z",
            "2026-05-06T01:02:03.456+05:30": "2026-05-06T01:02:03+05:30",
            "2026-05-06 01:02": "2026-05-06T01:02",
            "2026-05-06T00:00:00.000Z": "2026-05-06",
            "Mon, 05 Oct 2026 10:00:00 GMT": "2026-10-05T10:00:00Z",
            "Mon, 05 Oct 2026 00:00:00 GMT": "2026-10-05",
            "3 days ago": "",
            None: "",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(iso_timestamp(value), expected)


if __name__ == "__main__":
    unittest.main()
