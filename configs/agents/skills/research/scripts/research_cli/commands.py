"""One handler per CLI subcommand."""

import argparse
import json
import re
from collections import Counter
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import dataclass, field
from itertools import islice

from . import config
from .cache import cached_call
from .config import EXA_PAGE_CHARS, MAX_FETCH_WORKERS, ResearchError
from .credentials import api_key
from .network import ClientFactory, shared_client
from .output import (
    NO_PASSAGES,
    Rendered,
    emit_response,
    ranked_passages,
    render_response,
    save_text,
    saved_notice,
)
from .pages import validate_url
from .search import layout_results, search

# Below this an extraction is probably an unrendered shell, not the page.
THIN_PAGE_CHARS = 400
# Passage text kept per page read by `web --read`.
READ_PASSAGE_CHARS = 3000


def library_field(block: str, name: str) -> str:
    match = re.search(rf"{name}: *(.*)", block)
    return match.group(1).strip() if match else ""


def library_summary(block: str) -> str:
    fields = (
        ("Source Reputation", "reputation"),
        ("Code Snippets", "snippets"),
        ("Benchmark Score", "score"),
    )
    metadata = "; ".join(
        f"{label}: {value}"
        for name, label in fields
        if (value := library_field(block, name))
    )
    versions = library_field(block, "Versions") or "not listed"
    return "\n".join(
        line
        for line in (
            f"### {library_field(block, 'Title')} — {library_field(block, 'Context7-compatible library ID')}",
            library_field(block, "Description"),
            metadata,
            f"Versions: {versions}",
        )
        if line
    )


def docs(args: argparse.Namespace) -> None:
    library = args.library
    selection = ""
    if not library.startswith("/"):
        result = cached_call(
            "c7",
            "resolve-library-id",
            {"libraryName": library, "query": args.query or library},
            args.fresh,
        )
        blocks = [
            block
            for block in re.split(r"\n(?=- Title:)", result)
            if "Context7-compatible library ID:" in block
        ]
        if not blocks:
            raise ResearchError(
                f"no library matches '{library}'", "try a different name, or `web`"
            )
        if args.list or not args.query:
            listing = (
                f"# Context7 candidates ({len(blocks)})\n"
                'Next: `docs <id> "<question>"`; pin versions with '
                "`<id>/<exact-listed-version>`.\n\n"
            )
            listing += "\n\n".join(library_summary(block) for block in blocks)
            emit_response(listing, args, f"docs-list-{library}")
            return
        library = library_field(blocks[0], "Context7-compatible library ID")
        selection = f"Selection: first match of {len(blocks)}; use --list to compare.\n"
    print(f"# Context7: {library}")
    if len(library.strip("/").split("/")) == 2:
        selection += (
            "Version: unpinned; a version in the question does not pin the index.\n"
        )
    result = cached_call(
        "c7", "query-docs", {"libraryId": library, "query": args.query}, args.fresh
    )
    if re.search(r'Library ".*" not found', result):
        raise ResearchError(
            f"library id '{library}' not found",
            "use `research docs <name> --list` to find valid ids",
        )
    emit_response(
        (selection + "\n" if selection else "") + result,
        args,
        f"docs-{library}-{args.query}",
    )


def read_pages(
    args: argparse.Namespace, results: list[dict], client: ClientFactory
) -> list[str]:
    """Fetch the top `--read` results and swap their snippets for page passages."""
    targets = [result for result in results if result["url"]][: args.read]
    if not targets:
        return []
    options = argparse.Namespace(
        urls=[result["url"] for result in targets],
        raw=False,
        firecrawl=False,
        chars=EXA_PAGE_CHARS,
        fresh=args.fresh,
    )
    question = " ".join([*args.queries, args.objective or ""])
    notices = []
    with closing(fetch_results(options, client)) as pages:
        for result, (url, page) in zip(targets, pages):
            notices.extend(page.notices)
            if page.error is not None:
                notices.append(f"[read failed: {url}: {page.error}]")
                continue
            text = page.text.strip()
            result.update(
                page=str(save_text(text, f"fetch-{url}")),
                page_chars=len(text),
                source=page.source,
            )
            passages = ranked_passages(text, question, READ_PASSAGE_CHARS)
            if passages != NO_PASSAGES:
                result["text"] = passages
    return notices


def web_record(
    args: argparse.Namespace,
    results: list[dict],
    fitted: list[str],
    providers: list[str],
    notices: list[str],
    saved: str | None,
) -> dict:
    fields = ("title", "url", "date", "providers", "page", "source")
    return {
        "queries": args.queries,
        "providers": providers,
        "saved": saved,
        "notices": notices,
        "results": [
            {
                "rank": rank,
                **{key: result[key] for key in fields if result.get(key)},
                "text": text,
                "chars": len(result["text"]),
            }
            for rank, (result, text) in enumerate(zip(results, fitted), 1)
        ],
    }


def web(args: argparse.Namespace) -> None:
    with shared_client() as client:
        results, providers, notices = search(args, client)
        if args.read:
            notices += read_pages(args, results, client)
    label = f"web-{args.queries[0]}"
    full, compact, fitted = layout_results(
        results, args.max_chars, show_providers=len(providers) > 1
    )
    if args.json:
        saved = str(save_text(full, label)) if compact != full else None
        record = web_record(args, results, fitted, providers, notices, saved)
        print(json.dumps(record, ensure_ascii=False))
        return
    for notice in notices:
        print(notice)
    summary = f"[web: {len(results)} results via {', '.join(providers)}"
    if len(args.queries) > 1:
        summary += f" | {len(args.queries)} queries"
    if any(result.get("page") for result in results):
        summary += f" | pages saved in {config.OUTPUT}/"
    print(summary + "]")
    if args.match:
        emit_response(full, args, label)
    elif compact == full:
        print(full)
    else:
        path = save_text(full, label)
        print(saved_notice(path, full, "preview", len(compact), len(full)))
        print(compact)


def exa_fetch(
    args: argparse.Namespace,
    urls: list[str],
    *,
    client: ClientFactory | None = None,
    notices: list[str] | None = None,
) -> str:
    for url in urls:
        validate_url(url)
    notice = (
        f"[Exa extraction: ≤{args.chars:,} chars/page requested; may be incomplete]"
    )
    if notices is None:
        print(notice)
    else:
        notices.append(notice)
    return cached_call(
        "exa",
        "web_fetch_exa",
        {"urls": urls, "maxCharacters": args.chars},
        args.fresh,
        client=client,
    )


def fetch_url(
    args: argparse.Namespace,
    url: str,
    client: ClientFactory,
    notices: list[str],
) -> tuple[str, str]:
    validate_url(url)
    if args.raw:
        return cached_call(
            "raw", "fetch", {"url": url}, args.fresh, client=client
        ), "direct HTTP, unmodified"
    if args.firecrawl:
        return cached_call(
            "firecrawl", "scrape", {"url": url}, args.fresh, client=client
        ), "Firecrawl"
    try:
        return cached_call(
            "page", "fetch", {"url": url}, args.fresh, client=client
        ), "direct HTTP, markdown"
    except ResearchError as error:
        if error.final:
            raise
        notices.append(f"[direct fetch failed: {error}; falling back to Exa]")
    firecrawl = api_key("FIRECRAWL_API_KEY", "firecrawl-api-key")
    thin = None
    try:
        text = exa_fetch(args, [url], client=client, notices=notices)
        if len(text) >= THIN_PAGE_CHARS or not firecrawl:
            return text, "Exa"
        # Exa indexed the same unrendered shell; only a browser will get the page.
        thin = text
        notices.append(f"[Exa returned only {len(text)} chars; trying Firecrawl]")
    except ResearchError as error:
        if not firecrawl:
            raise
        notices.append(f"[Exa failed: {error}; falling back to Firecrawl]")
    try:
        return cached_call(
            "firecrawl", "scrape", {"url": url}, args.fresh, client=client
        ), "Firecrawl"
    except ResearchError:
        if thin is None:
            raise
        return thin, "Exa"


@dataclass
class FetchResult:
    text: str = ""
    source: str = ""
    notices: list[str] = field(default_factory=list)
    error: ResearchError | None = None


def fetch_result(
    args: argparse.Namespace, url: str, client: ClientFactory
) -> FetchResult:
    result = FetchResult()
    try:
        result.text, result.source = fetch_url(args, url, client, result.notices)
    except ResearchError as error:
        result.error = error
    return result


def fetch_results(
    args: argparse.Namespace, client: ClientFactory
) -> Generator[tuple[str, FetchResult]]:
    urls = iter(dict.fromkeys(args.urls))
    remaining = Counter(args.urls)
    repeated = {}
    with ThreadPoolExecutor(max_workers=MAX_FETCH_WORKERS) as executor:
        pending = {
            url: executor.submit(fetch_result, args, url, client)
            for url in islice(urls, MAX_FETCH_WORKERS)
        }
        for url in args.urls:
            if url in repeated:
                result = repeated[url]
            else:
                result = pending.pop(url).result()
                next_url = next(urls, None)
                if next_url is not None:
                    pending[next_url] = executor.submit(
                        fetch_result, args, next_url, client
                    )
                if remaining[url] > 1:
                    repeated[url] = result
            remaining[url] -= 1
            if not remaining[url]:
                repeated.pop(url, None)
            yield url, result


def fetch_record(url: str, result: FetchResult, rendered: Rendered) -> dict:
    return {
        "url": url,
        "source": result.source,
        "chars": rendered.chars,
        "lines": rendered.lines,
        "saved": str(rendered.path),
        "notices": result.notices,
        "text": rendered.shown,
    }


def fetch_with_exa(args: argparse.Namespace) -> None:
    """`fetch --exa`: every URL in one Exa request, reported as one response."""
    urls = list(dict.fromkeys(args.urls))
    label = f"fetch-{urls[0]}"
    if not args.json:
        emit_response(exa_fetch(args, urls), args, label, outline=True)
        return
    notices: list[str] = []
    text = exa_fetch(args, urls, notices=notices)
    rendered = render_response(text, args, label, save=True)
    record = fetch_record(urls[0], FetchResult(source="Exa", notices=notices), rendered)
    print(json.dumps({**record, "urls": urls}, ensure_ascii=False))


def print_fetched(
    args: argparse.Namespace, url: str, result: FetchResult, share: int | None
) -> int:
    """Print one URL's outcome; return the inline characters it used."""
    if result.error is not None:
        if args.json:
            error = {"error": str(result.error), "hint": result.error.hint}
            print(json.dumps({"url": url, **error, "notices": result.notices}))
        else:
            for notice in result.notices:
                print(notice)
            print(f"URL: {url} [error: {result.error} | hint: {result.error.hint}]")
        return 0
    rendered = render_response(
        result.text,
        args,
        f"fetch-{url}",
        raw=args.raw,
        budget=share,
        outline=True,
        save=args.json,
    )
    if args.json:
        print(json.dumps(fetch_record(url, result, rendered), ensure_ascii=False))
    else:
        lines = [*result.notices, f"URL: {url} [{result.source}]"]
        print("\n".join([*lines, *filter(None, (rendered.notice, rendered.shown))]))
    return rendered.used


def fetch(args: argparse.Namespace) -> None:
    if args.exa:
        fetch_with_exa(args)
        return
    budget = args.max_chars or None
    pending = len(args.urls)
    failures = 0
    with shared_client() as client, closing(fetch_results(args, client)) as results:
        for url, result in results:
            # Each page gets an equal share of what is left, so none is starved.
            share = None if budget is None else budget // pending
            pending -= 1
            failures += result.error is not None
            used = print_fetched(args, url, result, share)
            if budget is not None:
                budget -= used
    if failures == len(args.urls):
        raise ResearchError("no URL could be fetched", "see the errors above")


def examples(args: argparse.Namespace) -> None:
    result = cached_call(
        "exa",
        "get_code_context_exa",
        {"query": args.query, "numResults": args.n},
        args.fresh,
    )
    emit_response(result, args, f"examples-{args.query}")


def wiki(args: argparse.Namespace) -> None:
    if args.action == "ask":
        if not args.question:
            raise ResearchError(
                "wiki ask needs a question", 'research wiki ask owner/repo "<question>"'
            )
        repositories = args.repo.split(",") if "," in args.repo else args.repo
        result = cached_call(
            "dw",
            "ask_wiki_question",
            {"repoName": repositories, "question": args.question},
            args.fresh,
        )
    else:
        tool = (
            "read_wiki_structure" if args.action == "outline" else "read_wiki_contents"
        )
        result = cached_call("dw", tool, {"repoName": args.repo}, args.fresh)
    emit_response(result, args, f"wiki-{args.action}-{args.repo}-{args.question or ''}")


def code_index(result: str) -> str:
    """One line per hit (repo, path, snippet lines) so a preview shows every hit."""
    hits = re.findall(
        r"^Repository: (.+)\nPath: (.+)\n(?:.*\n)*?Snippets:\n((?:.*\n?)*?)(?=^Repository: |\Z)",
        result,
        flags=re.MULTILINE,
    )
    if len(hits) < 2:
        return ""
    lines = []
    for repo, path, body in hits:
        numbers = ",".join(
            re.findall(r"^--- Snippet \d+ \(Line (\d+)\)", body, re.MULTILINE)
        )
        lines.append(f"{repo} {path}" + (f":{numbers}" if numbers else ""))
    return f"Index ({len(hits)} hits):\n" + "\n".join(lines) + "\n\n"


def code(args: argparse.Namespace) -> None:
    arguments = {"query": args.query}
    for enabled, name in (
        (args.regex, "useRegexp"),
        (args.case, "matchCase"),
        (args.word, "matchWholeWords"),
    ):
        if enabled:
            arguments[name] = True
    for value, name in (
        (args.repo, "repo"),
        (args.path, "path"),
        (args.lang, "language"),
    ):
        if value:
            arguments[name] = value
    result = cached_call("grep", "searchGitHub", arguments, args.fresh)
    if result.strip().startswith("No results found"):
        filters = [f for f in ("repo", "path", "language") if f in arguments]
        raise ResearchError(
            "no matches",
            "grep.app matches literal code: shorten the snippet"
            + (f", drop --{filters[0].replace('language', 'lang')}" if filters else "")
            + ", or use `examples`/`web` instead of guessing more repos",
        )
    emit_response(code_index(result) + result, args, f"code-{args.query}")
