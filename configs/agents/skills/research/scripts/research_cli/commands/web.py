"""`web`: multi-provider web search, optionally reading the top pages."""

import json
from dataclasses import dataclass
from typing import Any

from .. import config
from ..excerpts import NO_PASSAGES, ranked_passages
from ..fetching import FetchOptions, fetch_many
from ..layout import Layout, layout_results
from ..models import SearchResult
from ..output import Output, emit, save_text, saved_notice
from ..pages import has_markdown_headings
from ..providers import SearchRequest
from ..search import SearchOutcome, search
from ..transport import Http

# Passage text kept per page read by `--read`.
READ_PASSAGE_CHARS = 3000
JSON_FIELDS = ("title", "url", "date", "providers", "query_ids", "page", "source")


@dataclass(frozen=True)
class WebOptions:
    queries: list[str]
    backend: str
    request: SearchRequest  # the count and filters; each query fills in `query`
    read: int
    json: bool
    output: Output


def read_pages(
    http: Http, results: list[SearchResult], options: WebOptions
) -> list[str]:
    """Fetch the top `--read` results and swap their snippets for page passages."""
    targets = [result for result in results if result.url][: options.read]
    question = " ".join([*options.queries, options.request.objective or ""])
    notices = []
    pages = fetch_many(
        http,
        [result.url for result in targets],
        FetchOptions(fresh=options.request.fresh),
    )
    for result, page in zip(targets, pages, strict=True):
        notices.extend(page.notices)
        if page.error is not None:
            notices.append(f"[read failed: {page.url}: {page.error}]")
            continue
        text = page.text.strip()
        result.page = str(save_text(text, f"fetch-{page.url}"))
        result.page_chars = len(text)
        result.source = page.source
        passages = ranked_passages(
            text, question, READ_PASSAGE_CHARS, markdown=has_markdown_headings(page.url)
        )
        if passages != NO_PASSAGES:
            result.text = passages
    return notices


def json_record(
    options: WebOptions, outcome: SearchOutcome, layout: Layout, saved: str | None
) -> dict[str, Any]:
    results = []
    for rank, (result, text) in enumerate(
        zip(outcome.results, layout.fitted, strict=True), 1
    ):
        fields = {key: getattr(result, key) for key in JSON_FIELDS}
        results.append(
            {
                "rank": rank,
                **{key: value for key, value in fields.items() if value},
                "text": text,
                "chars": len(result.text),
            }
        )
    return {
        "queries": options.queries,
        "providers": outcome.providers,
        "saved": saved,
        "notices": outcome.notices,
        "results": results,
    }


def run(options: WebOptions) -> None:
    with Http() as http:
        outcome = search(http, options.queries, options.backend, options.request)
        if options.read:
            outcome.notices += read_pages(http, outcome.results, options)
    label = f"web-{options.queries[0]}"
    layout = layout_results(
        outcome.results,
        options.output.limit,
        show_providers=len(outcome.providers) > 1,
        queries=options.queries,
    )
    if options.json:
        saved = (
            str(save_text(layout.full, label))
            if layout.compact != layout.full
            else None
        )
        print(
            json.dumps(json_record(options, outcome, layout, saved), ensure_ascii=False)
        )
        return
    for notice in outcome.notices:
        print(notice)
    summary = f"[web: {len(outcome.results)} results via {', '.join(outcome.providers)}"
    if len(options.queries) > 1:
        summary += f" | {len(options.queries)} queries"
    if any(result.page for result in outcome.results):
        summary += f" | pages saved in {config.OUTPUT}/"
    print(summary + "]")
    if options.output.selection.active:
        emit(layout.full, label, options.output)
    elif layout.compact == layout.full:
        print(layout.full)
    else:
        path = save_text(layout.full, label)
        print(
            saved_notice(
                path, layout.full, "preview", len(layout.compact), len(layout.full)
            )
        )
        print(layout.compact)
