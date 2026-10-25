"""`examples`: code and API usage examples from Exa's code index."""

from dataclasses import dataclass

from ..cache import cached
from ..mcp import call_tool
from ..output import Output, emit
from ..transport import Http


@dataclass(frozen=True)
class ExamplesOptions:
    query: str
    count: int
    fresh: bool
    output: Output


def run(options: ExamplesOptions) -> None:
    tool = "get_code_context_exa"
    arguments = {"query": options.query, "numResults": options.count}
    with Http() as http:
        result = cached(
            "exa",
            [tool, arguments],
            lambda: call_tool(http, "exa", tool, arguments),
            fresh=options.fresh,
        )
    emit(result, f"examples-{options.query}", options.output)
