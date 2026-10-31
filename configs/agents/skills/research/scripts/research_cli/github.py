"""GitHub pages read through their source: files, and issues or PRs via the API.

A `blob` page renders the file with JS, and an issue page hides years,
collapses long threads, and buries whether a pull request merged.
"""

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlsplit

from selectolax.lexbor import LexborHTMLParser

from .credentials import github_token
from .errors import ResearchError
from .excerpts import demote_headings
from .transport import Http

API_HOST = "api.github.com"
RAW_HOST = "raw.githubusercontent.com"
# github.com/<owner>/<repo>/blob/<ref>/<path>: the page renders the file with JS.
BLOB = re.compile(r"https?://github\.com/([^/]+/[^/]+)/blob/([^?#]+)")
# raw.githubusercontent.com/<owner>/<repo>/<ref>/<path>, the ref possibly in refs/.
RAW_FILE = re.compile(r"https://raw\.githubusercontent\.com/([^/]+/[^/]+)/([^?#]+)")
# refs/heads/<branch> and refs/tags/<tag> spell a ref in three segments.
FULL_REF = re.compile(r"refs/(?:heads|tags)/[^/]+")
THREAD = re.compile(r"https?://github\.com/([^/]+/[^/]+)/(?:issues|pull)/(\d+)/?")
COMMENTS_PER_PAGE = 100
COMMENT_PAGES = 3
MAINTAINER_ROLES = ("OWNER", "MEMBER", "COLLABORATOR")
API_ACCEPT = "application/vnd.github+json"
RAW_ACCEPT = "application/vnd.github.raw"
PAGE_DATA = 'script[type="application/json"][data-target="react-app.embeddedData"]'


@dataclass(frozen=True)
class RepoFile:
    """A file in a repository, which three hosts serve."""

    repo: str  # owner/name
    location: str  # <ref>/<path>; a ref may itself contain "/"

    @property
    def raw_url(self) -> str:
        return f"https://{RAW_HOST}/{self.repo}/{self.location}"

    @property
    def page_url(self) -> str:
        return f"https://github.com/{self.repo}/blob/{self.location}"

    def contents_url(self) -> str | None:
        """The contents API URL, guessing where the ref ends; None without a path.

        A wrong guess (a branch named `release/1.0`) answers 404, as raw does.
        """
        full = FULL_REF.match(self.location)
        ref, _, path = (
            (full.group(), "/", self.location[full.end() + 1 :])
            if full
            else self.location.partition("/")
        )
        if not path:
            return None
        return (
            f"https://{API_HOST}/repos/{self.repo}/contents/{path}"
            f"?ref={quote(ref, safe='')}"
        )


def repo_file(url: str) -> RepoFile | None:
    """The file a `blob` page or raw-content URL names, or None for other URLs."""
    match = BLOB.fullmatch(url) or RAW_FILE.fullmatch(url)
    return RepoFile(match.group(1), match.group(2)) if match else None


def find_raw_lines(data: Any) -> list[str] | None:
    if isinstance(data, dict):
        if isinstance(lines := data.get("rawLines"), list):
            return [str(line) for line in lines]
        children = data.values()
    elif isinstance(data, list):
        children = data
    else:
        return None
    for child in children:
        if (lines := find_raw_lines(child)) is not None:
            return lines
    return None


def file_from_page(html: str) -> str:
    """The file's text from a `blob` page, which embeds it as JSON for its script.

    Converting the page instead keeps only its headings and file metadata.
    """
    node = LexborHTMLParser(html).css_first(PAGE_DATA)
    try:
        lines = find_raw_lines(json.loads(node.text())) if node else None
    except ValueError:
        lines = None
    if lines is None:
        raise ResearchError(
            "GitHub page did not embed the file's text",
            "the file may be binary or too large to display; try fetch --exa",
        )
    return "\n".join(lines) + "\n" if lines else ""


def api_headers(url: str) -> dict[str, str]:
    """Authorization for api.github.com only; the token is never sent elsewhere."""
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != API_HOST:
        return {}
    token = github_token()
    return {"Authorization": f"Bearer {token}"} if token else {}


def is_api_rate_limit(url: str, status: int | None) -> bool:
    return urlsplit(url).hostname == API_HOST and status in (403, 429)


def rate_limit_error(status: int | None) -> ResearchError:
    # A scraper cannot stand in for an API; its copy would not be the JSON.
    return ResearchError(
        f"GitHub API: HTTP {status} (rate limit)",
        "set $GITHUB_TOKEN or run `gh auth login`, "
        "or fetch the github.com page instead",
        final=True,
        status=status,
    )


def missing_path_hint(url: str) -> str:
    """How to locate a file whose guessed repository path does not exist."""
    match = BLOB.match(url) or RAW_FILE.match(url)
    if not match:
        return ""
    repo, (ref, _, path) = match.group(1), match.group(2).partition("/")
    folder = path.rpartition("/")[0]
    return (
        f"no such path at {ref}; list the directory with `fetch "
        f"'https://{API_HOST}/repos/{repo}/contents/{folder}?ref={ref}'` "
        f'or find the file with `code "<symbol>" --repo {repo}`'
    )


def thread_api_url(url: str) -> str | None:
    """The API URL for an issue or pull-request page, or None for any other URL."""
    thread = THREAD.fullmatch(url)
    if not thread:
        return None
    return f"https://{API_HOST}/repos/{thread.group(1)}/issues/{thread.group(2)}"


def comments_api_url(thread_url: str, page: int) -> str:
    return f"{thread_url}/comments?per_page={COMMENTS_PER_PAGE}&page={page}"


def author(item: dict[str, Any]) -> str:
    """Login plus the repository role that marks a maintainer's statement."""
    login = (item.get("user") or {}).get("login", "unknown")
    role = item.get("author_association", "")
    return f"{login} ({role.lower()})" if role in MAINTAINER_ROLES else login


def thread_state(issue: dict[str, Any]) -> str:
    state = issue.get("state", "")
    pull = issue.get("pull_request")
    if pull and state == "closed":
        merged = (pull.get("merged_at") or "")[:10]
        return f"merged {merged}" if merged else "closed without merging"
    if state == "closed" and issue.get("state_reason"):
        return f"closed as {issue['state_reason'].replace('_', ' ')}"
    return state


def render_thread(issue: dict[str, Any], comments: list[dict[str, Any]]) -> str:
    """An issue or pull request as markdown: state, dates, body, and comments.

    The HTML page hides the year of dates, collapses long threads, and buries
    whether a pull request merged; the API states all three.
    """
    pull = issue.get("pull_request")
    repo = issue.get("repository_url", "").partition("/repos/")[2]
    kind = "Pull request" if pull else "Issue"
    facts = [
        f"{kind} #{issue.get('number')} in {repo}: {thread_state(issue)}",
        f"opened {issue.get('created_at', '')[:10]} by {author(issue)}",
    ]
    if issue.get("closed_at"):
        facts.append(f"closed {issue['closed_at'][:10]}")
    if labels := ", ".join(label["name"] for label in issue.get("labels") or []):
        facts.append(f"labels: {labels}")
    heading = f"## Comments ({len(comments)} of {issue.get('comments', len(comments))})"
    if pull:
        heading += "; review comments on the diff are not included"
    parts = [
        f"# {issue.get('title', '')}",
        " | ".join(facts),
        demote_headings(issue.get("body") or "", 2),
        heading,
        *(
            f"### {author(comment)} on {comment.get('created_at', '')[:10]}\n\n"
            + demote_headings((comment.get("body") or "").strip(), 3)
            for comment in comments
        ),
    ]
    return "\n\n".join(part.strip() for part in parts if part.strip())


def api_json(http: Http, url: str) -> Any:
    try:
        download = http.download(
            url, accept=API_ACCEPT, headers=api_headers(url), impersonate=False
        )
    except ResearchError as error:
        if is_api_rate_limit(url, error.status):
            raise rate_limit_error(error.status) from error
        raise
    try:
        return json.loads(download.text())
    except ValueError as error:
        raise ResearchError("GitHub API: invalid JSON response") from error


def fetch_thread(http: Http, api_url: str) -> str:
    """An issue or pull request with its comments, read through the API."""
    issue = api_json(http, api_url)
    comments: list[dict[str, Any]] = []
    for page in range(1, COMMENT_PAGES + 1):
        batch = api_json(http, comments_api_url(api_url, page))
        if not isinstance(issue, dict) or not isinstance(batch, list):
            raise ResearchError("GitHub API: unexpected response shape")
        comments.extend(batch)
        if len(batch) < COMMENTS_PER_PAGE:
            break
    return render_thread(issue, comments)
