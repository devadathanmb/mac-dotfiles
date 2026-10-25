"""Web search providers, each answering one query with a list of SearchResults."""

import html
import json
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from .cache import cached
from .credentials import KEYS, api_key
from .errors import ResearchError
from .mcp import call_tool
from .models import SearchResult
from .transport import Http, json_body

DEFAULT_RESULT_CHARS = 1500
# Brave's free plan allows one request per second.
BRAVE_INTERVAL_SECONDS = 1.1
BRAVE_ATTEMPTS = 3
SITE_OPERATOR = re.compile(r"(?<!\S)site:(\S+)")
EXA_LISTING = re.compile(r"(?m)^(?=Title: .*\nURL: )")
EXA_FIELDS = re.compile(
    r"Title: (.*)\nURL: (\S+)\n(?:Published: (.*)\n)?(?:Author: .*\n)?"
    r"(?:Highlights:\n)?"
)


@dataclass(frozen=True)
class SearchRequest:
    """One query and the filters every provider maps onto its own API."""

    query: str
    count: int
    domains: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    after: str | None = None  # YYYY-MM-DD
    before: str | None = None
    category: str | None = None  # Exa only
    chars: int | None = None  # page text per result instead of highlights
    objective: str | None = None
    fresh: bool = False

    @property
    def filtered(self) -> bool:
        return any((self.domains, self.exclude, self.after, self.before, self.category))


Provider = Callable[[Http, SearchRequest, list[str]], list[SearchResult]]


class Throttle:
    """Spaces calls from concurrent threads at least `interval` seconds apart."""

    def __init__(self, interval: float) -> None:
        self.interval = interval
        self.lock = threading.Lock()
        self.last = 0.0

    def wait(self) -> None:
        with self.lock:
            delay = self.last + self.interval - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self.last = time.monotonic()


brave_throttle = Throttle(BRAVE_INTERVAL_SECONDS)


def split_sites(query: str, *, keep_paths: bool) -> tuple[str, list[str]]:
    """Move `site:` operators, which only keyword engines honour, into domains.

    Without `keep_paths`, `site:github.com/owner/repo` filters on the host and
    returns the path to the query as plain words.
    """
    sites = SITE_OPERATOR.findall(query)
    words = [SITE_OPERATOR.sub("", query).strip()]
    domains = []
    for site in sites:
        host, _, path = site.strip("/").partition("/")
        domains.append(site.strip("/") if keep_paths else host)
        if path and not keep_paths:
            words.append(path.replace("/", " "))
    return " ".join(filter(None, words)) or " ".join(sites), domains


def provider_error_hints(name: str) -> dict[int, str]:
    key_hint = f"check {KEYS[name].locations}"
    return {
        401: key_hint,
        403: key_hint,
        402: "credits exhausted; use another --backend",
        429: "rate limited; use another --backend",
        432: "plan limit reached; use another --backend",
    }


def call_provider(
    http: Http, name: str, method: str, url: str, **options: Any
) -> dict[str, Any]:
    response = http.call_api(
        name,
        method,
        url,
        label=name,
        hint="use another --backend",
        status_hints=provider_error_hints(name),
        **options,
    )
    data = json_body(response, name)
    if not isinstance(data, dict):
        raise ResearchError(f"{name}: invalid response")
    return data


def rest_result(
    title: object, url: object, published: object, text: object
) -> SearchResult:
    """A result from a REST provider, whose text may carry HTML entities."""
    return SearchResult.create(
        html.unescape(str(title or "")),
        url,
        published,
        html.unescape(str(text or "")),
    )


def cached_results(
    name: str, key: object, compute: Callable[[], list[SearchResult]], fresh: bool
) -> list[SearchResult]:
    def serialised() -> str:
        return json.dumps([result.to_json() for result in compute()])

    text = cached(name, key, serialised, fresh=fresh)
    try:
        return [SearchResult.from_json(item) for item in json.loads(text)]
    except (ValueError, KeyError, TypeError) as error:
        raise ResearchError(f"{name}: invalid cached response") from error


def items(data: dict[str, Any], *path: str) -> list[dict[str, Any]]:
    """The list of objects at `path` in a provider response, skipping junk."""
    value: Any = data
    for name in path:
        value = value.get(name) if isinstance(value, dict) else None
    return [item for item in value or [] if isinstance(item, dict)]


def parse_exa_listing(text: str) -> list[SearchResult]:
    """Results from Exa's basic search, which answers in `Title:/URL:` text blocks."""
    results = []
    for block in EXA_LISTING.split(text):
        fields = EXA_FIELDS.match(block)
        if not fields:
            continue
        title, url, published = fields.groups()
        results.append(
            SearchResult.create(
                "" if title == "N/A" else title,
                url,
                published,
                block[fields.end() :],
            )
        )
    return results


def parse_exa_json(text: str, *, highlights: bool) -> list[SearchResult] | None:
    """Results from Exa's advanced search; None when the response is not its JSON."""
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    results = []
    for item in items(data, "results"):
        if not item.get("url"):
            continue
        passages = item.get("highlights") if highlights else None
        body = "\n...\n".join(passages) if passages else item.get("text")
        results.append(
            SearchResult.create(
                item.get("title"), item["url"], item.get("publishedDate"), body
            )
        )
    return results


def search_exa(
    http: Http, request: SearchRequest, notices: list[str]
) -> list[SearchResult]:
    query, sites = split_sites(request.query, keep_paths=False)
    domains = [*request.domains, *sites]
    arguments: dict[str, Any] = {"query": query, "numResults": request.count}
    if not (request.filtered or sites) and request.chars is None:
        tool = "web_search_exa"
        arguments["objective"] = request.objective or query
    else:
        tool = "web_search_advanced_exa"
        # Highlights are query-relevant; an explicit --chars asks for page text.
        highlights = request.chars is None
        if not highlights:
            notices.append(
                f"[Exa extraction: ≤{request.chars:,} chars/result requested; "
                "may be incomplete]"
            )
        arguments.update(
            textMaxCharacters=request.chars or DEFAULT_RESULT_CHARS,
            enableHighlights=highlights,
            type="auto",
        )
        for value, name in (
            (domains, "includeDomains"),
            (list(request.exclude), "excludeDomains"),
            (request.after, "startPublishedDate"),
            (request.before, "endPublishedDate"),
            (request.category, "category"),
        ):
            if value:
                arguments[name] = value
    response = cached(
        "exa",
        [tool, arguments],
        lambda: call_tool(http, "exa", tool, arguments),
        fresh=request.fresh,
    )
    if tool == "web_search_exa":
        results: list[SearchResult] | None = parse_exa_listing(response)
    else:
        results = parse_exa_json(response, highlights=request.chars is None)
    if results is None or (not results and "URL: " in response):
        # An unrecognised response that cites pages is still evidence; keep it whole.
        results = [SearchResult("", "", "", response.strip())]
    return results


def search_parallel(
    http: Http, request: SearchRequest, notices: list[str]
) -> list[SearchResult]:
    if request.before:
        raise ResearchError("parallel: --before is not supported")
    query, sites = split_sites(request.query, keep_paths=True)
    policy = {
        name: value
        for name, value in (
            ("include_domains", [*request.domains, *sites]),
            ("exclude_domains", list(request.exclude)),
            ("after_date", request.after),
        )
        if value
    }
    settings: dict[str, Any] = {
        "max_results": request.count,
        "excerpt_settings": {
            "max_chars_per_result": request.chars or DEFAULT_RESULT_CHARS
        },
    }
    if policy:
        settings["source_policy"] = policy
    payload = {
        "objective": request.objective or query,
        "search_queries": [query],
        "mode": "fast",
        "advanced_settings": settings,
    }

    def search() -> list[SearchResult]:
        data = call_provider(
            http,
            "parallel",
            "POST",
            "https://api.parallel.ai/v1/search",
            headers={"x-api-key": api_key("parallel") or ""},
            json=payload,
        )
        return [
            rest_result(
                item.get("title"),
                item.get("url"),
                item.get("publish_date"),
                "\n...\n".join(item.get("excerpts") or []),
            )
            for item in items(data, "results")
        ]

    return cached_results("parallel", payload, search, request.fresh)


def search_brave(
    http: Http, request: SearchRequest, notices: list[str]
) -> list[SearchResult]:
    query = request.query  # Brave honours site: operators itself
    if domains := request.domains:
        sites = " OR ".join(f"site:{domain}" for domain in domains)
        query = f"({sites}) {query}" if len(domains) > 1 else f"{sites} {query}"
    for domain in request.exclude:
        query += f" -site:{domain}"
    parameters = {
        "q": query,
        "count": str(min(request.count, 20)),
        "text_decorations": "false",
        "result_filter": "web",
        "extra_snippets": "true",
    }
    if request.after or request.before:
        start = request.after or "1990-01-01"
        end = request.before or date.today().isoformat()
        parameters["freshness"] = f"{start}to{end}"

    def send() -> dict[str, Any]:
        for attempt in range(1, BRAVE_ATTEMPTS + 1):
            # Concurrent queries would otherwise trip the per-second limit.
            brave_throttle.wait()
            try:
                return call_provider(
                    http,
                    "brave",
                    "GET",
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={
                        "X-Subscription-Token": api_key("brave") or "",
                        "Accept": "application/json",
                    },
                    params=parameters,
                )
            except ResearchError as error:
                # Another process may share the key's one-request-per-second allowance.
                if error.status != 429 or attempt == BRAVE_ATTEMPTS:
                    raise
        raise AssertionError("the last attempt returns or raises")

    def search() -> list[SearchResult]:
        data = send()
        return [
            rest_result(
                item.get("title"),
                item.get("url"),
                item.get("page_age"),
                "\n...\n".join(
                    [item.get("description") or "", *(item.get("extra_snippets") or [])]
                ),
            )
            for item in items(data, "web", "results")
        ]

    return cached_results("brave", parameters, search, request.fresh)


def search_tavily(
    http: Http, request: SearchRequest, notices: list[str]
) -> list[SearchResult]:
    query, sites = split_sites(request.query, keep_paths=False)
    payload: dict[str, Any] = {
        "query": query,
        "max_results": min(request.count, 20),
        "include_published_date": True,
    }
    for name, value in (
        ("include_domains", [*request.domains, *sites]),
        ("exclude_domains", list(request.exclude)),
        ("start_date", request.after),
        ("end_date", request.before),
    ):
        if value:
            payload[name] = value

    def search() -> list[SearchResult]:
        data = call_provider(
            http,
            "tavily",
            "POST",
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {api_key('tavily') or ''}"},
            json=payload,
        )
        return [
            rest_result(
                item.get("title"),
                item.get("url"),
                item.get("published_date"),
                item.get("content"),
            )
            for item in items(data, "results")
        ]

    return cached_results("tavily", payload, search, request.fresh)


# Fallback order for `--backend auto`.
PROVIDERS: dict[str, Provider] = {
    "exa": search_exa,
    "parallel": search_parallel,
    "brave": search_brave,
    "tavily": search_tavily,
}


def configured() -> list[str]:
    """Providers usable now; Exa works without a key, at a lower rate limit."""
    return [name for name in PROVIDERS if name == "exa" or api_key(name)]
