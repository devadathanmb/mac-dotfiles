"""Reading URLs: directly first, then through extraction services when blocked.

Order for one URL: a site API (GitHub, Stack Exchange) or the page over HTTP,
then Exa's index, then Firecrawl's browser when Exa has only an unrendered shell.
A failure no source can fix (a 404) stops the chain.
"""

import json
from collections import Counter
from collections.abc import Generator
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from itertools import islice

from . import config, firecrawl
from .cache import cached
from .errors import ResearchError
from .mcp import call_tool
from .pages import Page, fetch_page, fetch_raw, validate_url
from .transport import Http

# Below this an extraction is probably an unrendered shell, not the page.
THIN_PAGE_CHARS = 400


class Mode(StrEnum):
    AUTO = "auto"  # direct, then Exa, then Firecrawl
    RAW = "raw"  # the HTTP body, unconverted
    EXA = "exa"
    FIRECRAWL = "firecrawl"


@dataclass(frozen=True)
class FetchOptions:
    mode: Mode = Mode.AUTO
    fresh: bool = False
    exa_chars: int = config.EXA_PAGE_CHARS


@dataclass
class Fetched:
    url: str
    text: str = ""
    source: str = ""  # which backend produced `text`
    notices: list[str] = field(default_factory=list)
    error: ResearchError | None = None


def exa_extract(
    http: Http, urls: list[str], options: FetchOptions, notices: list[str]
) -> str:
    for url in urls:
        validate_url(url)
    notices.append(
        f"[Exa extraction: ≤{options.exa_chars:,} chars/page requested; "
        "may be incomplete]"
    )
    arguments = {"urls": urls, "maxCharacters": options.exa_chars}
    return cached(
        "exa",
        ["web_fetch_exa", arguments],
        lambda: call_tool(http, "exa", "web_fetch_exa", arguments),
        fresh=options.fresh,
    )


def scrape(http: Http, url: str, options: FetchOptions) -> str:
    return cached(
        "firecrawl",
        url,
        lambda: firecrawl.scrape(http, url, fresh=options.fresh),
        fresh=options.fresh,
    )


def direct(http: Http, url: str, options: FetchOptions, notices: list[str]) -> Page:
    text = cached(
        "page",
        url,
        lambda: json.dumps(asdict(fetch_page(http, url, notices))),
        fresh=options.fresh,
    )
    return Page(**json.loads(text))


def read_with_fallbacks(
    http: Http, url: str, options: FetchOptions, notices: list[str]
) -> tuple[str, str]:
    """(text, source) from the first backend that reads the page."""
    try:
        page = direct(http, url, options, notices)
        return page.text, page.source
    except ResearchError as error:
        if error.final:
            raise
        notices.append(f"[direct fetch failed: {error}; falling back to Exa]")
    has_firecrawl = firecrawl.configured()
    thin = None
    try:
        text = exa_extract(http, [url], options, notices)
        if len(text) >= THIN_PAGE_CHARS or not has_firecrawl:
            return text, "Exa"
        # Exa indexed the same unrendered shell; only a browser will get the page.
        thin = text
        notices.append(f"[Exa returned only {len(text)} chars; trying Firecrawl]")
    except ResearchError as error:
        if not has_firecrawl:
            raise
        notices.append(f"[Exa failed: {error}; falling back to Firecrawl]")
    try:
        return scrape(http, url, options), "Firecrawl"
    except ResearchError:
        if thin is None:
            raise
        return thin, "Exa"


def fetch_one(http: Http, url: str, options: FetchOptions) -> Fetched:
    fetched = Fetched(url)
    try:
        validate_url(url)
        match options.mode:
            case Mode.RAW:
                fetched.text = cached(
                    "raw", url, lambda: fetch_raw(http, url), fresh=options.fresh
                )
                fetched.source = "direct HTTP, unmodified"
            case Mode.FIRECRAWL:
                fetched.text, fetched.source = scrape(http, url, options), "Firecrawl"
            case Mode.EXA:
                fetched.text = exa_extract(http, [url], options, fetched.notices)
                fetched.source = "Exa"
            case Mode.AUTO:
                fetched.text, fetched.source = read_with_fallbacks(
                    http, url, options, fetched.notices
                )
    except ResearchError as error:
        fetched.error = error
    return fetched


def fetch_many(
    http: Http, urls: list[str], options: FetchOptions
) -> Generator[Fetched]:
    """Each URL's outcome in argument order, fetching a few ahead concurrently.

    A repeated URL is fetched once. Only `MAX_WORKERS` fetches are in flight, so
    stopping early (the reader failed) leaves the rest of a long batch unsent.
    """
    upcoming = iter(dict.fromkeys(urls))
    remaining = Counter(urls)
    finished: dict[str, Fetched] = {}
    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as pool:
        pending: dict[str, Future[Fetched]] = {
            url: pool.submit(fetch_one, http, url, options)
            for url in islice(upcoming, config.MAX_WORKERS)
        }
        try:
            for url in urls:
                if url not in finished:
                    finished[url] = pending.pop(url).result()
                    if (following := next(upcoming, None)) is not None:
                        pending[following] = pool.submit(
                            fetch_one, http, following, options
                        )
                remaining[url] -= 1
                yield finished[url] if remaining[url] else finished.pop(url)
        finally:
            for future in pending.values():
                future.cancel()
