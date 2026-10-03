"""Preview, --match excerpts, and saving oversized responses to disk."""

import argparse
import hashlib
import re

from . import config


def matching_lines(text: str, pattern: re.Pattern[str], context: int) -> str:
    lines = text.splitlines()
    selected = set()
    for index, line in enumerate(lines):
        if pattern.search(line):
            selected.update(
                range(max(0, index - context), min(len(lines), index + context + 1))
            )
    excerpt = []
    previous = -1
    for index in sorted(selected):
        if previous >= 0 and index > previous + 1:
            excerpt.append("...")
        excerpt.append(f"{index + 1}: {lines[index]}")
        previous = index
    return "\n".join(excerpt) or "No matching lines in this response."


def preview_length(text: str, limit: int) -> int:
    if not limit or len(text) <= limit:
        return len(text)
    cut = text.rfind("\n\n", 0, limit)
    if cut < limit * 0.5:
        cut = text.rfind("\n", 0, limit)
    return limit if cut < limit * 0.5 else cut


def emit_response(
    text: str,
    args: argparse.Namespace,
    label: str,
    *,
    raw: bool = False,
    budget: int | None = None,
) -> int:
    text = text if raw else text.strip()
    display = matching_lines(text, args.match, args.context) if args.match else text
    cut = preview_length(display, args.max_chars)
    if budget is not None:
        cut = min(cut, budget)
    if not args.match and cut == len(display):
        print(display)
        return cut
    config.OUTPUT.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:40] or "out"
    digest = hashlib.sha1(text.encode()).hexdigest()[:6]
    path = config.OUTPUT / f"{slug}-{digest}.md"
    path.write_bytes((text if raw else text + "\n").encode("utf-8"))
    # Notice first: agents often pipe through `head`, which would drop a trailing line.
    print(
        f"[saved: {path} | {len(text):,} chars, {len(text.splitlines())} lines "
        f"| {'excerpt' if args.match else 'preview'} {cut:,}/{len(display):,} chars]"
    )
    if cut:
        print(display[:cut].rstrip())
    return cut
