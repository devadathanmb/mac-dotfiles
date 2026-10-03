#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx>=0.28,<1"]
# ///
"""Research docs, web pages, repositories, and public code."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import sys
import tempfile
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import httpx

SECRETS = Path.home() / ".secrets"
WORK = Path(tempfile.gettempdir()) / f"research-{os.getuid()}"
CACHE = WORK / "cache"
OUTPUT = WORK / "out"
RETENTION_SECONDS = 24 * 3600
MAX_RAW_BYTES = 10 * 1024 * 1024

ENDPOINTS = {
    "exa": "https://mcp.exa.ai/mcp?tools=web_search_exa,web_search_advanced_exa,web_fetch_exa,get_code_context_exa",
    "c7": "https://mcp.context7.com/mcp",
    "dw": "https://mcp.deepwiki.com/mcp",
    "grep": "https://mcp.grep.app",
}
CACHE_TTL_SECONDS = {
    "c7": 24 * 3600,
    "dw": 24 * 3600,
    "grep": 6 * 3600,
    "exa": 3600,
    "raw": 3600,
}
REQUEST_TIMEOUT_SECONDS = {"dw": 240, "exa": 90, "c7": 60, "grep": 60}
DEFAULT_MAX_CHARS = 4000


class ResearchError(Exception):
    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


def api_key(environment_variable: str, filename: str) -> str | None:
    if value := os.environ.get(environment_variable):
        return value.strip()
    try:
        return (SECRETS / filename).read_text().strip() or None
    except OSError:
        return None


def auth_headers(service: str) -> dict[str, str]:
    if service == "exa":
        key = api_key("EXA_API_KEY", "exa-api-key")
        return {"x-api-key": key} if key else {}
    if service == "c7":
        key = api_key("CONTEXT7_API_KEY", "context7-api-key")
        return {"CONTEXT7_API_KEY": key} if key else {}
    return {}


def remove_expired_files() -> None:
    cutoff = time.time() - RETENTION_SECONDS
    for directory in (CACHE, OUTPUT):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        for path in directory.iterdir():
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                pass


def parse_tool_response(body: str, tool: str) -> str:
    if body.lstrip().startswith("{"):
        messages = [body]
    else:
        messages = [
            line[5:].strip() for line in body.splitlines() if line.startswith("data:")
        ]
    for message in messages:
        try:
            response = json.loads(message)
        except ValueError:
            continue
        if not isinstance(response, dict) or response.get("id") != 1:
            continue
        if "error" in response:
            error = response["error"]
            detail = error.get("message") if isinstance(error, dict) else error
            raise ResearchError(f"{tool}: {detail}")
        result = response.get("result")
        if not isinstance(result, dict) or not isinstance(
            result.get("content", []), list
        ):
            raise ResearchError(
                f"{tool}: invalid result", "retry or use another research source"
            )
        text = "\n".join(
            block["text"]
            for block in result.get("content", [])
            if isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ).strip()
        if result.get("isError"):
            raise ResearchError(f"{tool}: {text[:300]}")
        if not text:
            raise ResearchError(f"{tool}: empty result", "try a different query")
        return text
    raise ResearchError(f"{tool}: no response")


def request_tool(service: str, tool: str, arguments: dict) -> str:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "research-cli/2.0",
        **auth_headers(service),
    }
    for attempt in range(3):
        try:
            response = httpx.post(
                ENDPOINTS[service],
                json=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS[service],
                follow_redirects=True,
            )
            response.raise_for_status()
            return parse_tool_response(response.text, tool)
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            detail = error.response.text[:200].replace("\n", " ")
            if status in (429, 500, 502, 503, 504) and attempt < 2:
                retry_after = error.response.headers.get("Retry-After", "")
                delay = (
                    float(retry_after) if retry_after.isdigit() else 2**attempt * 1.5
                )
                time.sleep(min(delay, 10))
                continue
            hints = {
                401: "key rejected; check ~/.secrets or $EXA_API_KEY/$CONTEXT7_API_KEY",
                403: "blocked; retry later or try another tool",
                429: "rate limited"
                + (
                    ""
                    if auth_headers(service) or service in ("dw", "grep")
                    else " (no API key loaded; keys lift limits)"
                ),
            }
            raise ResearchError(
                f"{tool}: HTTP {status} {detail}", hints.get(status, "")
            ) from error
        except httpx.TimeoutException as error:
            raise ResearchError(
                f"{tool}: timeout", "try a narrower query or another source"
            ) from error
        except (httpx.RequestError, httpx.InvalidURL, OSError) as error:
            if attempt < 2:
                time.sleep(1.5)
                continue
            raise ResearchError(f"{tool}: {error}", "network/timeout; retry") from error
    raise ResearchError(f"{tool}: failed")


def fetch_raw(url: str) -> str:
    try:
        parts = urlsplit(url)
        if (
            parts.scheme not in ("http", "https")
            or not parts.hostname
            or parts.username
            or parts.password
        ):
            raise ResearchError("raw fetch requires an HTTP(S) URL without credentials")
        with httpx.stream(
            "GET",
            url,
            headers={"User-Agent": "research-cli/2.0", "Accept-Encoding": "identity"},
            timeout=REQUEST_TIMEOUT_SECONDS["exa"],
            follow_redirects=True,
        ) as response:
            response.raise_for_status()
            mime = (
                response.headers.get("Content-Type", "text/plain")
                .split(";", 1)[0]
                .strip()
                .lower()
            )
            if not (
                mime.startswith("text/")
                or mime.endswith(("+json", "+xml"))
                or mime
                in (
                    "application/json",
                    "application/xml",
                    "application/javascript",
                    "application/yaml",
                    "application/x-yaml",
                    "application/toml",
                    "application/octet-stream",
                )
            ):
                raise ResearchError(
                    f"raw fetch expected text, got {mime}",
                    "use fetch without --raw for page extraction",
                )
            body = bytearray()
            for chunk in response.iter_bytes(chunk_size=64 * 1024):
                if len(body) + len(chunk) > MAX_RAW_BYTES:
                    raise ResearchError(
                        "raw response exceeds 10 MiB",
                        "fetch a smaller source file or use page extraction",
                    )
                body.extend(chunk)
            text = body.decode(response.charset_encoding or "utf-8")
            if "\x00" in text:
                raise ResearchError(
                    "raw response contains binary data",
                    "use a text source or page extraction",
                )
            return text
    except httpx.HTTPStatusError as error:
        raise ResearchError(
            f"raw fetch: HTTP {error.response.status_code}",
            "check the URL or try fetch without --raw",
        ) from error
    except (UnicodeError, LookupError) as error:
        raise ResearchError(
            "raw response could not be decoded as text", "use fetch without --raw"
        ) from error
    except (httpx.RequestError, httpx.InvalidURL, OSError, ValueError) as error:
        raise ResearchError(
            f"raw fetch: {error}", "check the URL and network, then retry"
        ) from error


def cached_call(service: str, tool: str, arguments: dict, fresh: bool = False) -> str:
    key = hashlib.sha1(
        json.dumps([service, tool, arguments], sort_keys=True).encode()
    ).hexdigest()
    path = CACHE / key
    if (
        not fresh
        and path.exists()
        and time.time() - path.stat().st_mtime < CACHE_TTL_SECONDS[service]
    ):
        return path.read_bytes().decode("utf-8")
    text = (
        fetch_raw(arguments["url"])
        if service == "raw"
        else request_tool(service, tool, arguments)
    )
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", dir=CACHE, delete=False
    ) as pending:
        pending.write(text)
    try:
        os.replace(pending.name, path)
    finally:
        Path(pending.name).unlink(missing_ok=True)
    return text


def matching_lines(text: str, pattern: re.Pattern[str], context: int) -> str:
    lines = text.splitlines()
    selected = set()
    for index, line in enumerate(lines):
        if pattern.search(line):
            selected.update(
                range(max(0, index - context), min(len(lines), index + context + 1))
            )
    excerpt = []
    previous = -1
    for index in sorted(selected):
        if previous >= 0 and index > previous + 1:
            excerpt.append("...")
        excerpt.append(f"{index + 1}: {lines[index]}")
        previous = index
    return "\n".join(excerpt) or "No matching lines in this response."


def preview_length(text: str, limit: int) -> int:
    if not limit or len(text) <= limit:
        return len(text)
    cut = text.rfind("\n\n", 0, limit)
    if cut < limit * 0.5:
        cut = text.rfind("\n", 0, limit)
    return limit if cut < limit * 0.5 else cut


def emit_response(
    text: str,
    args: argparse.Namespace,
    label: str,
    *,
    raw: bool = False,
    budget: int | None = None,
) -> int:
    text = text if raw else text.strip()
    display = matching_lines(text, args.match, args.context) if args.match else text
    cut = preview_length(display, args.max_chars)
    if budget is not None:
        cut = min(cut, budget)
    if not args.match and cut == len(display):
        print(display)
        return cut
    OUTPUT.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:40] or "out"
    digest = hashlib.sha1(text.encode()).hexdigest()[:6]
    path = OUTPUT / f"{slug}-{digest}.md"
    path.write_bytes((text if raw else text + "\n").encode("utf-8"))
    if cut:
        print(display[:cut].rstrip())
    print(
        f"[saved: {path} | {len(text):,} chars, {len(text.splitlines())} lines "
        f"| {'excerpt' if args.match else 'preview'} {cut:,}/{len(display):,} chars]"
    )
    return cut


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
        result = re.sub(r"^(Title|Published|Author): N/A\n", "", result, flags=re.M)
    emit_response(result, args, f"web-{args.query}")


def fetch(args: argparse.Namespace) -> None:
    if args.raw:
        budget = args.max_chars or None
        for url in args.urls:
            result = cached_call("raw", "fetch", {"url": url}, args.fresh)
            print(f"URL: {url} [direct HTTP]")
            used = emit_response(result, args, f"fetch-{url}", raw=True, budget=budget)
            if budget is not None:
                budget -= used
    else:
        print(
            f"[Exa extraction: ≤{args.chars:,} chars/page requested; may be incomplete]"
        )
        result = cached_call(
            "exa",
            "web_fetch_exa",
            {"urls": args.urls, "maxCharacters": args.chars},
            args.fresh,
        )
        emit_response(result, args, f"fetch-{args.urls[0]}")


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
    emit_response(result, args, f"code-{args.query}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="research", description=__doc__)

    def common_options(
        parent: argparse.ArgumentParser, *, suppress_defaults: bool = False
    ) -> None:
        # Subcommand defaults must not overwrite options supplied before the command.
        def default(value):
            return argparse.SUPPRESS if suppress_defaults else value

        parent.add_argument(
            "--max-chars",
            type=int,
            default=default(DEFAULT_MAX_CHARS),
            help="inline text limit before saving to a file (default 4000, 0=unlimited)",
        )
        parent.add_argument(
            "--fresh",
            action="store_true",
            default=default(False),
            help="bypass the local cache",
        )
        parent.add_argument(
            "--match",
            default=default(None),
            metavar="REGEX",
            help="show matching lines; save the full response",
        )
        parent.add_argument(
            "--context",
            type=int,
            default=default(2),
            metavar="N",
            help="lines around matches (default 2)",
        )

    common_options(parser)
    options = argparse.ArgumentParser(add_help=False)
    common_options(options, suppress_defaults=True)
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")

    def command(name: str, help_text: str, handler) -> argparse.ArgumentParser:
        subparser = commands.add_parser(name, parents=[options], help=help_text)
        subparser.set_defaults(handler=handler)
        return subparser

    docs_parser = command("docs", "library/framework docs (Context7)", docs)
    docs_parser.add_argument(
        "library", help="name (react) or Context7 id (/vercel/next.js[/v15.1.0])"
    )
    docs_parser.add_argument(
        "query",
        nargs="?",
        default="",
        help="specific question; omit to list candidate ids",
    )
    docs_parser.add_argument(
        "--list", action="store_true", help="list candidate ids instead of fetching"
    )

    web_parser = command("web", "web search (Exa)", web)
    web_parser.add_argument("query")
    web_parser.add_argument("-n", type=int, default=5, help="results (default 5)")
    web_parser.add_argument(
        "--objective", help="what you want to learn (improves ranking)"
    )
    web_parser.add_argument(
        "--domain", action="append", help="only this domain (repeatable)"
    )
    web_parser.add_argument(
        "--exclude", action="append", help="exclude domain (repeatable)"
    )
    web_parser.add_argument("--after", metavar="YYYY-MM-DD")
    web_parser.add_argument("--before", metavar="YYYY-MM-DD")
    web_parser.add_argument(
        "--category",
        choices=[
            "news",
            "publication",
            "github",
            "company",
            "pdf",
            "people",
            "financial report",
            "personal site",
        ],
    )
    web_parser.add_argument(
        "--chars",
        type=int,
        help="Exa text chars per result (default 1500 with filters)",
    )

    fetch_parser = command("fetch", "read page(s) as markdown (Exa) or raw text", fetch)
    fetch_parser.add_argument("urls", nargs="+")
    fetch_parser.add_argument(
        "--chars",
        type=int,
        default=20000,
        help="Exa chars per page (default 20000; ignored with --raw)",
    )
    fetch_parser.add_argument(
        "--raw",
        action="store_true",
        help="fetch HTTP(S) text directly, up to 10 MiB per URL",
    )

    examples_parser = command(
        "examples", "code/API usage examples from the web (Exa)", examples
    )
    examples_parser.add_argument("query")
    examples_parser.add_argument("-n", type=int, default=3)

    wiki_parser = command(
        "wiki", "OSS repo Q&A and docs (DeepWiki; ask can take 10-60s)", wiki
    )
    wiki_parser.add_argument("action", choices=["ask", "outline", "read"])
    wiki_parser.add_argument("repo", help="owner/repo (ask: comma-separate up to 10)")
    wiki_parser.add_argument("question", nargs="?")

    code_parser = command(
        "code", "literal code search across public GitHub (grep.app)", code
    )
    code_parser.add_argument(
        "query", help="code as it appears in source; use --regex for patterns"
    )
    code_parser.add_argument("--regex", action="store_true")
    code_parser.add_argument("--case", action="store_true")
    code_parser.add_argument("--word", action="store_true")
    code_parser.add_argument("--repo", help="owner/repo (or prefix) filter")
    code_parser.add_argument("--path", help="file path filter")
    code_parser.add_argument(
        "--lang", action="append", help="language, repeatable (e.g. TypeScript)"
    )
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.max_chars < 0 or args.context < 0:
        raise ResearchError("--max-chars and --context must be nonnegative")
    if hasattr(args, "n") and not 1 <= args.n <= 100:
        raise ResearchError("-n must be between 1 and 100")
    if (
        getattr(args, "chars", None) is not None
        and not getattr(args, "raw", False)
        and args.chars < 1
    ):
        raise ResearchError(
            "--chars must be positive; --max-chars controls inline output"
        )
    if args.command == "docs" and args.library.startswith("/"):
        if not args.query.strip() or args.list:
            raise ResearchError(
                "docs with a library ID requires a question, without --list",
                'use docs <name> --list or docs <id> "<question>"',
            )
    if args.command == "web":
        filtered = any(
            (args.domain, args.exclude, args.after, args.before, args.category)
        )
        if args.objective and (filtered or args.chars is not None):
            raise ResearchError(
                "--objective cannot be combined with filters or --chars",
                "put the objective in the query for filtered searches",
            )
        for value in (args.after, args.before):
            if value:
                try:
                    date.fromisoformat(value)
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                        raise ValueError
                except ValueError as error:
                    raise ResearchError(
                        "dates must be valid YYYY-MM-DD values"
                    ) from error
        if args.after and args.before and args.after > args.before:
            raise ResearchError("--after must not be later than --before")
    if args.command == "wiki":
        repositories = [repo.strip() for repo in args.repo.split(",")]
        if any(not re.fullmatch(r"[\w.-]+/[\w.-]+", repo) for repo in repositories):
            raise ResearchError("wiki repositories must use owner/repo format")
        if args.action == "ask":
            if not args.question or not args.question.strip():
                raise ResearchError("wiki ask requires a question")
            if len(repositories) > 10:
                raise ResearchError("wiki ask supports at most 10 repositories")
        elif len(repositories) != 1 or args.question is not None:
            raise ResearchError(
                "wiki outline/read takes one repository and no question"
            )
        args.repo = ",".join(repositories)
    if args.match is not None:
        try:
            args.match = re.compile(args.match)
        except re.error as error:
            raise ResearchError(
                f"invalid --match regex: {error}",
                "escape punctuation or use a valid regex",
            ) from error


def main() -> int:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    args = build_parser().parse_args()
    try:
        validate_args(args)
        remove_expired_files()
        args.handler(args)
    except (ResearchError, OSError) as error:
        message = " ".join(str(error).splitlines())
        hint = " ".join(
            getattr(error, "hint", "check local cache/output permissions").splitlines()
        )
        print(
            f"error: {message}" + (f" | hint: {hint}" if hint else ""), file=sys.stderr
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
