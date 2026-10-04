"""Firecrawl's scrape API supplies markdown when ordinary fetches are blocked."""

import httpx

from .config import ResearchError
from .credentials import api_key
from .network import open_client, request_timeout
from .pages import validate_url


def scrape_page(
    url: str, fresh: bool = False, *, client: httpx.Client | None = None
) -> str:
    validate_url(url)
    key = api_key("FIRECRAWL_API_KEY", "firecrawl-api-key")
    if not key:
        raise ResearchError(
            "Firecrawl key not configured",
            "set $FIRECRAWL_API_KEY or ~/.secrets/firecrawl-api-key",
        )
    payload = {"url": url, "formats": ["markdown"], "onlyMainContent": True}
    if fresh:
        payload["maxAge"] = 0
    try:
        with open_client(client) as http:
            response = http.post(
                "https://api.firecrawl.dev/v2/scrape",
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
                timeout=request_timeout("firecrawl"),
                follow_redirects=False,
            )
        response.raise_for_status()
        result = response.json()
    except httpx.HTTPStatusError as error:
        hints = {
            401: "check $FIRECRAWL_API_KEY or ~/.secrets/firecrawl-api-key",
            402: "Firecrawl credits exhausted",
            429: "Firecrawl rate limited; retry later",
        }
        status = error.response.status_code
        raise ResearchError(
            f"Firecrawl: HTTP {status}", hints.get(status, "try another source")
        ) from error
    except httpx.TimeoutException as error:
        raise ResearchError("Firecrawl: timeout", "try another source") from error
    except (httpx.RequestError, ValueError) as error:
        raise ResearchError("Firecrawl: request or response failed") from error
    if not isinstance(result, dict) or result.get("success") is not True:
        raise ResearchError("Firecrawl: scrape failed", "try another source")
    data = result.get("data")
    if not isinstance(data, dict):
        raise ResearchError("Firecrawl: invalid response")
    metadata = data.get("metadata") or {}
    status = metadata.get("statusCode") if isinstance(metadata, dict) else None
    if isinstance(status, int) and status >= 400:
        raise ResearchError(f"Firecrawl: page HTTP {status}", "try another source")
    markdown = data.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        raise ResearchError("Firecrawl: empty markdown", "try another source")
    return markdown.strip()
