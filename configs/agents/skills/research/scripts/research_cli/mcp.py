"""JSON-RPC tool calls to hosted MCP servers: Exa, Context7, DeepWiki, and grep.app."""

import json
from dataclasses import dataclass
from time import sleep
from typing import Any

import httpx2

from . import config
from .credentials import KEYS, api_key
from .errors import ResearchError
from .transport import Http, response_detail, root_message, timeout


@dataclass(frozen=True)
class Server:
    url: str
    key_header: str | None = None  # the header that carries an optional API key


SERVERS = {
    "exa": Server(
        "https://mcp.exa.ai/mcp?tools=web_search_exa,web_search_advanced_exa,"
        "web_fetch_exa,get_code_context_exa",
        "x-api-key",
    ),
    "context7": Server("https://mcp.context7.com/mcp", "CONTEXT7_API_KEY"),
    "deepwiki": Server("https://mcp.deepwiki.com/mcp"),
    "grep": Server("https://mcp.grep.app"),
}
ATTEMPTS = 3
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_RETRY_SECONDS = 10.0
NETWORK_RETRY_SECONDS = 1.5


def auth_headers(service: str) -> dict[str, str]:
    header = SERVERS[service].key_header
    key = api_key(service) if header else None
    return {header: key} if header and key else {}


def parse_tool_response(body: str, tool: str) -> str:
    """The text of a tool result, from a JSON or server-sent-events response."""
    if body.lstrip().startswith("{"):
        messages = [body]
    else:
        messages = [
            line.removeprefix("data:").strip()
            for line in body.splitlines()
            if line.startswith("data:")
        ]
    for message in messages:
        try:
            response = json.loads(message)
        except ValueError:
            continue
        if not isinstance(response, dict) or response.get("id") != 1:
            continue
        if "error" in response:
            error = response["error"]
            detail = error.get("message") if isinstance(error, dict) else error
            raise ResearchError(f"{tool}: {detail}")
        result = response.get("result")
        if not isinstance(result, dict) or not isinstance(
            result.get("content", []), list
        ):
            raise ResearchError(
                f"{tool}: invalid result", "retry or use another research source"
            )
        text = "\n".join(
            block["text"]
            for block in result.get("content", [])
            if isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ).strip()
        if result.get("isError"):
            raise ResearchError(f"{tool}: {text[:300]}")
        if not text:
            raise ResearchError(f"{tool}: empty result", "try a different query")
        return text
    raise ResearchError(f"{tool}: no response")


def follow_same_origin(
    client: httpx2.Client, response: httpx2.Response, tool: str
) -> httpx2.Response:
    """Follow redirects that stay on the server, which keep the API key private."""
    origin = response.request.url
    for _ in range(client.max_redirects):
        request = response.next_request
        if request is None:
            return response
        target = request.url
        if (target.scheme, target.host, target.port) != (
            origin.scheme,
            origin.host,
            origin.port,
        ):
            raise ResearchError(
                f"{tool}: cross-origin redirect refused",
                "use the service's canonical MCP endpoint or another research source",
            )
        response = client.send(request, follow_redirects=False)
    if response.next_request is not None:
        raise ResearchError(f"{tool}: too many redirects")
    return response


def retry_delay(response: httpx2.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After", "")
    delay = float(retry_after) if retry_after.isdigit() else 1.5 * 2**attempt
    return min(delay, MAX_RETRY_SECONDS)


def status_hint(service: str, status: int) -> str:
    keyed = SERVERS[service].key_header is not None
    if status == 401 and keyed:
        return f"key rejected; check {KEYS[service].locations}"
    if status == 403:
        return "blocked; retry later or try another source"
    if status == 429:
        unkeyed = keyed and not auth_headers(service)
        return "rate limited" + (
            " (no API key loaded; keys lift limits)" if unkeyed else ""
        )
    return ""


def call_tool(http: Http, service: str, tool: str, arguments: dict[str, Any]) -> str:
    """Call one MCP tool, retrying rate limits, server errors, and network failures."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": config.USER_AGENT,
        **auth_headers(service),
    }
    for attempt in range(ATTEMPTS):
        final_attempt = attempt == ATTEMPTS - 1
        try:
            response = http.api.post(
                SERVERS[service].url,
                json=payload,
                headers=headers,
                timeout=timeout(service),
                follow_redirects=False,
            )
            response = follow_same_origin(http.api, response, tool)
        except httpx2.TimeoutException as error:
            # The service may still be working; asking again doubles the wait.
            raise ResearchError(
                f"{tool}: timeout", "try a narrower query or another source"
            ) from error
        except httpx2.TransportError as error:
            if not final_attempt:
                sleep(NETWORK_RETRY_SECONDS)
                continue
            raise ResearchError(
                f"{tool}: {root_message(error)}", "network error; retry"
            ) from error
        except (httpx2.HTTPError, httpx2.InvalidURL) as error:
            raise ResearchError(f"{tool}: {root_message(error)}") from error
        if response.is_success:
            return parse_tool_response(response.text, tool)
        status = response.status_code
        if status in RETRY_STATUSES and not final_attempt:
            sleep(retry_delay(response, attempt))
            continue
        raise ResearchError(
            f"{tool}: HTTP {status} {response_detail(response)}".rstrip(),
            status_hint(service, status),
            status=status,
        )
    raise AssertionError("every attempt returns or raises")
