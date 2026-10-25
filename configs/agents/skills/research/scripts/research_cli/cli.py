"""Argument parsing and validation, and the process entry point.

Arguments are checked here, before any network call, and turned into each
command's typed options; no command sees argparse.
"""

import argparse
import re
import signal
import sys
from collections.abc import Callable
from datetime import date
from functools import partial

from . import __version__
from .cache import remove_expired_files
from .commands import code, docs, examples, fetch, web, wiki
from .config import DEFAULT_MAX_CHARS, EXA_PAGE_CHARS
from .errors import ResearchError
from .fetching import FetchOptions, Mode
from .output import Output, Selection
from .providers import SearchRequest
from .search import result_count

EXA_CATEGORIES = (
    "news",
    "publication",
    "github",
    "company",
    "pdf",
    "people",
    "financial report",
    "personal site",
)
MAX_READ = 5
MAX_WIKI_REPOS = 10
REPO = re.compile(r"[\w.-]+/[\w.-]+")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

CommandFactory = Callable[[str, str], argparse.ArgumentParser]


def add_common_options(
    parser: argparse.ArgumentParser, *, suppress_defaults: bool = False
) -> None:
    """Options accepted before or after the command name."""

    # A subcommand's defaults would overwrite options given before the command.
    def default(value: object) -> object:
        return argparse.SUPPRESS if suppress_defaults else value

    parser.add_argument(
        "--max-chars",
        type=int,
        default=default(DEFAULT_MAX_CHARS),
        help="inline text limit before saving to a file (default 4000, 0=unlimited)",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        default=default(False),
        help="bypass the local cache",
    )
    parser.add_argument(
        "--match",
        default=default(None),
        metavar="REGEX",
        help="show matching lines; save the full response",
    )
    parser.add_argument(
        "--context",
        type=int,
        default=default(2),
        metavar="N",
        help="lines around matches (default 2)",
    )


def add_docs(command: CommandFactory) -> None:
    docs_parser = command("docs", "library/framework docs (Context7)")
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


def add_web(command: CommandFactory) -> None:
    web_parser = command("web", "web search (Exa → Parallel → Brave → Tavily)")
    web_parser.add_argument(
        "queries", nargs="+", metavar="query", help="one or more queries, merged"
    )
    web_parser.add_argument(
        "-n",
        type=int,
        help="results in total (default 5; 3 per query for several, at most 20)",
    )
    web_parser.add_argument(
        "--backend",
        default="auto",
        help="auto (first provider with results), all (fuse every configured "
        "provider), or a comma list of exa,parallel,brave,tavily",
    )
    web_parser.add_argument(
        "--read",
        type=int,
        default=0,
        metavar="N",
        help="also fetch the top N pages and show their most relevant passages",
    )
    web_parser.add_argument("--json", action="store_true", help="print one JSON object")
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
    web_parser.add_argument("--category", choices=EXA_CATEGORIES)
    web_parser.add_argument(
        "--chars",
        type=int,
        help="page text chars per result (default 1500); Exa then returns "
        "page text instead of highlights",
    )


def add_fetch(command: CommandFactory) -> None:
    fetch_parser = command(
        "fetch", "read page(s) as markdown (site API or direct HTTP → Exa → Firecrawl)"
    )
    fetch_parser.add_argument("urls", nargs="+")
    fetch_parser.add_argument(
        "--query",
        dest="about",
        metavar="QUESTION",
        help="show the passages most relevant to a question; save the full response",
    )
    fetch_parser.add_argument(
        "--section",
        metavar="REGEX",
        help="show whole sections whose heading matches (case-insensitive)",
    )
    fetch_parser.add_argument(
        "--lines",
        metavar="A-B",
        help="show source lines A to B, numbered (as cited in excerpts and outlines)",
    )
    fetch_parser.add_argument(
        "--json", action="store_true", help="print one JSON object per URL"
    )
    fetch_parser.add_argument(
        "--chars",
        type=int,
        default=EXA_PAGE_CHARS,
        help="Exa chars per page (default 200000; only with --exa or fallback)",
    )
    mode = fetch_parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--raw",
        action="store_true",
        help="return the HTTP body unmodified (HTML stays HTML), up to 10 MiB",
    )
    mode.add_argument(
        "--exa",
        action="store_true",
        help="use Exa extraction (JS-rendered or blocked pages)",
    )
    mode.add_argument(
        "--firecrawl",
        action="store_true",
        help="use Firecrawl scraping directly (requires FIRECRAWL_API_KEY)",
    )


def add_examples(command: CommandFactory) -> None:
    examples_parser = command("examples", "code/API usage examples from the web (Exa)")
    examples_parser.add_argument("query")
    examples_parser.add_argument("-n", type=int, default=3)


def add_wiki(command: CommandFactory) -> None:
    wiki_parser = command(
        "wiki", "OSS repo Q&A and docs (DeepWiki; ask can take 10-60s)"
    )
    wiki_parser.add_argument("action", choices=["ask", "outline", "read"])
    wiki_parser.add_argument("repo", help="owner/repo (ask: comma-separate up to 10)")
    wiki_parser.add_argument("question", nargs="?")


def add_code(command: CommandFactory) -> None:
    code_parser = command("code", "literal code search across public GitHub (grep.app)")
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="research",
        description="Research docs, web pages, repositories, and public code.",
        epilog="Saved responses and the cache live in $TMPDIR/research-<uid>/ "
        "for 24 hours; set TMPDIR to move them.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    add_common_options(parser)
    # Only `fetch` offers these selectors; the shared output code reads them.
    parser.set_defaults(section=None, about=None, lines=None)
    shared = argparse.ArgumentParser(add_help=False)
    add_common_options(shared, suppress_defaults=True)
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")

    def command(name: str, help_text: str) -> argparse.ArgumentParser:
        return commands.add_parser(name, parents=[shared], help=help_text)

    add_docs(command)
    add_web(command)
    add_fetch(command)
    add_examples(command)
    add_wiki(command)
    add_code(command)
    return parser


def output_options(args: argparse.Namespace) -> Output:
    if args.max_chars < 0 or args.context < 0:
        raise ResearchError("--max-chars and --context must be nonnegative")
    selectors = (args.match, args.section, args.about, args.lines)
    if sum(value is not None for value in selectors) > 1:
        raise ResearchError("use only one of --match, --section, --query, and --lines")
    lines = None
    if args.lines is not None:
        span = re.fullmatch(r"(\d+)-(\d+)", args.lines)
        if not span or not 1 <= int(span.group(1)) <= int(span.group(2)):
            raise ResearchError("--lines takes a range such as 120-180")
        lines = (int(span.group(1)), int(span.group(2)))
    try:
        section = re.compile(args.section, re.IGNORECASE) if args.section else None
        match = re.compile(args.match) if args.match is not None else None
    except re.error as error:
        raise ResearchError(
            f"invalid regex: {error}", "escape punctuation or use a valid regex"
        ) from error
    selection = Selection(
        match=match,
        context=args.context,
        section=section,
        query=args.about,
        lines=lines,
    )
    return Output(limit=args.max_chars or None, selection=selection)


def check_count(value: int | None) -> None:
    if value is not None and not 1 <= value <= 100:
        raise ResearchError("-n must be between 1 and 100")


def check_date(value: str | None) -> None:
    if value is None:
        return
    try:
        if not ISO_DATE.fullmatch(value):
            raise ValueError(value)
        date.fromisoformat(value)
    except ValueError as error:
        raise ResearchError("dates must be valid YYYY-MM-DD values") from error


def docs_options(args: argparse.Namespace, output: Output) -> docs.DocsOptions:
    if args.library.startswith("/") and (not args.query.strip() or args.list):
        raise ResearchError(
            "docs with a library ID requires a question, without --list",
            'use docs <name> --list or docs <id> "<question>"',
        )
    return docs.DocsOptions(args.library, args.query, args.list, args.fresh, output)


def web_options(args: argparse.Namespace, output: Output) -> web.WebOptions:
    check_count(args.n)
    if not 0 <= args.read <= MAX_READ:
        raise ResearchError(f"--read must be between 0 and {MAX_READ}")
    if any(not query.strip() for query in args.queries):
        raise ResearchError("queries must not be empty")
    if args.chars is not None and args.chars < 1:
        raise ResearchError(
            "--chars must be positive; --max-chars controls inline output"
        )
    filtered = any((args.domain, args.exclude, args.after, args.before, args.category))
    if args.objective and (filtered or args.chars is not None):
        raise ResearchError(
            "--objective cannot be combined with filters or --chars",
            "put the objective in the query for filtered searches",
        )
    check_date(args.after)
    check_date(args.before)
    if args.after and args.before and args.after > args.before:
        raise ResearchError("--after must not be later than --before")
    queries = list(dict.fromkeys(args.queries))
    request = SearchRequest(
        query="",
        count=result_count(len(queries), args.n),
        domains=tuple(args.domain or ()),
        exclude=tuple(args.exclude or ()),
        after=args.after,
        before=args.before,
        category=args.category,
        chars=args.chars,
        objective=args.objective,
        fresh=args.fresh,
    )
    return web.WebOptions(queries, args.backend, request, args.read, args.json, output)


def fetch_options(
    args: argparse.Namespace, output: Output
) -> fetch.FetchCommandOptions:
    if not args.raw and args.chars < 1:
        raise ResearchError(
            "--chars must be positive; --max-chars controls inline output"
        )
    mode = (
        Mode.RAW
        if args.raw
        else Mode.EXA
        if args.exa
        else Mode.FIRECRAWL
        if args.firecrawl
        else Mode.AUTO
    )
    options = FetchOptions(mode=mode, fresh=args.fresh, exa_chars=args.chars)
    return fetch.FetchCommandOptions(args.urls, options, args.json, output)


def examples_options(
    args: argparse.Namespace, output: Output
) -> examples.ExamplesOptions:
    check_count(args.n)
    return examples.ExamplesOptions(args.query, args.n, args.fresh, output)


def wiki_options(args: argparse.Namespace, output: Output) -> wiki.WikiOptions:
    repos = [repo.strip() for repo in args.repo.split(",")]
    if any(not REPO.fullmatch(repo) for repo in repos):
        raise ResearchError("wiki repositories must use owner/repo format")
    if args.action == "ask":
        if not args.question or not args.question.strip():
            raise ResearchError("wiki ask requires a question")
        if len(repos) > MAX_WIKI_REPOS:
            raise ResearchError(
                f"wiki ask supports at most {MAX_WIKI_REPOS} repositories"
            )
    elif len(repos) != 1 or args.question is not None:
        raise ResearchError("wiki outline/read takes one repository and no question")
    return wiki.WikiOptions(args.action, repos, args.question, args.fresh, output)


def code_options(args: argparse.Namespace, output: Output) -> code.CodeOptions:
    return code.CodeOptions(
        query=args.query,
        regex=args.regex,
        case=args.case,
        word=args.word,
        repo=args.repo,
        path=args.path,
        languages=tuple(args.lang or ()),
        fresh=args.fresh,
        output=output,
    )


def prepare(args: argparse.Namespace) -> Callable[[], None]:
    """Validate `args` and bind them to their command, without running it."""
    output = output_options(args)
    match args.command:
        case "docs":
            return partial(docs.run, docs_options(args, output))
        case "web":
            return partial(web.run, web_options(args, output))
        case "fetch":
            return partial(fetch.run, fetch_options(args, output))
        case "examples":
            return partial(examples.run, examples_options(args, output))
        case "wiki":
            return partial(wiki.run, wiki_options(args, output))
        case "code":
            return partial(code.run, code_options(args, output))
    raise AssertionError(f"unhandled command {args.command}")


def report(message: str, hint: str) -> None:
    sys.stdout.flush()  # keep printed results ahead of the error that ends them
    line = f"error: {' '.join(message.splitlines())}"
    if hint:
        line += f" | hint: {' '.join(hint.splitlines())}"
    print(line, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    args = build_parser().parse_args(argv)
    try:
        command = prepare(args)
        remove_expired_files()
        command()
    except ResearchError as error:
        report(error.message, error.hint)
        return 1
    except OSError as error:
        # Network errors arrive as ResearchError; this is the cache or output dir.
        report(str(error), "check local cache/output permissions")
        return 1
    return 0
