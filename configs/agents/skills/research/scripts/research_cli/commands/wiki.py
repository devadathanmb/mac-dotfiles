"""`wiki`: DeepWiki's generated documentation and Q&A for public repositories."""

from dataclasses import dataclass
from typing import Literal

from ..cache import cached
from ..mcp import call_tool
from ..output import Output, emit
from ..transport import Http

TOOLS = {
    "ask": "ask_wiki_question",
    "outline": "read_wiki_structure",
    "read": "read_wiki_contents",
}


@dataclass(frozen=True)
class WikiOptions:
    action: Literal["ask", "outline", "read"]
    repos: list[str]  # owner/repo; several only for `ask`
    question: str | None
    fresh: bool
    output: Output


def run(options: WikiOptions) -> None:
    tool = TOOLS[options.action]
    # DeepWiki takes a list only when asking across several repositories.
    repos: str | list[str] = (
        options.repos if len(options.repos) > 1 else options.repos[0]
    )
    arguments: dict[str, str | list[str]] = {"repoName": repos}
    if options.question is not None:
        arguments["question"] = options.question
    with Http() as http:
        result = cached(
            "deepwiki",
            [tool, arguments],
            lambda: call_tool(http, "deepwiki", tool, arguments),
            fresh=options.fresh,
        )
    label = f"wiki-{options.action}-{','.join(options.repos)}-{options.question or ''}"
    emit(result, label, options.output)
