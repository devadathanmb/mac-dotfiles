"""`docs`: library documentation from Context7, by library name or ID."""

import re
from dataclasses import dataclass

from ..cache import cached
from ..errors import ResearchError
from ..mcp import call_tool
from ..output import Output, emit
from ..transport import Http

LISTING_FIELDS = (
    ("Source Reputation", "reputation"),
    ("Code Snippets", "snippets"),
    ("Benchmark Score", "score"),
)
LIBRARY_ID = "Context7-compatible library ID"


@dataclass(frozen=True)
class DocsOptions:
    library: str  # a name, or an ID starting with "/"
    query: str
    list_only: bool
    fresh: bool
    output: Output


def field(block: str, name: str) -> str:
    match = re.search(rf"{name}: *(.*)", block)
    return match.group(1).strip() if match else ""


def summary(block: str) -> str:
    """One candidate library: name, ID, description, ranking signals, versions."""
    metadata = "; ".join(
        f"{label}: {value}"
        for name, label in LISTING_FIELDS
        if (value := field(block, name))
    )
    lines = (
        f"### {field(block, 'Title')} — {field(block, LIBRARY_ID)}",
        field(block, "Description"),
        metadata,
        f"Versions: {field(block, 'Versions') or 'not listed'}",
    )
    return "\n".join(line for line in lines if line)


def query_context7(
    http: Http, tool: str, arguments: dict[str, str], fresh: bool
) -> str:
    return cached(
        "context7",
        [tool, arguments],
        lambda: call_tool(http, "context7", tool, arguments),
        fresh=fresh,
    )


def run(options: DocsOptions) -> None:
    library = options.library
    selection = ""
    with Http() as http:
        if not library.startswith("/"):
            result = query_context7(
                http,
                "resolve-library-id",
                {"libraryName": library, "query": options.query or library},
                options.fresh,
            )
            blocks = [
                block
                for block in re.split(r"\n(?=- Title:)", result)
                if f"{LIBRARY_ID}:" in block
            ]
            if not blocks:
                raise ResearchError(
                    f"no library matches '{library}'", "try a different name, or `web`"
                )
            if options.list_only or not options.query:
                listing = (
                    f"# Context7 candidates ({len(blocks)})\n"
                    'Next: `docs <id> "<question>"`; pin versions with '
                    "`<id>/<exact-listed-version>`.\n\n"
                    + "\n\n".join(summary(block) for block in blocks)
                )
                emit(listing, f"docs-list-{library}", options.output)
                return
            library = field(blocks[0], LIBRARY_ID)
            selection = (
                f"Selection: first match of {len(blocks)}; use --list to compare.\n"
            )
        if len(library.strip("/").split("/")) == 2:
            selection += (
                "Version: unpinned; a version in the question does not pin the index.\n"
            )
        result = query_context7(
            http,
            "query-docs",
            {"libraryId": library, "query": options.query},
            options.fresh,
        )
    if re.search(r'Library ".*" not found', result):
        raise ResearchError(
            f"library id '{library}' not found",
            "use `research docs <name> --list` to find valid ids",
        )
    print(f"# Context7: {library}")
    emit(
        (selection + "\n" if selection else "") + result,
        f"docs-{library}-{options.query}",
        options.output,
    )
