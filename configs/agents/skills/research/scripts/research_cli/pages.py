"""Direct HTTP page fetching, with HTML converted to compact markdown."""

import json
import re
from urllib.parse import urljoin, urlsplit

import httpx
from html_to_markdown import convert
from selectolax.lexbor import LexborHTMLParser

from . import config, github
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
    "[role=banner], [aria-hidden=true], a.headerlink, a.anchor, a.hash-link"
)
# Where pages state their publication date, most reliable first: (selector, attribute).
DATE_SOURCES = (
    ('meta[property="article:published_time"]', "content"),
    ('meta[name="date"]', "content"),
    ("time[datetime]", "datetime"),
    (".date, .published, .post-date, .entry-date", None),
)
# A short page that asks for JavaScript has not rendered its real content.
JS_NOTICE = re.compile(r"(?i)(requires?|enable|turn on|without) javascript")
JS_NOTICE_PAGE_CHARS = 5000


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
    final_urls: list[str] | None = None,
) -> tuple[str, str]:
    """Return (text, lowercase mime) for an HTTP(S) URL, enforcing size/text limits.

    The URL that answered, after redirects, is appended to `final_urls`.
    """
    validate_url(url)
    try:
        with open_client(client) as http:
            return download_response(http, url, accept, compress, final_urls)
    except httpx.HTTPStatusError as error:
        status = error.response.status_code
        if github.is_api_rate_limit(url, status):
            # A scraper cannot stand in for an API; its copy would not be the JSON.
            raise ResearchError(
                f"GitHub API: HTTP {status} (rate limit)",
                "set $GITHUB_TOKEN or run `gh auth login`, or fetch the "
                "github.com page instead",
                final=True,
            ) from error
        if status in (404, 410):
            raise ResearchError(
                f"raw fetch: HTTP {status}",
                github.missing_path_hint(url)
                or "not served now; fix the URL, find it with `web`, or try "
                "`fetch --exa` for an indexed copy",
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


def redirect_notice(requested: str, final: str) -> str:
    """A leading line for a page served from a different location than asked for."""

    def location(url: str) -> tuple[str, str]:
        parts = urlsplit(url)
        return (parts.hostname or "").removeprefix("www."), parts.path.rstrip("/")

    if location(requested) == location(final):
        return ""
    return f"[redirected to {final}; this may not be the page you asked for]\n\n"


def download_response(
    client: httpx.Client,
    url: str,
    accept: str,
    compress: bool,
    final_urls: list[str] | None = None,
) -> tuple[str, str]:
    with client.stream(
        "GET",
        url,
        headers={
            "User-Agent": "research-cli/2.0",
            "Accept": accept,
            **github.api_headers(url),
            "Accept-Encoding": "gzip, deflate" if compress else "identity",
        },
        timeout=request_timeout("exa"),
        follow_redirects=True,
    ) as response:
        response.raise_for_status()
        if final_urls is not None:
            final_urls.append(str(response.url))
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
                # An extraction service would only return a broken fragment of it.
                raise ResearchError(
                    "response exceeds 10 MiB",
                    "request a narrower URL: a versioned, filtered, or paginated "
                    "endpoint, or one file instead of an index",
                    final=True,
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


def page_heading(tree: LexborHTMLParser) -> tuple[str, str]:
    """(title, publication date) from the document, which often sit outside <main>."""
    node = tree.css_first("title")
    title = " ".join(node.text().split()) if node else ""
    published = ""
    for selector, attribute in DATE_SOURCES:
        node = tree.css_first(selector)
        value = (
            (node.attrs.get(attribute) if attribute else node.text()) if node else ""
        )
        if value and (match := re.search(r"\d{4}-\d{2}-\d{2}", value)):
            published = match.group()
            break
    return title, published


def main_content(body, base_url: str) -> str:
    """Markdown of the page's main region, falling back to wider ones if it is thin."""
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


def html_to_markdown(html: str, base_url: str) -> str:
    """Convert a page's main content to markdown without nav/scripts/images."""
    tree = LexborHTMLParser(html)
    if tree.body is None:
        return ""
    # Read before main_content, which strips headers out of the tree.
    title, published = page_heading(tree)
    result = main_content(tree.body, base_url)
    if len(result) < MIN_PAGE_CHARS:
        return result
    # Site names follow a separator in <title>; the page's own name comes first.
    name = re.split(r"\s+[|·–—]\s+", title)[0]
    lead = [f"# {title}"] if name and name.lower() not in result[:400].lower() else []
    if published and published not in result[:400]:
        lead.append(f"Published: {published}")
    return "\n\n".join([*lead, result])


def require_rendered(markdown: str) -> None:
    """Raise, so the caller falls back to a scraper, if the page did not render."""
    if len(markdown) < 1000 and "a required part of this site couldn't load" in (
        markdown.lower().replace("’", "'")
    ):
        raise ResearchError("page returned a loading error", "try a scraping fallback")
    if len(markdown) < JS_NOTICE_PAGE_CHARS and JS_NOTICE.search(markdown):
        raise ResearchError(
            "page says it needs JavaScript", "its content is rendered client-side"
        )
    if len(markdown) < MIN_PAGE_CHARS:
        raise ResearchError(
            f"page has little static content ({len(markdown)} chars after conversion)",
            "likely JS-rendered or blocked; use fetch --exa",
        )


def fetch_thread(api: str, client: httpx.Client | None) -> str:
    """A GitHub issue or pull request, with its comments, read through the API."""
    issue = json.loads(download(api, client=client, compress=True)[0])
    comments: list[dict] = []
    for page in range(1, github.COMMENT_PAGES + 1):
        url = github.comments_api_url(api, page)
        batch = json.loads(download(url, client=client, compress=True)[0])
        comments.extend(batch)
        if len(batch) < github.COMMENTS_PER_PAGE:
            break
    return github.render_thread(issue, comments)


def fetch_page(url: str, *, client: httpx.Client | None = None) -> str:
    """Fetch a URL; markdown/plain text passes through, HTML is converted."""
    if raw := github.raw_file_url(url):
        try:
            return download(raw, client=client, compress=True)[0]
        except ResearchError:
            pass  # e.g. a ref containing "/"; the page itself may still work
    if api := github.thread_api_url(url):
        try:
            return fetch_thread(api, client)
        except (ResearchError, ValueError, KeyError, TypeError, AttributeError):
            pass  # rate-limited or an unexpected shape; the page still has the text
    final_urls: list[str] = []
    text, mime = download(
        url, PAGE_ACCEPT, client=client, compress=True, final_urls=final_urls
    )
    if mime == "application/json" or mime.endswith("+json"):
        # Minified JSON is one line, which defeats --match and line-based reads.
        try:
            return json.dumps(json.loads(text), indent=2, ensure_ascii=False)
        except ValueError:
            return text
    if mime not in HTML_MIMES:
        return text
    markdown = html_to_markdown(text, url)
    require_rendered(markdown)
    return redirect_notice(url, final_urls[0] if final_urls else url) + markdown
