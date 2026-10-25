"""Firecrawl renders a page in a browser; it reads what direct fetches cannot."""

from typing import Any

from .credentials import KEYS, api_key
from .errors import ResearchError
from .pages import redirect_notice, validate_url
from .transport import Http, json_body

ENDPOINT = "https://api.firecrawl.dev/v2/scrape"
LABEL = "Firecrawl"


def configured() -> bool:
    return api_key("firecrawl") is not None


def scrape(http: Http, url: str, *, fresh: bool = False) -> str:
    validate_url(url)
    key = api_key("firecrawl")
    if not key:
        raise ResearchError(
            "Firecrawl key not configured", f"set {KEYS['firecrawl'].locations}"
        )
    payload: dict[str, Any] = {
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True,
    }
    if fresh:
        payload["maxAge"] = 0  # Firecrawl otherwise serves its own cached copy
    response = http.call_api(
        "firecrawl",
        "POST",
        ENDPOINT,
        label=LABEL,
        hint="try another source",
        status_hints={
            401: f"check {KEYS['firecrawl'].locations}",
            402: "Firecrawl credits exhausted",
            429: "Firecrawl rate limited; retry later",
        },
        # Error bodies can echo the request; the status and hint say enough.
        show_body=False,
        headers={"Authorization": f"Bearer {key}"},
        json=payload,
    )
    result = json_body(response, LABEL)
    if not isinstance(result, dict) or result.get("success") is not True:
        raise ResearchError("Firecrawl: scrape failed", "try another source")
    data = result.get("data")
    if not isinstance(data, dict):
        raise ResearchError("Firecrawl: invalid response")
    metadata = data.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    status = metadata.get("statusCode")
    if isinstance(status, int) and status >= 400:
        raise ResearchError(f"Firecrawl: page HTTP {status}", "try another source")
    markdown = data.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        raise ResearchError("Firecrawl: empty markdown", "try another source")
    served = metadata.get("url")
    return redirect_notice(url, served if isinstance(served, str) else url) + (
        markdown.strip()
    )
