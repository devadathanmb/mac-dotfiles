"""The one error type the CLI reports, with a hint for the agent's next step."""


class ResearchError(Exception):
    """A failure the agent can act on.

    `final` marks failures no other source can fix (an HTTP 404, an oversized
    response), so fallback chains stop instead of spending quota. `status` is
    the HTTP status behind the failure, when there was one.
    """

    def __init__(
        self,
        message: str,
        hint: str = "",
        *,
        final: bool = False,
        status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.final = final
        self.status = status
