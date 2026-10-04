"""JSON-RPC calls to the hosted MCP services (Context7, Exa, DeepWiki, grep.app)."""

import json
import time

import httpx

from .config import ENDPOINTS, ResearchError
from .credentials import api_key
from .network import open_client, request_timeout


def auth_headers(service: str) -> dict[str, str]:
    if service == "exa":
        key = api_key("EXA_API_KEY", "exa-api-key")
        return {"x-api-key": key} if key else {}
    if service == "c7":
        key = api_key("CONTEXT7_API_KEY", "context7-api-key")
        return {"CONTEXT7_API_KEY": key} if key else {}
    return {}


def parse_tool_response(body: str, tool: str) -> str:
    if body.lstrip().startswith("{"):
        messages = [body]
    else:
        messages = [
            line[5:].strip() for line in body.splitlines() if line.startswith("data:")
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


def request_tool(
    service: str, tool: str, arguments: dict, *, client: httpx.Client | None = None
) -> str:
    with open_client(client) as http:
        return call_tool(http, service, tool, arguments)


def same_origin_response(
    client: httpx.Client, response: httpx.Response, tool: str
) -> httpx.Response:
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
        raise httpx.TooManyRedirects("too many MCP redirects", request=response.request)
    return response


def call_tool(client: httpx.Client, service: str, tool: str, arguments: dict) -> str:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "research-cli/2.0",
        **auth_headers(service),
    }
    for attempt in range(3):
        try:
            response = client.post(
                ENDPOINTS[service],
                json=payload,
                headers=headers,
                timeout=request_timeout(service),
                follow_redirects=False,
            )
            response = same_origin_response(client, response, tool)
            response.raise_for_status()
            return parse_tool_response(response.text, tool)
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            detail = error.response.text[:200].replace("\n", " ")
            if status in (429, 500, 502, 503, 504) and attempt < 2:
                retry_after = error.response.headers.get("Retry-After", "")
                delay = (
                    float(retry_after) if retry_after.isdigit() else 2**attempt * 1.5
                )
                time.sleep(min(delay, 10))
                continue
            hints = {
                401: "key rejected; check ~/.secrets or $EXA_API_KEY/$CONTEXT7_API_KEY",
                403: "blocked; retry later or try another tool",
                429: "rate limited"
                + (
                    ""
                    if auth_headers(service) or service in ("dw", "grep")
                    else " (no API key loaded; keys lift limits)"
                ),
            }
            raise ResearchError(
                f"{tool}: HTTP {status} {detail}", hints.get(status, "")
            ) from error
        except httpx.TimeoutException as error:
            raise ResearchError(
                f"{tool}: timeout", "try a narrower query or another source"
            ) from error
        except (httpx.RequestError, httpx.InvalidURL, OSError) as error:
            if attempt < 2:
                time.sleep(1.5)
                continue
            raise ResearchError(f"{tool}: {error}", "network/timeout; retry") from error
    raise ResearchError(f"{tool}: failed")
