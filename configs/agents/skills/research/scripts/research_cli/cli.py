"""Argument parsing, validation, and the process entry point."""

import argparse
import re
import signal
import sys
from datetime import date

from . import commands as handlers
from .cache import remove_expired_files
from .config import DEFAULT_MAX_CHARS, EXA_PAGE_CHARS, ResearchError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="research",
        description="Research docs, web pages, repositories, and public code.",
        epilog="Saved responses and the cache live in $TMPDIR/research-<uid>/ "
        "for 24 hours; set TMPDIR to move them.",
    )

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
    # Only `fetch` offers these selectors; every command's output code reads them.
    parser.set_defaults(section=None, about=None, lines=None)
    options = argparse.ArgumentParser(add_help=False)
    common_options(options, suppress_defaults=True)
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")

    def command(name: str, help_text: str, handler) -> argparse.ArgumentParser:
        subparser = commands.add_parser(name, parents=[options], help=help_text)
        subparser.set_defaults(handler=handler)
        return subparser

    docs_parser = command("docs", "library/framework docs (Context7)", handlers.docs)
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

    web_parser = command(
        "web", "web search (Exa → Parallel → Brave → Tavily)", handlers.web
    )
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
        help="page text chars per result (default 1500); Exa then returns "
        "page text instead of highlights",
    )

    fetch_parser = command(
        "fetch",
        "read page(s) as markdown (direct HTTP → Exa → Firecrawl)",
        handlers.fetch,
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
        help="use Exa extraction instead of direct fetch (JS-rendered or blocked pages)",
    )
    mode.add_argument(
        "--firecrawl",
        action="store_true",
        help="use Firecrawl scraping directly (requires FIRECRAWL_API_KEY)",
    )

    examples_parser = command(
        "examples", "code/API usage examples from the web (Exa)", handlers.examples
    )
    examples_parser.add_argument("query")
    examples_parser.add_argument("-n", type=int, default=3)

    wiki_parser = command(
        "wiki", "OSS repo Q&A and docs (DeepWiki; ask can take 10-60s)", handlers.wiki
    )
    wiki_parser.add_argument("action", choices=["ask", "outline", "read"])
    wiki_parser.add_argument("repo", help="owner/repo (ask: comma-separate up to 10)")
    wiki_parser.add_argument("question", nargs="?")

    code_parser = command(
        "code", "literal code search across public GitHub (grep.app)", handlers.code
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


def validate_docs(args: argparse.Namespace) -> None:
    if args.library.startswith("/") and (not args.query.strip() or args.list):
        raise ResearchError(
            "docs with a library ID requires a question, without --list",
            'use docs <name> --list or docs <id> "<question>"',
        )


def validate_web(args: argparse.Namespace) -> None:
    if not 0 <= args.read <= 5:
        raise ResearchError("--read must be between 0 and 5")
    if any(not query.strip() for query in args.queries):
        raise ResearchError("queries must not be empty")
    filtered = any((args.domain, args.exclude, args.after, args.before, args.category))
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
                raise ResearchError("dates must be valid YYYY-MM-DD values") from error
    if args.after and args.before and args.after > args.before:
        raise ResearchError("--after must not be later than --before")


def validate_wiki(args: argparse.Namespace) -> None:
    repositories = [repo.strip() for repo in args.repo.split(",")]
    if any(not re.fullmatch(r"[\w.-]+/[\w.-]+", repo) for repo in repositories):
        raise ResearchError("wiki repositories must use owner/repo format")
    if args.action == "ask":
        if not args.question or not args.question.strip():
            raise ResearchError("wiki ask requires a question")
        if len(repositories) > 10:
            raise ResearchError("wiki ask supports at most 10 repositories")
    elif len(repositories) != 1 or args.question is not None:
        raise ResearchError("wiki outline/read takes one repository and no question")
    args.repo = ",".join(repositories)


def validate_selectors(args: argparse.Namespace) -> None:
    """Check the excerpt selectors and replace them with their parsed forms."""
    selectors = (args.match, args.section, args.about, args.lines)
    if sum(value is not None for value in selectors) > 1:
        raise ResearchError("use only one of --match, --section, --query, and --lines")
    if args.lines is not None:
        span = re.fullmatch(r"(\d+)-(\d+)", args.lines)
        if not span or not 1 <= int(span.group(1)) <= int(span.group(2)):
            raise ResearchError("--lines takes a range such as 120-180")
        args.lines = (int(span.group(1)), int(span.group(2)))
    try:
        if args.section is not None:
            args.section = re.compile(args.section, re.IGNORECASE)
        if args.match is not None:
            args.match = re.compile(args.match)
    except re.error as error:
        raise ResearchError(
            f"invalid regex: {error}", "escape punctuation or use a valid regex"
        ) from error


COMMAND_VALIDATORS = {"docs": validate_docs, "web": validate_web, "wiki": validate_wiki}


def validate_args(args: argparse.Namespace) -> None:
    if args.max_chars < 0 or args.context < 0:
        raise ResearchError("--max-chars and --context must be nonnegative")
    if getattr(args, "n", None) is not None and not 1 <= args.n <= 100:
        raise ResearchError("-n must be between 1 and 100")
    if (
        getattr(args, "chars", None) is not None
        and not getattr(args, "raw", False)
        and args.chars < 1
    ):
        raise ResearchError(
            "--chars must be positive; --max-chars controls inline output"
        )
    if validate_command := COMMAND_VALIDATORS.get(args.command):
        validate_command(args)
    validate_selectors(args)


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
