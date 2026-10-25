"""HTML to compact markdown: the main content, its title, and its publication date."""

import re
from urllib.parse import urljoin, urlsplit

from html_to_markdown import convert
from selectolax.lexbor import LexborHTMLParser, LexborNode

from .dates import iso_timestamp
from .errors import ResearchError

# Below this the page is likely JS-rendered or blocked; callers try other sources.
MIN_PAGE_CHARS = 200
# The lead of the converted text, where a page usually states its title and date.
LEAD_CHARS = 400
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
LOADING_ERROR = "a required part of this site couldn't load"
LOADING_ERROR_PAGE_CHARS = 1000
CHALLENGE_HEADING = re.compile(
    r"(?i)^#\s+(?:just a moment(?:\.{3}|…)?|"
    r"attention required!?\s*[|·]\s*cloudflare|client challenge|"
    r"(?:reddit\s*[-–—]\s*)?prove your humanity)\s*$"
)
LOGIN_PATH = re.compile(r"(?i)/(?:log-?in|sign-?in|auth(?:enticate)?|sso)(?:/|$)")


def page_metadata(tree: LexborHTMLParser) -> tuple[str, list[str]]:
    """(title, publication dates) from the document, which often sit outside <main>.

    Several dates mean a feed or thread that dates every post; the first may not
    be the page's own.
    """
    node = tree.css_first("title")
    title = " ".join(node.text().split()) if node else ""
    for selector, attribute in DATE_SOURCES:
        stamps = [
            iso_timestamp(node.attrs.get(attribute) if attribute else node.text())
            for node in tree.css(selector)
        ]
        if published := list(dict.fromkeys(filter(None, stamps))):
            return title, published
    return title, []


def main_content(body: LexborNode, base_url: str) -> str:
    """Markdown of the page's main region, widening the region while it is thin."""
    articles = body.css("article")
    candidates = [body.css_first("main, [role=main]")]
    if len(articles) == 1:
        candidates.append(articles[0])
    candidates.append(body)
    result = ""
    for root in filter(None, candidates):
        for node in root.css(NOISE):
            node.decompose()
        if root is body:  # a <header> inside main or article often holds the title
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
    """The page's main content as markdown, led by its title and date when missing."""
    tree = LexborHTMLParser(html)
    if tree.body is None:
        return ""
    # Read before main_content, which strips headers out of the tree.
    title, published = page_metadata(tree)
    result = main_content(tree.body, base_url)
    if len(result) < MIN_PAGE_CHARS:
        return result
    lead = result[:LEAD_CHARS].lower()
    # Site names follow a separator in <title>; the page's own name comes first.
    name = re.split(r"\s+[|·–—]\s+", title)[0]
    header = [f"# {title}"] if name and name.lower() not in lead else []
    if published and published[0].lower() not in lead:
        count = len(published)
        note = f" (first of {count} timestamps on the page)" if count > 1 else ""
        header.append(f"Published: {published[0]}{note}")
    return "\n\n".join([*header, result])


def require_rendered(markdown: str) -> None:
    """Raise, so the caller tries another source, if the page did not render."""
    first_line = markdown.lstrip().split("\n", 1)[0].strip()
    if CHALLENGE_HEADING.fullmatch(first_line):
        raise ResearchError("page returned a bot challenge", "try a scraping fallback")
    normalized = markdown.lower().replace("’", "'")
    if len(markdown) < LOADING_ERROR_PAGE_CHARS and LOADING_ERROR in normalized:
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


def require_public(requested: str, final: str) -> None:
    """Raise if the request was redirected to a sign-in page instead of content."""
    if LOGIN_PATH.search(urlsplit(final).path) and not LOGIN_PATH.search(
        urlsplit(requested).path
    ):
        raise ResearchError(
            f"redirected to a sign-in page ({final})",
            "the content needs an account; an indexed copy may still exist",
        )
