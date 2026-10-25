"""Web search across providers: a fallback chain or a rank fusion for each query."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from urllib.parse import parse_qsl, urlencode, urlsplit

from . import config
from .credentials import KEYS
from .errors import ResearchError
from .models import SearchResult
from .providers import PROVIDERS, SearchRequest, configured
from .transport import Http

# Reciprocal rank fusion constant from Cormack et al.; damps single-list outliers.
FUSION_K = 60
# Mis-decoded text: more than one character in this many is garbage.
GARBLED_RATIO = 20
# Room for every query when several share the result count.
RESULTS_PER_QUERY = 3
MAX_RESULTS = 20
DEFAULT_RESULTS = 5


@dataclass
class SearchOutcome:
    results: list[SearchResult]
    providers: list[str]  # those that returned results, in fallback order
    notices: list[str]


def select_providers(backend: str, category: str | None = None) -> list[str]:
    available = configured()
    if backend in ("auto", "all"):
        names = available
    else:
        names = list(dict.fromkeys(backend.split(",")))
        for name in names:
            if name not in PROVIDERS:
                raise ResearchError(
                    f"unknown backend '{name}'",
                    f"use auto, all, or a comma list of: {', '.join(PROVIDERS)}",
                )
            if name not in available:
                raise ResearchError(
                    f"{name} key not configured",
                    f"set {KEYS[name].locations}; configured: {', '.join(available)}",
                )
    if category:
        if backend not in ("auto", "exa"):
            raise ResearchError(
                "--category is Exa-only", "drop it or use --backend exa"
            )
        names = ["exa"]
    return names


def result_count(queries: int, requested: int | None) -> int:
    if requested is not None:
        return requested
    if queries == 1:
        return DEFAULT_RESULTS
    return min(RESULTS_PER_QUERY * queries, MAX_RESULTS)


def search_chain(
    http: Http, names: list[str], request: SearchRequest, label: str
) -> tuple[str, list[SearchResult], list[str]]:
    """(provider, results, notices) from the chain's first provider with results."""
    notices: list[str] = []
    for name in names:
        try:
            if results := PROVIDERS[name](http, request, notices):
                return name, results, notices
            notices.append(f"[{name}{label}: no results]")
        except ResearchError as error:
            reason = f"{error}; {error.hint}" if error.hint else str(error)
            notices.append(f"[{name}{label} failed: {reason}]")
    return "", [], notices


def canonical_url(url: str) -> str:
    """The URL without scheme, `www.`, trailing slash, or tracking parameters."""
    parts = urlsplit(url)
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if not key.lower().startswith("utm_")
        ]
    )
    host = (parts.hostname or "").removeprefix("www.")
    return f"{host}{parts.path.rstrip('/')}" + (f"?{query}" if query else "")


def readable(text: str) -> bool:
    """False for mis-decoded page text, which some indexes return verbatim."""
    garbled = sum(char == "�" or (char < " " and char not in "\n\t\r") for char in text)
    return garbled * GARBLED_RATIO <= len(text)


def fuse(
    rankings: list[tuple[str, list[SearchResult]]], count: int
) -> list[SearchResult]:
    """Merge providers' rankings of one query by reciprocal rank fusion."""
    merged: dict[str, SearchResult] = {}
    scores: dict[str, float] = {}
    for name, results in rankings:
        for rank, result in enumerate(results):
            key = canonical_url(result.url) or f"{name}:{rank}:{result.text[:40]}"
            if key not in merged:
                merged[key] = replace(result, providers=[])
                scores[key] = 0.0
            entry = merged[key]
            scores[key] += 1 / (FUSION_K + rank)
            if name not in entry.providers:
                entry.providers.append(name)
            entry.title = entry.title or result.title
            entry.date = entry.date or result.date
            entry.text = entry.text or result.text
            if not readable(entry.text):
                entry.text = ""
    ranked = sorted(merged, key=lambda key: -scores[key])[:count]
    return [merged[key] for key in ranked]


def interleave(rankings: list[list[SearchResult]], count: int) -> list[SearchResult]:
    """Take results from each query in turn so every query is represented."""
    merged: dict[str, SearchResult] = {}
    for rank in range(max(map(len, rankings), default=0)):
        for number, results in enumerate(rankings):
            if rank >= len(results):
                continue
            result = results[rank]
            key = canonical_url(result.url) or f"{number}:{rank}"
            if key not in merged:
                merged[key] = result
                continue
            known = merged[key]
            known.providers.extend(
                p for p in result.providers if p not in known.providers
            )
            known.query_ids = sorted({*known.query_ids, *result.query_ids})
    return list(merged.values())[:count]


def search(
    http: Http, queries: list[str], backend: str, template: SearchRequest
) -> SearchOutcome:
    """Results for every query; `template` carries the count and filters.

    With `auto` each query runs one fallback chain; otherwise every selected
    provider answers each query and their rankings are fused.
    """
    names = select_providers(backend, template.category)
    queries = list(dict.fromkeys(queries))
    multiple = len(queries) > 1
    chains = [names] if backend == "auto" else [[name] for name in names]
    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
        pending = [
            [
                executor.submit(
                    search_chain,
                    http,
                    chain,
                    replace(template, query=query),
                    f" (query {number})" if multiple else "",
                )
                for chain in chains
            ]
            for number, query in enumerate(queries, 1)
        ]
        outcomes = [[future.result() for future in futures] for futures in pending]
    notices = list(
        dict.fromkeys(
            note for answers in outcomes for *_, notes in answers for note in notes
        )
    )
    # Providers rank the same query, so fuse them; queries differ, so alternate.
    per_query = [
        fuse(
            [(name, results) for name, results, _ in answers if results], template.count
        )
        for answers in outcomes
    ]
    for number, results in enumerate(per_query, 1):
        for result in results:
            result.query_ids = [number]
    if not any(per_query):
        if all(" failed: " in notice for notice in notices):
            # Rephrasing cannot fix a rejected key or an outage; each notice says why.
            raise ResearchError(
                "every provider failed: " + " ".join(notices),
                "follow the providers' hints or pick another --backend",
            )
        raise ResearchError(
            "no results: " + " ".join(notices),
            "rephrase the query, loosen filters (use --domain, not site:), "
            "or pick another --backend",
        )
    answered = {name for answers in outcomes for name, results, _ in answers if results}
    providers = [name for name in PROVIDERS if name in answered]
    return SearchOutcome(interleave(per_query, template.count), providers, notices)
