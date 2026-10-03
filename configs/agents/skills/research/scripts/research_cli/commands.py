"""One handler per CLI subcommand."""

import argparse
import json
import re

from .cache import cached_call
from .config import ResearchError
from .output import emit_response


def library_field(block: str, name: str) -> str:
    match = re.search(rf"{name}: *(.*)", block)
    return match.group(1).strip() if match else ""


def docs(args: argparse.Namespace) -> None:
    library = args.library
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
            listing = "\n".join(
                f"{library_field(block, 'Context7-compatible library ID')}  {library_field(block, 'Title')}  "
                f"[{library_field(block, 'Source Reputation')}]  {library_field(block, 'Description')[:90]}"
                for block in blocks[:8]
            )
            emit_response(listing, args, f"docs-list-{library}")
            if not args.query:
                print('\n(pass a query to fetch docs: research docs <id> "<question>")')
            return
        library = library_field(blocks[0], "Context7-compatible library ID")
    print(f"# Context7: {library}")
    result = cached_call(
        "c7", "query-docs", {"libraryId": library, "query": args.query}, args.fresh
    )
    if re.search(r'Library ".*" not found', result):
        raise ResearchError(
            f"library id '{library}' not found",
            "use `research docs <name> --list` to find valid ids",
        )
    emit_response(result, args, f"docs-{library}-{args.query}")


def format_search_results(response: str) -> str:
    try:
        results = json.loads(response)["results"]
        return (
            "\n\n".join(
                f"{(result.get('title') or '').strip()} {result.get('publishedDate') or ''}".strip()
                + f"\n{result['url']}\n{(result.get('text') or '').strip()}"
                for result in results
            )
            or response
        )
    except (ValueError, KeyError, TypeError, AttributeError):
        return response


def web(args: argparse.Namespace) -> None:
    arguments = {"query": args.query, "numResults": args.n}
    if (
        any((args.domain, args.exclude, args.after, args.before, args.category))
        or args.chars is not None
    ):
        chars = args.chars if args.chars is not None else 1500
        print(f"[Exa extraction: ≤{chars:,} chars/result requested; may be incomplete]")
        arguments.update(textMaxCharacters=chars, enableHighlights=False, type="auto")
        for value, name in (
            (args.domain, "includeDomains"),
            (args.exclude, "excludeDomains"),
            (args.after, "startPublishedDate"),
            (args.before, "endPublishedDate"),
            (args.category, "category"),
        ):
            if value:
                arguments[name] = value
        result = cached_call("exa", "web_search_advanced_exa", arguments, args.fresh)
        result = format_search_results(result)
    else:
        arguments["objective"] = args.objective or args.query
        result = cached_call("exa", "web_search_exa", arguments, args.fresh)
        result = re.sub(
            r"^(Title|Published|Author): N/A\n", "", result, flags=re.MULTILINE
        )
    emit_response(result, args, f"web-{args.query}")


def exa_fetch(args: argparse.Namespace, urls: list[str]) -> str:
    print(f"[Exa extraction: ≤{args.chars:,} chars/page requested; may be incomplete]")
    return cached_call(
        "exa",
        "web_fetch_exa",
        {"urls": urls, "maxCharacters": args.chars},
        args.fresh,
    )


def fetch(args: argparse.Namespace) -> None:
    if args.exa:
        emit_response(exa_fetch(args, args.urls), args, f"fetch-{args.urls[0]}")
        return
    budget = args.max_chars or None
    failures = 0
    for url in args.urls:
        if args.raw:
            result = cached_call("raw", "fetch", {"url": url}, args.fresh)
            print(f"URL: {url} [direct HTTP, unmodified]")
        else:
            try:
                result = cached_call("page", "fetch", {"url": url}, args.fresh)
                print(f"URL: {url} [direct HTTP, markdown]")
            except ResearchError as error:
                if error.final:
                    print(f"URL: {url} [error: {error} | hint: {error.hint}]")
                    failures += 1
                    continue
                print(f"[direct fetch failed: {error}; falling back to Exa]")
                result = exa_fetch(args, [url])
                print(f"URL: {url} [Exa]")
        used = emit_response(result, args, f"fetch-{url}", raw=args.raw, budget=budget)
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
