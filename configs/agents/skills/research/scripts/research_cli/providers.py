"""REST search providers, each returning a JSON list of {title, url, date, text}."""

import html
import json
import re
import threading
import time
from datetime import date
from email.utils import parsedate_to_datetime

import httpx

from .config import ResearchError
from .credentials import api_key
from .network import open_client, request_timeout

# name: (environment variable, ~/.secrets filename)
KEYS = {
    "parallel": ("PARALLEL_API_KEY", "parallel-api-key"),
    "brave": ("BRAVE_API_KEY", "brave-api-key"),
    "tavily": ("TAVILY_API_KEY", "tavily-api-key"),
}
# Brave's free plan allows one request per second.
BRAVE_INTERVAL_SECONDS = 1.1
BRAVE_ATTEMPTS = 3


class Throttle:
    """Spaces calls from concurrent threads at least `interval` seconds apart."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.last = 0.0

    def wait(self, interval: float) -> None:
        with self.lock:
            delay = self.last + interval - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self.last = time.monotonic()


brave_throttle = Throttle()


def provider_key(name: str) -> str | None:
    return api_key(*KEYS[name])


def request_json(
    name: str, method: str, url: str, *, client: httpx.Client | None = None, **options
) -> dict:
    variable, filename = KEYS[name]
    key_hint = f"check ${variable} or ~/.secrets/{filename}"
    try:
        with open_client(client) as http:
            response = http.request(
                method,
                url,
                timeout=request_timeout(name),
                follow_redirects=False,
                **options,
            )
        response.raise_for_status()
        result = response.json()
    except httpx.HTTPStatusError as error:
        status = error.response.status_code
        hints = {
            401: key_hint,
            403: key_hint,
            402: "credits exhausted; use another --backend",
            429: "rate limited; use another --backend",
            432: "plan limit reached; use another --backend",
        }
        # The hint already explains known statuses; their bodies are only noise.
        detail = "" if status in hints else error.response.text[:160].replace("\n", " ")
        raise ResearchError(
            f"{name}: HTTP {status} {detail}".strip(),
            hints.get(status, "use another --backend"),
            status=status,
        ) from error
    except httpx.TimeoutException as error:
        raise ResearchError(f"{name}: timeout", "use another --backend") from error
    except (httpx.RequestError, ValueError) as error:
        raise ResearchError(f"{name}: request or response failed: {error}") from error
    if not isinstance(result, dict):
        raise ResearchError(f"{name}: invalid response")
    return result


def iso_date(value: object) -> str:
    """YYYY-MM-DD from an ISO or RFC 2822 timestamp, or "" when unrecognised."""
    text = str(value or "").strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", text):
        return text[:10]
    try:
        return parsedate_to_datetime(text).date().isoformat()
    except (TypeError, ValueError):
        return ""


def result(title: object, url: object, published: object, text: object) -> dict:
    return {
        "title": html.unescape(str(title or "")).strip(),
        "url": str(url or "").strip(),
        "date": iso_date(published),
        "text": html.unescape(str(text or "")).strip(),
    }


def search_parallel(arguments: dict, *, client: httpx.Client | None = None) -> str:
    settings: dict = {
        "max_results": arguments["n"],
        "excerpt_settings": {"max_chars_per_result": arguments["chars"]},
    }
    policy = {
        name: arguments[source]
        for name, source in (
            ("include_domains", "domains"),
            ("exclude_domains", "exclude"),
            ("after_date", "after"),
        )
        if arguments.get(source)
    }
    if policy:
        settings["source_policy"] = policy
    response = request_json(
        "parallel",
        "POST",
        "https://api.parallel.ai/v1/search",
        client=client,
        headers={"x-api-key": provider_key("parallel") or ""},
        json={
            "objective": arguments.get("objective") or arguments["queries"][0],
            "search_queries": arguments["queries"],
            "mode": "fast",
            "advanced_settings": settings,
        },
    )
    return json.dumps(
        [
            result(
                item.get("title"),
                item.get("url"),
                item.get("publish_date"),
                "\n...\n".join(item.get("excerpts") or []),
            )
            for item in response.get("results") or []
            if isinstance(item, dict)
        ]
    )


def search_brave(arguments: dict, *, client: httpx.Client | None = None) -> str:
    query = arguments["queries"][0]
    if domains := arguments.get("domains"):
        sites = " OR ".join(f"site:{domain}" for domain in domains)
        query = f"({sites}) {query}" if len(domains) > 1 else f"{sites} {query}"
    for domain in arguments.get("exclude") or []:
        query += f" -site:{domain}"
    parameters = {
        "q": query,
        "count": min(arguments["n"], 20),
        "text_decorations": "false",
        "result_filter": "web",
        "extra_snippets": "true",
    }
    if arguments.get("after") or arguments.get("before"):
        start = arguments.get("after") or "1990-01-01"
        end = arguments.get("before") or date.today().isoformat()
        parameters["freshness"] = f"{start}to{end}"

    def send() -> dict:
        # Concurrent queries would otherwise trip the per-second limit.
        brave_throttle.wait(BRAVE_INTERVAL_SECONDS)
        return request_json(
            "brave",
            "GET",
            "https://api.search.brave.com/res/v1/web/search",
            client=client,
            headers={
                "X-Subscription-Token": provider_key("brave") or "",
                "Accept": "application/json",
            },
            params=parameters,
        )

    response = None
    for _ in range(BRAVE_ATTEMPTS - 1):
        try:
            response = send()
            break
        except ResearchError as error:
            # Another process may share the key's one-request-per-second allowance.
            if error.status != 429:
                raise
    web = (response or send()).get("web") or {}
    return json.dumps(
        [
            result(
                item.get("title"),
                item.get("url"),
                item.get("page_age"),
                "\n...\n".join(
                    [item.get("description") or "", *(item.get("extra_snippets") or [])]
                ),
            )
            for item in web.get("results") or []
            if isinstance(item, dict)
        ]
    )


def search_tavily(arguments: dict, *, client: httpx.Client | None = None) -> str:
    payload = {
        "query": arguments["queries"][0],
        "max_results": min(arguments["n"], 20),
        "include_published_date": True,
    }
    for name, source in (
        ("include_domains", "domains"),
        ("exclude_domains", "exclude"),
        ("start_date", "after"),
        ("end_date", "before"),
    ):
        if arguments.get(source):
            payload[name] = arguments[source]
    response = request_json(
        "tavily",
        "POST",
        "https://api.tavily.com/search",
        client=client,
        headers={"Authorization": f"Bearer {provider_key('tavily') or ''}"},
        json=payload,
    )
    return json.dumps(
        [
            result(
                item.get("title"),
                item.get("url"),
                item.get("published_date"),
                item.get("content"),
            )
            for item in response.get("results") or []
            if isinstance(item, dict)
        ]
    )


SEARCHERS = {
    "parallel": search_parallel,
    "brave": search_brave,
    "tavily": search_tavily,
}
