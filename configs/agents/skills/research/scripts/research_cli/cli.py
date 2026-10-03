"""Argument parsing, validation, and the process entry point."""

import argparse
import re
import signal
import sys
from datetime import date

from . import commands as handlers
from .cache import remove_expired_files
from .config import DEFAULT_MAX_CHARS, ResearchError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="research",
        description="Research docs, web pages, repositories, and public code.",
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

    web_parser = command("web", "web search (Exa)", handlers.web)
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

    fetch_parser = command(
        "fetch",
        "read page(s) as markdown (HTML converted locally; Exa fallback)",
        handlers.fetch,
    )
    fetch_parser.add_argument("urls", nargs="+")
    fetch_parser.add_argument(
        "--chars",
        type=int,
        default=20000,
        help="Exa chars per page (default 20000; only with --exa or fallback)",
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
    if (
        args.command == "docs"
        and args.library.startswith("/")
        and (not args.query.strip() or args.list)
    ):
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
