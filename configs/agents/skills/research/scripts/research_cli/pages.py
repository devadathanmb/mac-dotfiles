"""Reading a URL directly: a site's API when it has a better copy, else the page."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from . import github, health, stackexchange
from .errors import ResearchError
from .extract import html_to_markdown, require_public, require_rendered
from .transport import GONE_STATUSES, Download, Http

HTML_MIMES = frozenset({"text/html", "application/xhtml+xml"})
# Servers that support markdown negotiation (e.g. Cloudflare) return it directly.
PAGE_ACCEPT = "text/markdown, text/html;q=0.9, text/plain;q=0.8, */*;q=0.5"
DIRECT = "direct HTTP, markdown"
# Languages where a line starting `# ` is a comment, not a markdown heading.
HASH_COMMENT_SUFFIXES = frozenset(
    {
        ".py",
        ".pyi",
        ".sh",
        ".bash",
        ".zsh",
        ".fish",
        ".rb",
        ".pl",
        ".r",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".tf",
        ".nix",
        ".cmake",
        ".ps1",
        ".jl",
        ".ex",
        ".exs",
        ".cr",
        ".nim",
        ".coffee",
    }
)
HASH_COMMENT_NAMES = frozenset({"dockerfile", "makefile", "gemfile", "rakefile"})
GONE_HINT = (
    "not served now; fix the URL, find it with `web`, "
    "or try `fetch --exa` for an indexed copy"
)


@dataclass(frozen=True)
class Page:
    text: str
    source: str  # the API or method that produced `text`


def validate_url(url: str) -> None:
    try:
        parts = urlsplit(url)
        valid = (
            parts.scheme in ("http", "https")
            and bool(parts.hostname)
            and not parts.username
            and not parts.password
        )
    except ValueError:
        valid = False
    if not valid:
        raise ResearchError(
            "fetch requires an HTTP(S) URL without credentials", final=True
        )


def download(http: Http, url: str, accept: str = "*/*") -> Download:
    """GET `url`, with errors that say how to find what the URL should have been."""
    validate_url(url)
    api = urlsplit(url).hostname == github.API_HOST
    try:
        return http.download(
            url, accept=accept, headers=github.api_headers(url), impersonate=not api
        )
    except ResearchError as error:
        if github.is_api_rate_limit(url, error.status):
            raise github.rate_limit_error(error.status) from error
        if error.status in GONE_STATUSES:
            hint = github.missing_path_hint(url) or GONE_HINT
            raise ResearchError(
                error.message, hint, final=True, status=error.status
            ) from error
        if error.status is not None and not error.hint:
            raise ResearchError(
                error.message, "check the URL or try fetch --exa", status=error.status
            ) from error
        raise


def fetch_raw(http: Http, url: str) -> str:
    return download(http, url).text()


def has_markdown_headings(url: str) -> bool:
    """False for source files whose `#` lines are comments, judged by file name."""
    name = PurePosixPath(urlsplit(url).path).name.lower()
    suffix = PurePosixPath(name).suffix
    return suffix not in HASH_COMMENT_SUFFIXES and name not in HASH_COMMENT_NAMES


def redirect_notice(requested: str, final: str) -> str:
    """A leading line for a page served from a different location than asked for."""

    def location(url: str) -> tuple[str, str]:
        parts = urlsplit(url)
        return (parts.hostname or "").removeprefix("www."), parts.path.rstrip("/")

    if location(requested) == location(final):
        return ""
    return f"[redirected to {final}; this may not be the page you asked for]\n\n"


def from_repo_file(http: Http, file: github.RepoFile, notices: list[str]) -> Page:
    """A GitHub file's text from the first of its hosts that serves it.

    Raw content is cheapest, but some networks stall its handshakes, so the
    contents API and the `blob` page (on hosts that stay reachable) stand in; a
    host that stalled recently goes last. Only the page resolves a ref that
    contains "/", so a 404 from the others skips straight to it.
    """
    page_route = "GitHub file page"
    routes: list[tuple[str, Callable[[], str]]] = [
        ("GitHub raw file", lambda: fetch_raw(http, file.raw_url))
    ]
    if contents := file.contents_url():
        routes.append(
            (
                "GitHub contents API",
                lambda: download(http, contents, github.RAW_ACCEPT).text(),
            )
        )
    routes.append(
        (page_route, lambda: github.file_from_page(fetch_html(http, file.page_url)))
    )
    if health.stalled_recently(github.RAW_HOST):
        routes.append(routes.pop(0))
    gone = False
    failure: ResearchError | None = None
    for name, read in routes:
        if gone and name != page_route:
            continue
        try:
            return Page(read(), name)
        except ResearchError as error:
            if error.final and name == page_route:
                raise
            gone = gone or error.status in GONE_STATUSES
            failure = error
            notices.append(f"[{name} unavailable: {error}]")
    assert failure is not None
    raise ResearchError(
        f"no GitHub host served the file; last: {failure.message}",
        failure.hint or "try fetch --exa",
        final=failure.final,
        status=failure.status,
    )


def fetch_html(http: Http, url: str) -> str:
    page = download(http, url, "text/html")
    if page.mime not in HTML_MIMES:
        raise ResearchError(f"expected an HTML page, got {page.mime}")
    return page.text()


def from_site_api(http: Http, url: str, notices: list[str]) -> Page | None:
    """The page's source from the site's API, or None to read the page itself."""
    if (file := github.repo_file(url)) is not None:
        return from_repo_file(http, file, notices)
    if api := github.thread_api_url(url):
        try:
            return Page(github.fetch_thread(http, api), "GitHub API")
        except ResearchError as error:
            notices.append(f"[GitHub API unavailable: {error}; reading the page]")
    try:
        if (question := stackexchange.fetch_question(http, url)) is not None:
            return Page(question, "Stack Exchange API")
    except ResearchError as error:
        notices.append(f"[{error}; reading the page]")
    return None


def fetch_page(http: Http, url: str, notices: list[str]) -> Page:
    """The URL as markdown; markdown and plain text pass through, HTML is converted.

    Raises when the page did not render (a bot challenge, a JS shell, a sign-in
    redirect), so the caller can try an extraction service.
    """
    validate_url(url)
    if (found := from_site_api(http, url, notices)) is not None:
        return found
    page = download(http, url, PAGE_ACCEPT)
    text = page.text()
    if page.mime == "application/json" or page.mime.endswith("+json"):
        # Minified JSON is one line, which defeats --match and line-based reads.
        try:
            return Page(
                json.dumps(json.loads(text), indent=2, ensure_ascii=False), DIRECT
            )
        except ValueError:
            return Page(text, DIRECT)
    if page.mime not in HTML_MIMES:
        return Page(text, DIRECT)
    require_public(url, page.url)
    markdown = html_to_markdown(text, page.url)
    require_rendered(markdown)
    return Page(redirect_notice(url, page.url) + markdown, DIRECT)
