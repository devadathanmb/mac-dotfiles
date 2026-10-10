"""Previews, excerpts (--match, --section, --query, --lines), and saved responses."""

import argparse
import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from . import config

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
WORD = re.compile(r"[a-z0-9_]{2,}")
STOPWORDS = frozenset(
    {"a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for"}
    | {"from", "how", "in", "is", "it", "of", "on", "or", "that", "the", "this"}
    | {"to", "what", "when", "where", "which", "why", "with"}
)
# Without an inline limit, ranked passages still need a bound to be a selection.
DEFAULT_PASSAGE_CHARS = 12000
NO_PASSAGES = "No passages contain the question's words; use terms the page uses."
# A passage this short is usually a signature or term; its explanation follows.
SHORT_PASSAGE_CHARS = 160
# Room reserved for each passage's `[lines A-B | heading]` label.
PASSAGE_LABEL_CHARS = 60
# Longer matched lines (minified code, tables) are clipped in a ranked excerpt.
MATCH_LINE_CHARS = 300
# BM25 term-frequency saturation and length normalisation (the usual defaults).
BM25_K1 = 1.2
BM25_B = 0.75
MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """(line index, level, title) for ATX headings outside code fences."""
    found = []
    fenced = False
    for index, line in enumerate(lines):
        if FENCE.match(line):
            fenced = not fenced
        elif not fenced and (match := HEADING.match(line)):
            # Permalink anchors and link targets are noise in a label.
            title = MARKDOWN_LINK.sub(r"\1", match.group(2)).replace("¶", "").strip()
            found.append((index, len(match.group(1)), title))
    return found


def rarest_matches(
    lines: list[str], hits: list[int], pattern: re.Pattern[str], limit: int
) -> str:
    """As many matching lines as fit `limit`, favouring rarely matched text.

    A broad pattern mostly hits boilerplate; the alternative that matched only a
    few lines is usually the one the caller was looking for.
    """
    matched = {
        index: {match.group().lower() for match in pattern.finditer(lines[index])}
        for index in hits
    }
    frequency = Counter(text for texts in matched.values() for text in texts)
    ranked = sorted(
        hits, key=lambda index: (-sum(1 / frequency[t] for t in matched[index]), index)
    )
    note = (
        "[{} of {} matching lines, rarest matched text first; "
        "rg the saved file for the rest]"
    )
    used = len(note)
    chosen = {}
    for index in ranked:
        line = lines[index]
        if len(line) > MATCH_LINE_CHARS:
            line = line[:MATCH_LINE_CHARS] + " …"
        entry = f"{index + 1}: {line}"
        if used + len(entry) + 1 <= limit:
            chosen[index] = entry
            used += len(entry) + 1
    return "\n".join(
        [
            note.format(len(chosen), len(hits)),
            *under_headings(lines, [(i, chosen[i]) for i in sorted(chosen)]),
        ]
    )


def under_headings(lines: list[str], entries: list[tuple[int, str]]) -> list[str]:
    """Insert each entry's governing heading, once, so an excerpt can be placed.

    A matched changelog or release-note line means little without the version or
    date heading above it.
    """
    found = headings(lines)
    shown = {index for index, _ in entries}
    labelled = []
    position = 0
    current = None
    for index, entry in entries:
        while position < len(found) and found[position][0] <= index:
            position += 1
        heading = found[position - 1] if position else None
        if heading and heading != current and heading[0] not in shown:
            labelled.append(f"§ {heading[2]} (line {heading[0] + 1})")
        current = heading
        labelled.append(entry)
    return labelled


def matching_lines(
    text: str, pattern: re.Pattern[str], context: int, limit: int = 0
) -> str:
    lines = text.splitlines()
    selected = set()
    hits = []
    for index, line in enumerate(lines):
        if pattern.search(line):
            hits.append(index)
            selected.update(
                range(max(0, index - context), min(len(lines), index + context + 1))
            )
    entries = []
    previous = -1
    for index in sorted(selected):
        gap = "...\n" if previous >= 0 and index > previous + 1 else ""
        entries.append((index, f"{gap}{index + 1}: {lines[index]}"))
        previous = index
    excerpt = under_headings(lines, entries)
    if limit and sum(map(len, excerpt)) + len(excerpt) > limit:
        return rarest_matches(lines, hits, pattern, limit)
    return "\n".join(excerpt) or "No matching lines in this response."


def numbered_lines(text: str, first: int, last: int) -> str:
    lines = text.splitlines()
    if first > len(lines):
        return f"No such lines; this response has {len(lines)}."
    return "\n".join(
        f"{number}: {line}"
        for number, line in enumerate(lines[first - 1 : last], first)
    )


def page_outline(text: str, limit: int) -> str:
    """Line-numbered headings, dropping the deepest levels until they fit `limit`."""
    found = headings(text.splitlines())
    if len(found) < 3:
        return ""
    title = "Outline (line: heading); read a part with --section or --query:"
    depth = max(level for _, level, _ in found)
    while True:
        entries = [
            f"{index + 1}: {'#' * level} {name}"
            for index, level, name in found
            if level <= depth
        ]
        if len(title) + sum(len(entry) + 1 for entry in entries) <= limit or depth == 1:
            break
        depth -= 1
    kept = []
    used = len(title)
    for entry in entries:
        used += len(entry) + 1
        if used > limit:
            break
        kept.append(entry)
    if not kept:
        return ""
    if len(kept) < len(found):
        kept.append(f"(+{len(found) - len(kept)} more headings)")
    return "\n".join([title, *kept])


def matching_sections(text: str, pattern: re.Pattern[str]) -> str:
    """Whole sections whose heading matches, each ending at the next peer heading."""
    lines = text.splitlines()
    found = headings(lines)
    ranges: list[list[int]] = []
    for position, (index, level, name) in enumerate(found):
        if not pattern.search(name):
            continue
        end = next(
            (later for later, peer, _ in found[position + 1 :] if peer <= level),
            len(lines),
        )
        if ranges and index < ranges[-1][1]:
            ranges[-1][1] = max(ranges[-1][1], end)
        else:
            ranges.append([index, end])
    if not ranges:
        outline = page_outline(text, 2000)
        return "No heading matches this response." + (
            f"\n{outline}" if outline else " It has no markdown headings; use --match."
        )
    return "\n\n".join(
        f"[lines {start + 1}-{end}]\n" + "\n".join(lines[start:end]).strip()
        for start, end in ranges
    )


def terms(text: str) -> list[str]:
    return [word for word in WORD.findall(text.lower()) if word not in STOPWORDS]


def text_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """Half-open line ranges of paragraphs; a fenced code block stays whole."""
    blocks = []
    start = None
    fenced = False
    for index, line in enumerate(lines):
        if FENCE.match(line):
            fenced = not fenced
        if line.strip() or fenced:
            if start is None:
                start = index
        elif start is not None:
            blocks.append((start, index))
            start = None
    if start is not None:
        blocks.append((start, len(lines)))
    return blocks


@dataclass
class Block:
    """A paragraph or fenced code block, with the heading it sits under."""

    start: int
    end: int
    heading: str
    body: str
    counts: Counter


def passage_blocks(lines: list[str], wanted: set[str]) -> list[Block]:
    section = {index: name for index, _, name in headings(lines)}
    blocks = []
    heading = ""
    for start, end in text_blocks(lines):
        if start in section and end == start + 1:
            heading = section[start]
            continue
        body = "\n".join(lines[start:end])
        counts = Counter(terms(body))
        # A heading names its section, so its terms count toward each paragraph.
        counts.update(set(terms(heading)) & wanted)
        blocks.append(Block(start, end, heading, body, counts))
    return blocks


def relevance_order(blocks: list[Block], wanted: set[str]) -> list[int]:
    """Indexes of the blocks sharing words with the question, best BM25 score first."""
    average = sum(sum(block.counts.values()) for block in blocks) / len(blocks) or 1
    containing = Counter(
        term for block in blocks for term in wanted if block.counts[term]
    )

    def score(block: Block) -> float:
        length = sum(block.counts.values())
        norm = BM25_K1 * (1 - BM25_B + BM25_B * length / average)
        return sum(
            math.log(
                1 + (len(blocks) - containing[term] + 0.5) / (containing[term] + 0.5)
            )
            * block.counts[term]
            * (BM25_K1 + 1)
            / (block.counts[term] + norm)
            for term in wanted
            if block.counts[term]
        )

    scored = [(score(block), index) for index, block in enumerate(blocks)]
    return [index for value, index in sorted(scored, reverse=True) if value > 0]


def pick_passages(blocks: list[Block], order: list[int], limit: int) -> dict[int, str]:
    """Text of the best blocks that fit `limit`, keyed by block index."""
    picked: dict[int, str] = {}
    used = 0
    for index in order:
        if index in picked:
            continue
        body = blocks[index].body
        room = limit - used - PASSAGE_LABEL_CHARS
        if len(body) > room:
            # Clip only the best passage; a lesser one that does not fit is skipped.
            if picked or room < 200:
                continue
            body = body[: preview_length(body, room)].rstrip() + " …"
        picked[index] = body
        used += len(body) + PASSAGE_LABEL_CHARS
        after = index + 1
        if (
            len(body) < SHORT_PASSAGE_CHARS
            and after < len(blocks)
            and after not in picked
            and blocks[after].heading == blocks[index].heading
            and len(blocks[after].body) <= limit - used
        ):
            picked[after] = blocks[after].body
            used += len(picked[after]) + 2
    return picked


def ranked_passages(text: str, question: str, limit: int) -> str:
    """The paragraphs sharing the most words with `question`, in document order."""
    lines = text.splitlines()
    wanted = set(terms(question))
    blocks = passage_blocks(lines, wanted)
    if not blocks or not wanted:
        return NO_PASSAGES
    picked = pick_passages(blocks, relevance_order(blocks, wanted), limit)
    if not picked:
        return NO_PASSAGES
    # Adjacent picks under one heading read as a single passage.
    passages: list[tuple[int, int, str, list[str]]] = []
    previous = None
    for index in sorted(picked):
        block = blocks[index]
        if previous == index - 1 and passages[-1][2] == block.heading:
            start, _, heading, bodies = passages.pop()
            passages.append((start, block.end, heading, [*bodies, picked[index]]))
        else:
            passages.append((block.start, block.end, block.heading, [picked[index]]))
        previous = index
    return "\n\n".join(
        f"[lines {start + 1}-{end}"
        + (f" | {heading}]" if heading else "]")
        + "\n"
        + "\n\n".join(bodies)
        for start, end, heading, bodies in passages
    )


def preview_length(text: str, limit: int) -> int:
    if not limit or len(text) <= limit:
        return len(text)
    cut = text.rfind("\n\n", 0, limit)
    if cut < limit * 0.5:
        cut = text.rfind("\n", 0, limit)
    return limit if cut < limit * 0.5 else cut


def save_text(text: str, label: str, *, raw: bool = False) -> Path:
    config.OUTPUT.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:40] or "out"
    # The label is hashed too: one file read at two versions keeps two paths.
    digest = hashlib.sha1(f"{label}\0{text}".encode()).hexdigest()[:6]
    path = config.OUTPUT / f"{slug}-{digest}.md"
    path.write_bytes((text if raw else text + "\n").encode("utf-8"))
    return path


def saved_notice(path: Path, text: str, kind: str, shown: int, total: int) -> str:
    """The line telling the reader where the complete text is and how much they see."""
    return (
        f"[saved: {path} | {len(text):,} chars, {len(text.splitlines())} lines "
        f"| {kind} {shown:,}/{total:,} chars]"
    )


@dataclass
class Rendered:
    shown: str
    used: int
    chars: int
    lines: int
    path: Path | None = None
    notice: str = ""


def render_response(
    text: str,
    args: argparse.Namespace,
    label: str,
    *,
    raw: bool = False,
    budget: int | None = None,
    outline: bool = False,
    save: bool = False,
) -> Rendered:
    text = text if raw else text.strip()
    excerpt = bool(args.match or args.section or args.about or args.lines)
    limit = args.max_chars if budget is None else budget
    if args.match:
        display = matching_lines(text, args.match, args.context, limit)
    elif args.lines:
        display = numbered_lines(text, *args.lines)
    elif args.section:
        display = matching_sections(text, args.section)
    elif args.about:
        display = ranked_passages(text, args.about, limit or DEFAULT_PASSAGE_CHARS)
    else:
        display = text
    cut = preview_length(display, limit) if limit or budget is None else 0
    rendered = Rendered(display, cut, len(text), len(text.splitlines()))
    if not excerpt and not save and cut == len(display):
        return rendered
    rendered.path = save_text(text, label, raw=raw)
    rendered.shown = display[:cut].rstrip()
    if outline and not excerpt and not raw and cut < len(display):
        contents = page_outline(text, cut * 2 // 5)
        if contents:
            body = display[: preview_length(display, cut - len(contents))].rstrip()
            rendered.shown = f"{contents}\n\n{body}"
    # Notice first: agents often pipe through `head`, which would drop a trailing line.
    rendered.notice = saved_notice(
        rendered.path, text, "excerpt" if excerpt else "preview", cut, len(display)
    )
    return rendered


def emit_response(
    text: str,
    args: argparse.Namespace,
    label: str,
    *,
    raw: bool = False,
    budget: int | None = None,
    outline: bool = False,
) -> int:
    rendered = render_response(
        text, args, label, raw=raw, budget=budget, outline=outline
    )
    if rendered.notice:
        print(rendered.notice)
    if rendered.shown:
        print(rendered.shown)
    return rendered.used
