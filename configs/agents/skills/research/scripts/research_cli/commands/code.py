"""`code`: literal or regex code search across public GitHub, via grep.app."""

import re
from dataclasses import dataclass
from typing import Any

from ..cache import cached
from ..errors import ResearchError
from ..mcp import call_tool
from ..output import Output, emit
from ..transport import Http

# One search hit: repository, path, and its snippets up to the next hit.
HIT = re.compile(
    r"^Repository: (.+)\nPath: (.+)\n(?:.*\n)*?Snippets:\n"
    r"((?:.*\n?)*?)(?=^Repository: |\Z)",
    re.MULTILINE,
)
SNIPPET_LINE = re.compile(r"^--- Snippet \d+ \(Line (\d+)\)", re.MULTILINE)


@dataclass(frozen=True)
class CodeOptions:
    query: str
    output: Output
    regex: bool = False
    case: bool = False
    word: bool = False
    repo: str | None = None
    path: str | None = None
    languages: tuple[str, ...] = ()
    fresh: bool = False


def index(result: str) -> str:
    """One line per hit (repo, path, snippet lines) so a preview shows every hit."""
    hits = HIT.findall(result)
    if len(hits) < 2:
        return ""
    lines = []
    for repo, path, body in hits:
        numbers = ",".join(SNIPPET_LINE.findall(body))
        lines.append(f"{repo} {path}" + (f":{numbers}" if numbers else ""))
    return f"Index ({len(hits)} hits):\n" + "\n".join(lines) + "\n\n"


def arguments(options: CodeOptions) -> dict[str, Any]:
    query: dict[str, Any] = {"query": options.query}
    for enabled, name in (
        (options.regex, "useRegexp"),
        (options.case, "matchCase"),
        (options.word, "matchWholeWords"),
    ):
        if enabled:
            query[name] = True
    for value, name in (
        (options.repo, "repo"),
        (options.path, "path"),
        (list(options.languages), "language"),
    ):
        if value:
            query[name] = value
    return query


def run(options: CodeOptions) -> None:
    query = arguments(options)
    with Http() as http:
        result = cached(
            "grep",
            ["searchGitHub", query],
            lambda: call_tool(http, "grep", "searchGitHub", query),
            fresh=options.fresh,
        )
    if result.strip().startswith("No results found"):
        filters = [
            flag
            for flag, name in (
                ("--repo", "repo"),
                ("--path", "path"),
                ("--lang", "language"),
            )
            if name in query
        ]
        raise ResearchError(
            "no matches",
            "grep.app matches literal code: shorten the snippet"
            + (f", drop {filters[0]}" if filters else "")
            + ", or use `examples`/`web` instead of guessing more repos",
        )
    emit(index(result) + result, f"code-{options.query}", options.output)
