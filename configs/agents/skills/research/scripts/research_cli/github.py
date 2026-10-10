"""GitHub URL forms: raw files, API authorization, and issue or PR threads."""

import re
from urllib.parse import urlsplit

from .credentials import github_token

API_HOST = "api.github.com"
# github.com/<owner>/<repo>/blob/<ref>/<path>: the HTML page is a JS shell.
BLOB = re.compile(r"https?://github\.com/([^/]+/[^/]+)/blob/([^?#]+)")
RAW = re.compile(r"https://raw\.githubusercontent\.com/([^/]+/[^/]+)/([^/]+)/([^?#]+)")
THREAD = re.compile(r"https?://github\.com/([^/]+/[^/]+)/(?:issues|pull)/(\d+)/?")
COMMENTS_PER_PAGE = 100
COMMENT_PAGES = 3
MAINTAINER_ROLES = ("OWNER", "MEMBER", "COLLABORATOR")


def raw_file_url(url: str) -> str | None:
    """The raw-content URL for a `blob` page URL, or None for any other URL."""
    blob = BLOB.fullmatch(url)
    if not blob:
        return None
    return f"https://raw.githubusercontent.com/{blob.group(1)}/{blob.group(2)}"


def api_headers(url: str) -> dict[str, str]:
    """Authorization for api.github.com only; the token is never sent elsewhere."""
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != API_HOST:
        return {}
    token = github_token()
    return {"Authorization": f"Bearer {token}"} if token else {}


def is_api_rate_limit(url: str, status: int) -> bool:
    return urlsplit(url).hostname == API_HOST and status in (403, 429)


def missing_path_hint(url: str) -> str:
    """How to locate a file whose guessed repository path does not exist."""
    match = RAW.match(raw_file_url(url) or url)
    if not match:
        return ""
    repo, ref, path = match.groups()
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


def author(item: dict) -> str:
    """Login plus the repository role that marks a maintainer's statement."""
    login = (item.get("user") or {}).get("login", "unknown")
    role = item.get("author_association", "")
    return f"{login} ({role.lower()})" if role in MAINTAINER_ROLES else login


def thread_state(issue: dict) -> str:
    state = issue.get("state", "")
    pull = issue.get("pull_request")
    if pull and state == "closed":
        merged = (pull.get("merged_at") or "")[:10]
        return f"merged {merged}" if merged else "closed without merging"
    if state == "closed" and issue.get("state_reason"):
        return f"closed as {issue['state_reason'].replace('_', ' ')}"
    return state


def render_thread(issue: dict, comments: list[dict]) -> str:
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
        issue.get("body") or "",
        heading,
        *(
            f"### {author(comment)} on {comment.get('created_at', '')[:10]}\n\n"
            + (comment.get("body") or "").strip()
            for comment in comments
        ),
    ]
    return "\n\n".join(part.strip() for part in parts if part.strip())
