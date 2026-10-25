"""`fetch`: read URLs as markdown, each page previewed or excerpted."""

import json
from contextlib import closing
from dataclasses import dataclass
from typing import Any

from ..errors import ResearchError
from ..fetching import Fetched, FetchOptions, Mode, exa_extract, fetch_many
from ..output import Output, Rendered, emit, render
from ..pages import has_markdown_headings
from ..transport import Http


@dataclass(frozen=True)
class FetchCommandOptions:
    urls: list[str]
    fetch: FetchOptions
    json: bool
    output: Output


def json_record(page: Fetched, rendered: Rendered) -> dict[str, Any]:
    return {
        "url": page.url,
        "source": page.source,
        "chars": rendered.chars,
        "lines": rendered.lines,
        "saved": str(rendered.path),
        "notices": page.notices,
        "text": rendered.shown,
    }


def print_page(options: FetchCommandOptions, page: Fetched, share: int | None) -> int:
    """Print one URL's outcome; return the inline characters it used."""
    if page.error is not None:
        if options.json:
            failure = {"error": str(page.error), "hint": page.error.hint}
            print(json.dumps({"url": page.url, **failure, "notices": page.notices}))
        else:
            print("\n".join(page.notices))
            print(f"URL: {page.url} [error: {page.error} | hint: {page.error.hint}]")
        return 0
    rendered = render(
        page.text,
        f"fetch-{page.url}",
        limit=share,
        selection=options.output.selection,
        raw=options.fetch.mode is Mode.RAW,
        outline=True,
        save=options.json,
        markdown=has_markdown_headings(page.url),
    )
    if options.json:
        print(json.dumps(json_record(page, rendered), ensure_ascii=False))
    else:
        print(
            "\n".join(
                [*page.notices, f"URL: {page.url} [{page.source}]", str(rendered)]
            ).rstrip()
        )
    return rendered.used


def run_exa_batch(options: FetchCommandOptions) -> None:
    """`fetch --exa`: every URL in one Exa request, reported as one response."""
    urls = list(dict.fromkeys(options.urls))
    page = Fetched(urls[0], source="Exa")
    with Http() as http:
        page.text = exa_extract(http, urls, options.fetch, page.notices)
    label = f"fetch-{urls[0]}"
    if not options.json:
        print("\n".join(page.notices))
        emit(page.text, label, options.output, outline=True)
        return
    rendered = render(
        page.text,
        label,
        limit=options.output.limit,
        selection=options.output.selection,
        save=True,
    )
    print(json.dumps({**json_record(page, rendered), "urls": urls}, ensure_ascii=False))


def run(options: FetchCommandOptions) -> None:
    if options.fetch.mode is Mode.EXA:
        run_exa_batch(options)
        return
    budget = options.output.limit
    pending = len(options.urls)
    failures = 0
    with (
        Http() as http,
        closing(fetch_many(http, options.urls, options.fetch)) as pages,
    ):
        for page in pages:
            # Each page gets an equal share of what is left, so none is starved.
            share = None if budget is None else budget // pending
            pending -= 1
            failures += page.error is not None
            used = print_page(options, page, share)
            if budget is not None:
                budget -= used
    if failures == len(options.urls):
        raise ResearchError("no URL could be fetched", "see the errors above")
