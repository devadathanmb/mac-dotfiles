"""Stack Exchange questions read through the public API.

The sites refuse automated clients, browser fingerprints included. The API is
open (300 requests a day per IP, 10,000 with a key) and states each answer's
score, acceptance, and dates, which the rendered page reduces to widgets.
"""

import html
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from html_to_markdown import convert

from .credentials import api_key
from .errors import ResearchError
from .excerpts import demote_headings
from .transport import Http, json_body

API = "https://api.stackexchange.com/2.3"
# Q&A sites; the bare stackexchange.com is the network's hub, not a site.
SITE = re.compile(
    r"(?:[a-z0-9-]+\.)?(?:stackoverflow\.com|serverfault\.com|superuser\.com"
    r"|askubuntu\.com|mathoverflow\.net|stackapps\.com)"
    r"|[a-z0-9-]+\.stackexchange\.com"
)
QUESTION_PATH = re.compile(r"/(?:questions|q)/(\d+)(?:/[^/]*)?/?")
# /a/<answer>, or a question URL that names an answer after its slug.
ANSWER_PATH = re.compile(r"/a/(\d+)(?:/\d+)?/?|/questions/\d+/[^/]+/(\d+)/?")
ANSWER_LIMIT = 10
LABEL = "Stack Exchange API"


def parse_url(url: str) -> tuple[str, str, str | None] | None:
    """(site, question or answer ID, kind) for a question or answer URL, else None.

    `kind` is "question" or "answer"; the site is the host, which the API accepts.
    """
    parts = urlsplit(url)
    host = (parts.hostname or "").removeprefix("www.")
    if not SITE.fullmatch(host):
        return None
    if answer := ANSWER_PATH.fullmatch(parts.path):
        return host, answer.group(1) or answer.group(2), "answer"
    if question := QUESTION_PATH.fullmatch(parts.path):
        return host, question.group(1), "question"
    return None


def api_items(http: Http, path: str, site: str, **params: str) -> list[dict[str, Any]]:
    query = {"site": site, **params}
    if key := api_key("stackexchange"):
        query["key"] = key
    response = http.call_api(
        "stackexchange",
        "GET",
        f"{API}/{path}",
        label=LABEL,
        hint="quota or throttle limit; the page is read from another source",
        params=query,
    )
    data = json_body(response, LABEL)
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ResearchError(f"{LABEL}: unexpected response shape")
    return [item for item in items if isinstance(item, dict)]


def day(timestamp: object) -> str:
    if not isinstance(timestamp, int):
        return ""
    return datetime.fromtimestamp(timestamp, UTC).date().isoformat()


def owner(item: dict[str, Any]) -> str:
    name = (item.get("owner") or {}).get("display_name") or "unknown"
    return html.unescape(name)


def markdown(body: object, depth: int) -> str:
    """A post's HTML as markdown, its headings nested below `depth`."""
    return demote_headings(str(convert(str(body or "")).content).strip(), depth)


def dated(item: dict[str, Any], verb: str) -> str:
    text = f"{verb} {day(item.get('creation_date'))} by {owner(item)}"
    if edited := day(item.get("last_edit_date")):
        text += f", edited {edited}"
    return text


def render_answer(answer: dict[str, Any], linked: str | None) -> str:
    facts = [f"score {answer.get('score', 0)}"]
    if answer.get("is_accepted"):
        facts.append("accepted")
    if str(answer.get("answer_id")) == linked:
        facts.append("the linked answer")
    heading = (
        f"### Answer {answer.get('answer_id')}: {', '.join(facts)} "
        f"| {dated(answer, 'answered')}"
    )
    if "body" not in answer:
        return (
            f"{heading}\n\n(The API returned no body; read the page with fetch --exa.)"
        )
    return f"{heading}\n\n{markdown(answer.get('body'), 3)}"


def render_question(
    site: str,
    question: dict[str, Any],
    answers: list[dict[str, Any]],
    linked: str | None,
) -> str:
    count = question.get("answer_count", len(answers))
    facts = [
        f"Question {question.get('question_id')} on {site}",
        f"score {question.get('score', 0)}",
        dated(question, "asked"),
        f"{count} answers"
        + (", one accepted" if question.get("accepted_answer_id") else ""),
    ]
    if tags := question.get("tags"):
        facts.append(f"tags: {', '.join(tags)}")
    parts = [
        f"# {html.unescape(question.get('title', ''))}",
        " | ".join(facts),
        markdown(question.get("body"), 2),
        f"## Answers ({len(answers)} of {count}, highest score first)",
        *(render_answer(answer, linked) for answer in answers),
    ]
    return "\n\n".join(part for part in parts if part)


def complete_answers(
    http: Http,
    site: str,
    question: dict[str, Any],
    answers: list[dict[str, Any]],
    linked: str | None,
) -> list[dict[str, Any]]:
    """`answers` plus the accepted and linked ones, each with its body.

    The API drops the body of a long answer from some pages of results, and an
    outvoted accepted or linked answer still belongs in the reply.
    """
    by_id = {str(answer.get("answer_id")): answer for answer in answers}
    wanted = [str(question.get("accepted_answer_id") or ""), linked or ""]
    refetch = [answer_id for answer_id, answer in by_id.items() if "body" not in answer]
    refetch += [
        answer_id for answer_id in wanted if answer_id and answer_id not in by_id
    ]
    if refetch:
        ids = ";".join(dict.fromkeys(refetch))
        for answer in api_items(http, f"answers/{ids}", site, filter="withbody"):
            by_id[str(answer.get("answer_id"))] = answer
    return list(by_id.values())


def fetch_question(http: Http, url: str) -> str | None:
    """The question and its best answers as markdown, or None for other URLs."""
    parsed = parse_url(url)
    if parsed is None:
        return None
    site, identifier, kind = parsed
    linked = None
    if kind == "answer":
        linked = identifier
        found = api_items(http, f"answers/{identifier}", site)
        if not found:
            raise ResearchError(
                f"{LABEL}: no answer {identifier} on {site}", final=True
            )
        identifier = str(found[0]["question_id"])
    questions = api_items(http, f"questions/{identifier}", site, filter="withbody")
    if not questions:
        raise ResearchError(f"{LABEL}: no question {identifier} on {site}", final=True)
    question = questions[0]
    answers = api_items(
        http,
        f"questions/{identifier}/answers",
        site,
        filter="withbody",
        sort="votes",
        order="desc",
        pagesize=str(ANSWER_LIMIT),
    )
    answers = complete_answers(http, site, question, answers, linked)
    return render_question(site, question, answers, linked)
