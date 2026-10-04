"""Direct HTTP page fetching, with HTML converted to compact markdown."""

import json
from urllib.parse import urljoin, urlsplit

import httpx
from html_to_markdown import convert
from selectolax.lexbor import LexborHTMLParser

from . import config
from .config import ResearchError
from .network import open_client, request_timeout

HTML_MIMES = ("text/html", "application/xhtml+xml")
TEXT_MIMES = (
    "application/json",
    "application/xml",
    "application/javascript",
    "application/yaml",
    "application/x-yaml",
    "application/toml",
    "application/octet-stream",
)
# Servers that support markdown negotiation (e.g. Cloudflare) return it directly.
PAGE_ACCEPT = "text/markdown, text/html;q=0.9, text/plain;q=0.8, */*;q=0.5"
# Below this the page is likely JS-rendered or blocked; callers use scraping fallbacks.
MIN_PAGE_CHARS = 200
NOISE = (
    "script, style, noscript, template, svg, canvas, iframe, form, button, "
    "img, picture, video, audio, nav, aside, footer, [role=navigation], "
    "[role=banner], [aria-hidden=true]"
)


def validate_url(url: str) -> None:
    try:
        parts = urlsplit(url)
        if (
            parts.scheme not in ("http", "https")
            or not parts.hostname
            or parts.username
            or parts.password
        ):
            raise ValueError
    except ValueError as error:
        raise ResearchError(
            "fetch requires an HTTP(S) URL without credentials", final=True
        ) from error


def download(
    url: str,
    accept: str = "*/*",
    *,
    client: httpx.Client | None = None,
    compress: bool = False,
) -> tuple[str, str]:
    """Return (text, lowercase mime) for an HTTP(S) URL, enforcing size/text limits."""
    validate_url(url)
    try:
        with open_client(client) as http:
            return download_response(http, url, accept, compress)
    except httpx.HTTPStatusError as error:
        status = error.response.status_code
        if status in (404, 410):
            raise ResearchError(
                f"raw fetch: HTTP {status}",
                "page does not exist; fix the URL or find it with `web`",
                final=True,
            ) from error
        raise ResearchError(
            f"raw fetch: HTTP {status}", "check the URL or try fetch --exa"
        ) from error
    except (UnicodeError, LookupError) as error:
        raise ResearchError(
            "raw response could not be decoded as text", "use fetch --exa"
        ) from error
    except (httpx.RequestError, httpx.InvalidURL, OSError, ValueError) as error:
        raise ResearchError(
            f"raw fetch: {error}", "check the URL and network, then retry"
        ) from error


def download_response(
    client: httpx.Client, url: str, accept: str, compress: bool
) -> tuple[str, str]:
    with client.stream(
        "GET",
        url,
        headers={
            "User-Agent": "research-cli/2.0",
            "Accept": accept,
            "Accept-Encoding": "gzip, deflate" if compress else "identity",
        },
        timeout=request_timeout("exa"),
        follow_redirects=True,
    ) as response:
        response.raise_for_status()
        mime = (
            response.headers.get("Content-Type", "text/plain")
            .split(";", 1)[0]
            .strip()
            .lower()
        )
        if not (
            mime.startswith("text/")
            or mime.endswith(("+json", "+xml"))
            or mime in TEXT_MIMES
            or mime in HTML_MIMES
        ):
            raise ResearchError(
                f"raw fetch expected text, got {mime}",
                "use fetch --exa for page extraction",
            )
        body = bytearray()
        for chunk in response.iter_bytes(chunk_size=64 * 1024):
            if len(body) + len(chunk) > config.MAX_RAW_BYTES:
                raise ResearchError(
                    "raw response exceeds 10 MiB",
                    "fetch a smaller source file or use fetch --exa",
                )
            body.extend(chunk)
        text = body.decode(response.charset_encoding or "utf-8")
        if "\x00" in text:
            raise ResearchError(
                "raw response contains binary data",
                "use a text source or fetch --exa",
            )
        return text, mime


def fetch_raw(url: str, *, client: httpx.Client | None = None) -> str:
    return download(url, client=client)[0]


def html_to_markdown(html: str, base_url: str) -> str:
    """Convert a page's main content to markdown without nav/scripts/images."""
    tree = LexborHTMLParser(html)
    body = tree.body
    if body is None:
        return ""
    articles = body.css("article")
    candidates = [body.css_first("main, [role=main]")]
    if len(articles) == 1:
        candidates.append(articles[0])
    candidates.append(body)
    result = ""
    for root in filter(None, candidates):
        for node in root.css(NOISE):
            node.decompose()
        if root is body:  # <header> inside main/article often holds the title
            for node in root.css("header"):
                node.decompose()
        for link in root.css("a[href]"):
            href = link.attrs["href"]
            if href is not None and not href.startswith("#"):
                link.attrs["href"] = urljoin(base_url, href)
        result = str(convert(root.html or "").content).strip()
        if len(result) >= MIN_PAGE_CHARS:
            break
    return result


def fetch_page(url: str, *, client: httpx.Client | None = None) -> str:
    """Fetch a URL; markdown/plain text passes through, HTML is converted."""
    text, mime = download(url, PAGE_ACCEPT, client=client, compress=True)
    if mime == "application/json" or mime.endswith("+json"):
        # Minified JSON is one line, which defeats --match and line-based reads.
        try:
            return json.dumps(json.loads(text), indent=2, ensure_ascii=False)
        except ValueError:
            return text
    if mime not in HTML_MIMES:
        return text
    markdown = html_to_markdown(text, url)
    if len(markdown) < 1000 and "a required part of this site couldn't load" in (
        markdown.lower().replace("’", "'")
    ):
        raise ResearchError("page returned a loading error", "try a scraping fallback")
    if len(markdown) < MIN_PAGE_CHARS:
        raise ResearchError(
            f"page has little static content ({len(markdown)} chars after conversion)",
            "likely JS-rendered or blocked; use fetch --exa",
        )
    return markdown
