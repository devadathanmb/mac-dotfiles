"""Web search across providers: fallback chain, rank fusion, and result layout."""

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

from .cache import cached_call
from .config import MAX_FETCH_WORKERS, ResearchError
from .dates import iso_timestamp
from .network import ClientFactory
from .output import MARKDOWN_LINK, preview_length, terms
from .providers import KEYS, provider_key

# Fallback order for `--backend auto`; Exa also works without a key.
PROVIDERS = ("exa", "parallel", "brave", "tavily")
DEFAULT_RESULT_CHARS = 1500
# Reciprocal rank fusion constant from Cormack et al.; damps single-list outliers.
FUSION_K = 60
# A page read by --read earns this multiple of a snippet's share of the preview.
PAGE_WEIGHT = 3
# Room reserved per result for the `… [+N chars, saved line L]` note.
CUT_NOTE_CHARS = 40
# Below this a trimmed passage says too little to be worth its lines.
MIN_PASSAGE_CHARS = 80
# Two results repeat each other when this share of one's word runs is in the other.
REPEAT_SHARE = 0.8
REPEAT_RUN_WORDS = 4
# Shorter texts share boilerplate runs by chance.
MIN_REPEAT_RUNS = 20
# Line numbers in a passage label differ between copies of the same text.
PASSAGE_LINES = re.compile(r"(?m)^\[lines \d+-\d+")
SITE_OPERATOR = re.compile(r"(?<!\S)site:(\S+)")


def configured() -> list[str]:
    return [name for name in PROVIDERS if name == "exa" or provider_key(name)]


def select_providers(args: argparse.Namespace) -> list[str]:
    available = configured()
    if args.backend in ("auto", "all"):
        names = available
    else:
        names = list(dict.fromkeys(args.backend.split(",")))
        for name in names:
            if name not in PROVIDERS:
                raise ResearchError(
                    f"unknown backend '{name}'",
                    f"use auto, all, or a comma list of: {', '.join(PROVIDERS)}",
                )
            if name not in available:
                variable, filename = KEYS[name]
                raise ResearchError(
                    f"{name} key not configured",
                    f"set ${variable} or ~/.secrets/{filename}; "
                    f"configured: {', '.join(available)}",
                )
    if args.category:
        if args.backend not in ("auto", "exa"):
            raise ResearchError(
                "--category is Exa-only", "drop it or use --backend exa"
            )
        names = ["exa"]
    return names


def parse_exa_listing(text: str) -> list[dict]:
    """Results from Exa's basic search, which answers in `Title:/URL:` text blocks."""
    results = []
    for block in re.split(r"(?m)^(?=Title: .*\nURL: )", text):
        fields = re.match(
            r"Title: (.*)\nURL: (\S+)\n(?:Published: (.*)\n)?(?:Author: .*\n)?"
            r"(?:Highlights:\n)?",
            block,
        )
        if not fields:
            continue
        title, url, published = fields.groups()
        results.append(
            {
                "title": "" if title == "N/A" else title.strip(),
                "url": url,
                "date": iso_timestamp(published),
                "text": block[fields.end() :].strip(),
            }
        )
    return results


def parse_exa_json(text: str, *, highlights: bool) -> list[dict] | None:
    """Results from Exa's advanced search; None when the response is not its JSON."""
    try:
        items = json.loads(text).get("results") or []
    except (ValueError, AttributeError):
        return None
    results = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or not item.get("url"):
            continue
        passages = item.get("highlights") if highlights else None
        results.append(
            {
                "title": (item.get("title") or "").strip(),
                "url": item["url"],
                "date": iso_timestamp(item.get("publishedDate")),
                "text": (
                    "\n...\n".join(passages) if passages else item.get("text") or ""
                ).strip(),
            }
        )
    return results


def split_sites(query: str, *, paths: bool) -> tuple[str, list[str]]:
    """Move `site:` operators, which only keyword engines honour, into a domain list.

    Without `paths`, a path such as `github.com/owner/repo` keeps its host as the
    domain and returns to the query as plain words.
    """
    sites = SITE_OPERATOR.findall(query)
    words = [SITE_OPERATOR.sub("", query).strip()]
    domains = []
    for site in sites:
        host, _, path = site.strip("/").partition("/")
        domains.append(site.strip("/") if paths else host)
        if path and not paths:
            words.append(path.replace("/", " "))
    return " ".join(filter(None, words)) or " ".join(sites), domains


def search_exa(
    args: argparse.Namespace,
    query: str,
    count: int,
    client: ClientFactory,
    notices: list[str],
) -> list[dict]:
    query, sites = split_sites(query, paths=False)
    domains = [*(args.domain or []), *sites]
    arguments: dict = {"query": query, "numResults": count}
    filtered = any((domains, args.exclude, args.after, args.before, args.category))
    if not filtered and args.chars is None:
        arguments["objective"] = args.objective or query
        response = cached_call(
            "exa", "web_search_exa", arguments, args.fresh, client=client
        )
        results = parse_exa_listing(response)
    else:
        # Highlights are query-relevant; an explicit --chars asks for page text instead.
        highlights = args.chars is None
        if not highlights:
            notices.append(
                f"[Exa extraction: ≤{args.chars:,} chars/result requested; "
                "may be incomplete]"
            )
        arguments.update(
            textMaxCharacters=args.chars or DEFAULT_RESULT_CHARS,
            enableHighlights=highlights,
            type="auto",
        )
        for value, name in (
            (domains, "includeDomains"),
            (args.exclude, "excludeDomains"),
            (args.after, "startPublishedDate"),
            (args.before, "endPublishedDate"),
            (args.category, "category"),
        ):
            if value:
                arguments[name] = value
        response = cached_call(
            "exa", "web_search_advanced_exa", arguments, args.fresh, client=client
        )
        results = parse_exa_json(response, highlights=highlights)
    if results is None or (not results and "URL: " in response):
        # An unrecognised response that cites pages is still evidence; keep it whole.
        results = [{"title": "", "url": "", "date": "", "text": response.strip()}]
    return results


def search_provider(
    name: str,
    args: argparse.Namespace,
    query: str,
    count: int,
    client: ClientFactory,
    notices: list[str],
) -> list[dict]:
    if name == "exa":
        return search_exa(args, query, count, client, notices)
    if name == "parallel" and args.before:
        raise ResearchError("parallel: --before is not supported")
    sites: list[str] = []
    if name != "brave":  # Brave reads the operator itself.
        query, sites = split_sites(query, paths=name == "parallel")
    arguments = {
        "queries": [query],
        "n": count,
        "chars": args.chars or DEFAULT_RESULT_CHARS,
    }
    for value, key in (
        ([*(args.domain or []), *sites], "domains"),
        (args.exclude, "exclude"),
        (args.after, "after"),
        (args.before, "before"),
        (args.objective, "objective"),
    ):
        if value:
            arguments[key] = value
    response = cached_call(name, "search", arguments, args.fresh, client=client)
    try:
        return json.loads(response)
    except ValueError as error:
        raise ResearchError(f"{name}: invalid cached response") from error


def search_chain(
    names: list[str],
    args: argparse.Namespace,
    query: str,
    count: int,
    client: ClientFactory,
    label: str,
) -> tuple[str, list[dict], list[str]]:
    """Results from the first provider in `names` that returns any."""
    notices: list[str] = []
    for name in names:
        try:
            if results := search_provider(name, args, query, count, client, notices):
                return name, results, notices
            notices.append(f"[{name}{label}: no results]")
        except ResearchError as error:
            notices.append(f"[{name}{label} failed: {error}]")
    return "", [], notices


def canonical_url(url: str) -> str:
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
    garbled = sum(
        char == "\ufffd" or (char < " " and char not in "\n\t\r") for char in text
    )
    return garbled * 20 <= len(text)


def fuse(rankings: list[tuple[str, list[dict]]], count: int) -> list[dict]:
    """Merge rankings by reciprocal rank fusion, one entry per page."""
    merged: dict[str, dict] = {}
    for name, results in rankings:
        for rank, result in enumerate(results):
            key = canonical_url(result["url"]) or f"{name}:{rank}:{result['text'][:40]}"
            entry = merged.setdefault(key, {**result, "providers": [], "score": 0.0})
            entry["score"] += 1 / (FUSION_K + rank)
            if name not in entry["providers"]:
                entry["providers"].append(name)
            for field in ("title", "date", "text"):
                entry[field] = entry[field] or result[field]
            if not readable(entry["text"]):
                entry["text"] = ""
    ranked = sorted(merged.values(), key=lambda entry: -entry["score"])[:count]
    for entry in ranked:
        del entry["score"]
    return ranked


def interleave(rankings: list[list[dict]], count: int) -> list[dict]:
    """Take results from each query in turn so every query is represented."""
    merged: dict[str, dict] = {}
    for rank in range(max(map(len, rankings), default=0)):
        for results in rankings:
            if rank >= len(results):
                continue
            result = results[rank]
            key = canonical_url(result["url"]) or f"{id(results)}:{rank}"
            if key in merged:
                known = merged[key]["providers"]
                known.extend(p for p in result["providers"] if p not in known)
            else:
                merged[key] = result
    return list(merged.values())[:count]


def search(
    args: argparse.Namespace, client: ClientFactory
) -> tuple[list[dict], list[str], list[str]]:
    """(results, providers that answered, notices) for every query in `args`."""
    names = select_providers(args)
    queries = list(dict.fromkeys(args.queries))
    count = args.n or (5 if len(queries) == 1 else min(3 * len(queries), 20))
    # auto: one fallback chain per query; otherwise every provider answers each.
    chains = [names] if args.backend == "auto" else [[name] for name in names]
    with ThreadPoolExecutor(max_workers=MAX_FETCH_WORKERS) as executor:
        pending = [
            [
                executor.submit(
                    search_chain,
                    chain,
                    args,
                    query,
                    count,
                    client,
                    f" (query {number})" if len(queries) > 1 else "",
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
        fuse([(name, results) for name, results, _ in answers if results], count)
        for answers in outcomes
    ]
    if not any(per_query):
        raise ResearchError(
            "no results: " + " ".join(notices),
            "rephrase the query, loosen filters (use --domain, not site:), "
            "or pick another --backend",
        )
    answered = {name for answers in outcomes for name, results, _ in answers if results}
    used = [name for name in PROVIDERS if name in answered]
    return interleave(per_query, count), used, notices


def result_header(rank: int, result: dict, show_providers: bool) -> str:
    title = result["title"] or result["url"] or "(untitled)"
    line = f"{rank}. {title}"
    if result["date"]:
        line += f" ({result['date']})"
    if show_providers:
        line += f" [{', '.join(result['providers'])}]"
    lines = [line]
    if result["title"] and result["url"]:
        lines.append(result["url"])
    if result.get("page"):
        lines.append(
            f"page saved: {Path(result['page']).name} ({result['page_chars']:,} chars, "
            f"{result['source']}); line numbers refer to it"
        )
    return "\n".join(lines)


def allowances(lengths: list[int], weights: list[int], budget: int) -> list[int]:
    """Split `budget` by weight; texts shorter than their share pass the rest on."""
    allowed = [0] * len(lengths)
    order = sorted(range(len(lengths)), key=lambda i: lengths[i] / weights[i])
    weight = sum(weights)
    for index in order:
        share = max(budget, 0) * weights[index] // weight
        allowed[index] = min(lengths[index], share)
        budget -= allowed[index]
        weight -= weights[index]
    return allowed


def trim_passage(text: str, allowed: int, first_line: int) -> str:
    """`text` cut to `allowed` chars, noting where it resumes in the saved file."""
    if allowed >= len(text):
        return text
    shown = ""
    if allowed >= MIN_PASSAGE_CHARS:
        shown = text[: preview_length(text, allowed)].rstrip()
    resume = first_line + (shown.count("\n") + 1 if shown else 0)
    note = f"… [+{len(text) - len(shown):,} chars, saved line {resume}]"
    return f"{shown}\n{note}" if shown else note


def repeated_results(texts: list[str]) -> dict[int, int]:
    """Results whose text an earlier result already shows: {index: earlier index}.

    A docs page and its source file, or a mirror, would otherwise be shown twice.
    """
    seen: list[tuple[int, set[tuple[str, ...]]]] = []
    repeats = {}
    for index, text in enumerate(texts):
        words = terms(MARKDOWN_LINK.sub(r"\1", PASSAGE_LINES.sub("", text)))
        runs = {
            tuple(words[start : start + REPEAT_RUN_WORDS])
            for start in range(len(words) - REPEAT_RUN_WORDS + 1)
        }
        if len(runs) < MIN_REPEAT_RUNS:
            continue
        for earlier, known in seen:
            if len(runs & known) >= REPEAT_SHARE * len(runs):
                repeats[index] = earlier
                break
        else:
            seen.append((index, runs))
    return repeats


def join_results(headers: list[str], texts: list[str]) -> str:
    return "\n\n".join(
        f"{header}\n{text}".rstrip() for header, text in zip(headers, texts)
    )


def layout_results(
    results: list[dict], limit: int, show_providers: bool
) -> tuple[str, str, list[str]]:
    """(complete text, text fitted to `limit`, fitted passage per result)."""
    headers = [
        result_header(rank, result, show_providers)
        for rank, result in enumerate(results, 1)
    ]
    texts = [result["text"] for result in results]
    full = join_results(headers, texts)
    repeats = repeated_results(texts)
    fits = not limit or len(full) <= limit
    if fits and not repeats:
        return full, full, texts
    lengths = [0 if index in repeats else len(text) for index, text in enumerate(texts)]
    if fits:
        shares = lengths
    else:
        budget = limit - sum(len(header) + 2 + CUT_NOTE_CHARS for header in headers)
        weights = [PAGE_WEIGHT if result.get("page") else 1 for result in results]
        shares = allowances(lengths, weights, budget)
    fitted = []
    line = 1  # line of `full` where the next result starts
    for index, (header, text, allowed) in enumerate(zip(headers, texts, shares)):
        first_line = line + header.count("\n") + 1
        if index in repeats:
            fitted.append(
                f"[same text as result {repeats[index] + 1}; saved line {first_line}]"
            )
        else:
            fitted.append(trim_passage(text, allowed, first_line))
        # A result ends with a blank line; one without text has no passage lines.
        line = first_line + (text.count("\n") + 2 if text else 1)
    return full, join_results(headers, fitted), fitted
