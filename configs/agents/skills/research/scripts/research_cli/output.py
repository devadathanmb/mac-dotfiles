"""Inline previews and excerpts of responses, and the saved files they point into.

Agents read inline output, which is capped; the complete response is saved so a
later `rg` or Read can reach anything the preview left out.
"""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from . import config
from .excerpts import (
    DEFAULT_PASSAGE_CHARS,
    NO_MATCHES,
    matching_lines,
    matching_sections,
    numbered_lines,
    page_outline,
    preview_length,
    ranked_passages,
)

# Share of a long page's preview given to its heading outline.
OUTLINE_SHARE = 0.4


@dataclass(frozen=True)
class Selection:
    """The part of a response to show; at most one selector is set."""

    match: re.Pattern[str] | None = None
    context: int = 2
    section: re.Pattern[str] | None = None
    query: str | None = None
    lines: tuple[int, int] | None = None

    @property
    def active(self) -> bool:
        selectors = (self.match, self.section, self.query, self.lines)
        return any(selector is not None for selector in selectors)

    def apply(self, text: str, limit: int | None, *, markdown: bool = True) -> str:
        if self.match is not None:
            return matching_lines(
                text, self.match, self.context, limit or 0, markdown=markdown
            )
        if self.lines is not None:
            return numbered_lines(text, *self.lines)
        if self.section is not None:
            return matching_sections(text, self.section, markdown=markdown)
        if self.query is not None:
            budget = limit or DEFAULT_PASSAGE_CHARS
            return ranked_passages(text, self.query, budget, markdown=markdown)
        return text


NO_SELECTION = Selection()


def save_text(text: str, label: str, *, raw: bool = False) -> Path:
    config.OUTPUT.mkdir(parents=True, exist_ok=True, mode=0o700)
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:40] or "out"
    # The label is hashed too: one file read at two versions keeps two paths.
    digest = hashlib.sha256(f"{label}\0{text}".encode()).hexdigest()[:6]
    path = config.OUTPUT / f"{slug}-{digest}.md"
    path.write_bytes((text if raw else text + "\n").encode("utf-8"))
    return path


def saved_notice(path: Path, text: str, kind: str, shown: int, total: int) -> str:
    """The line saying where the complete text is and how much of it is shown."""
    return (
        f"[saved: {path} | {len(text):,} chars, {len(text.splitlines())} lines "
        f"| {kind} {shown:,}/{total:,} chars]"
    )


def fitted_length(text: str, limit: int | None) -> int:
    """Characters of `text` to show within `limit`; None is unlimited."""
    if limit is None:
        return len(text)
    return preview_length(text, limit) if limit else 0


@dataclass
class Rendered:
    shown: str
    used: int  # inline characters spent, for splitting a batch's budget
    chars: int
    lines: int
    path: Path | None = None
    notice: str = ""

    def __str__(self) -> str:
        # Notice first: agents often pipe through `head`, which drops a last line.
        return "\n".join(part for part in (self.notice, self.shown) if part)


def render(
    text: str,
    label: str,
    *,
    limit: int | None,
    selection: Selection = NO_SELECTION,
    raw: bool = False,
    outline: bool = False,
    save: bool = False,
    markdown: bool = True,
) -> Rendered:
    """Fit `text`, or the part `selection` picks, into `limit` inline characters.

    The complete text is saved whenever something is left out, a selector is
    used, or `save` asks for a path regardless. `markdown=False` marks source
    code whose `#` lines are comments, not headings.
    """
    text = text if raw else text.strip()
    display = selection.apply(text, limit, markdown=markdown)
    cut = fitted_length(display, limit)
    rendered = Rendered(display, cut, len(text), len(text.splitlines()))
    if not selection.active and not save and cut == len(display):
        return rendered
    rendered.path = save_text(text, label, raw=raw)
    rendered.shown = display[:cut].rstrip()
    if outline and not selection.active and not raw and cut < len(display):
        contents = page_outline(text, int(cut * OUTLINE_SHARE), markdown=markdown)
        if contents:
            body = display[: preview_length(display, cut - len(contents))].rstrip()
            rendered.shown = f"{contents}\n\n{body}"
    kind = "excerpt" if selection.active else "preview"
    rendered.notice = saved_notice(rendered.path, text, kind, cut, len(display))
    if selection.match is not None and display == NO_MATCHES:
        rendered.notice = (
            f"[saved: {rendered.path} | {len(text):,} chars, "
            f"{len(text.splitlines())} lines | --match: 0 matching lines; "
            "full response saved, try a different pattern or read the saved file]"
        )
    return rendered


@dataclass(frozen=True)
class Output:
    """How much of a response to print inline, and which part."""

    limit: int | None = config.DEFAULT_MAX_CHARS  # None: unlimited
    selection: Selection = NO_SELECTION


def emit(
    text: str,
    label: str,
    output: Output,
    *,
    raw: bool = False,
    outline: bool = False,
) -> Rendered:
    """Print `text` as `render` fits it, and return what was printed."""
    rendered = render(
        text,
        label,
        limit=output.limit,
        selection=output.selection,
        raw=raw,
        outline=outline,
    )
    if printed := str(rendered):
        print(printed)
    return rendered
