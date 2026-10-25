"""Search results laid out to fit the inline limit, every result keeping its place.

A tight limit trims each result's text rather than dropping results, and each cut
notes the saved-file line where the text resumes.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .excerpts import MARKDOWN_LINK, preview_length, terms
from .models import SearchResult

# A page read by --read earns this multiple of a snippet's share of the preview.
PAGE_WEIGHT = 3
# Room reserved per result for the `… [+N chars, saved line L]` note.
CUT_NOTE_CHARS = 40
# Below this a trimmed passage says too little to be worth its lines.
MIN_PASSAGE_CHARS = 80
# Two results repeat each other when this share of one's word runs is in the other.
REPEAT_SHARE = 0.8
REPEAT_RUN_WORDS = 4
# Shorter texts share boilerplate runs by chance.
MIN_REPEAT_RUNS = 20
# Line numbers in a passage label differ between copies of the same text.
PASSAGE_LINES = re.compile(r"(?m)^\[lines \d+-\d+")


@dataclass(frozen=True)
class Layout:
    full: str  # every result complete, as saved
    compact: str  # fitted to the limit
    fitted: list[str]  # each result's text as shown in `compact`


def result_header(
    rank: int, result: SearchResult, show_providers: bool, show_queries: bool
) -> str:
    line = f"{rank}. {result.title or result.url or '(untitled)'}"
    if result.date:
        line += f" ({result.date})"
    if show_providers:
        line += f" [{', '.join(result.providers)}]"
    if show_queries:
        line += f" [queries: {', '.join(f'Q{q}' for q in sorted(result.query_ids))}]"
    lines = [line]
    if result.title and result.url:
        lines.append(result.url)
    if result.page:
        lines.append(
            f"page saved: {Path(result.page).name} ({result.page_chars:,} chars, "
            f"{result.source}); line numbers refer to it"
        )
    return "\n".join(lines)


def allowances(lengths: list[int], weights: list[int], budget: int) -> list[int]:
    """Split `budget` by weight; texts shorter than their share pass the rest on."""
    allowed = [0] * len(lengths)
    order = sorted(range(len(lengths)), key=lambda i: lengths[i] / weights[i])
    weight = sum(weights)
    for index in order:
        share = max(budget, 0) * weights[index] // weight
        allowed[index] = min(lengths[index], share)
        budget -= allowed[index]
        weight -= weights[index]
    return allowed


def trim_passage(text: str, allowed: int, first_line: int) -> str:
    """`text` cut to `allowed` chars, noting where it resumes in the saved file."""
    if allowed >= len(text):
        return text
    shown = ""
    if allowed >= MIN_PASSAGE_CHARS:
        shown = text[: preview_length(text, allowed)].rstrip()
    resume = first_line + (shown.count("\n") + 1 if shown else 0)
    note = f"… [+{len(text) - len(shown):,} chars, saved line {resume}]"
    return f"{shown}\n{note}" if shown else note


def repeated_results(texts: list[str]) -> dict[int, int]:
    """Results whose text an earlier result already shows: {index: earlier index}.

    A docs page and its source file, or a mirror, would otherwise be shown twice.
    """
    seen: list[tuple[int, set[tuple[str, ...]]]] = []
    repeats = {}
    for index, text in enumerate(texts):
        words = terms(MARKDOWN_LINK.sub(r"\1", PASSAGE_LINES.sub("", text)))
        runs = {
            tuple(words[start : start + REPEAT_RUN_WORDS])
            for start in range(len(words) - REPEAT_RUN_WORDS + 1)
        }
        if len(runs) < MIN_REPEAT_RUNS:
            continue
        for earlier, known in seen:
            if len(runs & known) >= REPEAT_SHARE * len(runs):
                repeats[index] = earlier
                break
        else:
            seen.append((index, runs))
    return repeats


def join_results(headers: list[str], texts: list[str]) -> str:
    return "\n\n".join(
        f"{header}\n{text}".rstrip()
        for header, text in zip(headers, texts, strict=True)
    )


def query_map(queries: list[str]) -> str:
    """The numbered queries that result headers cite, when there are several."""
    if len(queries) < 2:
        return ""
    numbered = (
        f"Q{number}: {json.dumps(query, ensure_ascii=False)}"
        for number, query in enumerate(queries, 1)
    )
    return "Queries:\n" + "\n".join(numbered) + "\n\n"


def layout_results(
    results: list[SearchResult],
    limit: int | None,
    *,
    show_providers: bool,
    queries: list[str],
) -> Layout:
    prefix = query_map(queries)
    headers = [
        result_header(rank, result, show_providers, bool(prefix))
        for rank, result in enumerate(results, 1)
    ]
    texts = [result.text for result in results]
    full = prefix + join_results(headers, texts)
    repeats = repeated_results(texts)
    fits = limit is None or len(full) <= limit
    if fits and not repeats:
        return Layout(full, full, texts)
    lengths = [0 if index in repeats else len(text) for index, text in enumerate(texts)]
    if fits:
        shares = lengths
    else:
        budget = (
            (limit or 0)
            - len(prefix)
            - sum(len(header) + 2 + CUT_NOTE_CHARS for header in headers)
        )
        weights = [PAGE_WEIGHT if result.page else 1 for result in results]
        shares = allowances(lengths, weights, budget)
    fitted = []
    line = 1 + prefix.count("\n")  # line of `full` where the next result starts
    for index, (header, text, allowed) in enumerate(
        zip(headers, texts, shares, strict=True)
    ):
        first_line = line + header.count("\n") + 1
        if index in repeats:
            fitted.append(
                f"[same text as result {repeats[index] + 1}; saved line {first_line}]"
            )
        else:
            fitted.append(trim_passage(text, allowed, first_line))
        # A result ends with a blank line; one without text has no passage lines.
        line = first_line + (text.count("\n") + 2 if text else 1)
    return Layout(full, prefix + join_results(headers, fitted), fitted)
