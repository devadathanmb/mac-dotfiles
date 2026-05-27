// Based on pi-filechanges by Johnny Wu (@johnnywu)
// Original: https://github.com/jwu/pi-filechanges.git
// Licensed under MIT

import { createTwoFilesPatch } from "diff";
import { relative, resolve } from "node:path";

// --- Types ---

export type Baseline = {
  path: string; // normalized path relative to ctx.cwd where possible
  absPath: string;
  originalContent: string | null; // null => file did not exist (created)
  createdAt: number;
};

export type TrackedFile = {
  path: string;
  absPath: string;
  displayPath: string;
  originalContent: string | null;
  currentContent: string;
  added: number;
  removed: number;
  kind: "new" | "edited";
  updatedAt: number;
};

export type PendingSnapshot = {
  path: string;
  absPath: string;
  before: string | null;
};

// --- Icons ---
const ICON_EDITED = "";
const ICON_NEW = "";

// --- Pure / standalone utility functions ---

/**
 * Strip a leading "@" prefix from a path string if present.
 */
export function stripAtPrefix(p: string): string {
  return p.startsWith("@") ? p.slice(1) : p;
}

/**
 * Resolve a raw tool path (possibly "@"-prefixed) into absolute and
 * cwd-relative paths.
 */
export function normalizeToolPath(cwd: string, raw: string): { absPath: string; relPath: string } {
  const cleaned = stripAtPrefix(raw);
  const absPath = resolve(cwd, cleaned);
  const rel = relative(cwd, absPath);
  // Always use cwd-relative path for storage/UI.
  const relPath = rel || ".";
  return { absPath, relPath };
}

/**
 * Count added (+) and removed (-) lines in a unified diff, ignoring
 * the "+++", "---", and "@@" header lines.
 */
export function countDiffLines(unifiedDiff: string): { added: number; removed: number } {
  let added = 0;
  let removed = 0;
  for (const line of unifiedDiff.split("\n")) {
    if (line.startsWith("+++ ") || line.startsWith("--- ") || line.startsWith("@@")) continue;
    if (line.startsWith("+")) added++;
    else if (line.startsWith("-")) removed++;
  }
  return { added, removed };
}

/**
 * Format added/removed counts as a plain string: "(+x/-y)".
 */
export function formatAddedRemovedPlain(added: number, removed: number): string {
  return `(+${added}/-${removed})`;
}

/**
 * Generate a unified diff patch between baseline and current content.
 * Pass null for original to indicate a new file.
 *
 * The patch is used only for computing aggregate added/removed counts;
 * the extension no longer exposes diff inspection UI.
 */
export function patchFromBaseline(
  displayPath: string,
  original: string | null,
  current: string,
): string {
  return createTwoFilesPatch(displayPath, displayPath, original ?? "", current, "", "", {
    context: 3,
  });
}

/**
 * Split command argument string into trimmed, non-empty tokens.
 */
export function splitArgs(args: string | undefined): string[] {
  if (!args) return [];
  return args
    .split(/\s+/g)
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * Estimate the visible (monospace column) width of a string.
 * Counts ASCII chars as 1, CJK / fullwidth / wide chars as 2.
 */
function visibleWidth(s: string): number {
  let w = 0;
  for (const ch of s) {
    const cp = ch.codePointAt(0)!;
    if (
      (cp >= 0x1100 && cp <= 0x115f) || // Hangul Jamo
      (cp >= 0x2e80 && cp <= 0xa4cf) || // CJK Radicals .. Yi
      (cp >= 0xac00 && cp <= 0xd7a3) || // Hangul Syllables
      (cp >= 0xf900 && cp <= 0xfaff) || // CJK Compatibility Ideographs
      (cp >= 0xfe10 && cp <= 0xfe19) || // Vertical forms
      (cp >= 0xfe30 && cp <= 0xfe6f) || // CJK Compatibility Forms
      (cp >= 0xff01 && cp <= 0xff60) || // Fullwidth Forms
      (cp >= 0xffe0 && cp <= 0xffe6) || // Fullwidth Signs
      (cp >= 0x1f300 && cp <= 0x1f64f) || // Emoticons
      (cp >= 0x1f900 && cp <= 0x1f9ff) || // Supplemental Symbols
      (cp >= 0x20000 && cp <= 0x2ffff) // CJK Extension B ..
    ) {
      w += 2;
    } else {
      w += 1;
    }
  }
  return w;
}

// --- Theme-dependent formatting (accept a lightweight theme interface) ---

export interface ThemeLike {
  fg(color: string, text: string): string;
}

function compareAsciiLowercaseFirst(a: string, b: string): number {
  const rank = (char: string): number => {
    if (char >= "a" && char <= "z") return char.charCodeAt(0) - 97;
    if (char >= "A" && char <= "Z") return char.charCodeAt(0) - 65 + 26;
    return char.charCodeAt(0) + 52;
  };

  const length = Math.min(a.length, b.length);
  for (let i = 0; i < length; i++) {
    const ar = rank(a[i]);
    const br = rank(b[i]);
    if (ar !== br) return ar - br;
  }

  return a.length - b.length;
}

/**
 * Build a short status string for the footer/status area.
 * Returns undefined when there are no tracked files.
 */
export function formatStatus(
  tracked: Map<string, TrackedFile>,
  theme?: ThemeLike,
): string | undefined {
  if (tracked.size === 0) return undefined;

  let edited = 0;
  let created = 0;
  for (const t of tracked.values()) {
    if (t.kind === "new") created++;
    else edited++;
  }

  const status = `${ICON_EDITED}${edited}  ${ICON_NEW}${created}`;
  return theme ? theme.fg("muted", status) : status;
}

/**
 * Build a list of lines for the widget area (rendered above the editor).
 * At most `maxLines` files are shown; the rest are summarized.
 * When `maxWidth` is provided, display paths are truncated from the left
 * (e.g. "ICON_EDITED ...ny-work/01-daily-日记/2026-05-12.md (+48/-3)") to fit.
 * Returns undefined when there are no tracked files.
 */
export function buildWidgetLines(
  tracked: Map<string, TrackedFile>,
  theme?: ThemeLike,
  maxLines?: number,
  maxWidth?: number,
): string[] | undefined {
  if (tracked.size === 0) return undefined;
  const max = maxLines ?? 8;
  const items = [...tracked.values()].sort((a, b) =>
    compareAsciiLowercaseFirst(a.displayPath, b.displayPath),
  );
  const lines: string[] = [];

  for (const t of items.slice(0, max)) {
    const tag = t.kind === "new" ? ICON_NEW : ICON_EDITED;
    const countStr = formatAddedRemovedPlain(t.added, t.removed); // e.g. "(+48/-3)"

    if (!theme) {
      let line = `${tag} ${t.displayPath} ${countStr}`;
      if (maxWidth && line.length > maxWidth) {
        line = truncateLinePlain(tag, t.displayPath, countStr, maxWidth);
      }
      lines.push(line);
      continue;
    }

    const plus =
      t.added === 0 ? theme.fg("text", `+${t.added}`) : theme.fg("success", `+${t.added}`);
    const minus =
      t.removed === 0 ? theme.fg("text", `-${t.removed}`) : theme.fg("error", `-${t.removed}`);
    const counts =
      theme.fg("text", "(") + plus + theme.fg("text", "/") + minus + theme.fg("text", ")");

    if (maxWidth) {
      // Measure visible width of the non-path parts
      const prefixVis = visibleWidth(`${tag} `);
      const suffixVis = visibleWidth(` ${countStr}`);
      const pathVis = visibleWidth(t.displayPath);
      const totalVis = prefixVis + pathVis + suffixVis;

      if (totalVis > maxWidth) {
        const availPathVis = maxWidth - prefixVis - suffixVis - 3; // 3 for "..."
        if (availPathVis > 0) {
          // Truncate path from the left, preserving the rightmost chars
          let kept = "";
          let keptVis = 0;
          for (let i = t.displayPath.length - 1; i >= 0 && keptVis < availPathVis; i--) {
            kept = t.displayPath[i] + kept;
            keptVis = visibleWidth(kept);
          }
          // Trim excess if we overshot
          while (keptVis > availPathVis && kept.length > 0) {
            kept = kept.slice(1);
            keptVis = visibleWidth(kept);
          }
          const truncatedPath = "..." + kept;
          lines.push(
            theme.fg("muted", `${tag} `) + theme.fg("muted", truncatedPath + " ") + counts,
          );
          continue;
        }
        // Terminal too narrow for path — show minimal: "ICON_EDITED ... (+2/-1)"
        lines.push(theme.fg("muted", `${tag} ... `) + counts);
        continue;
      }
    }

    const prefix = theme.fg("muted", `${tag} `) + theme.fg("muted", `${t.displayPath} `);
    lines.push(prefix + counts);
  }

  if (items.length > max) {
    const rest = items.length - max;
    lines.push(theme ? theme.fg("dim", `…and ${rest} more`) : `…and ${rest} more`);
  }

  // Trailing blank line for visual breathing room above the prompt editor
  lines.push("");

  return lines;
}

/** Truncate a plain-text file-changes line by eliding the path from the left.
 * Falls back to "ICON_EDITED ... (+2/-1)" when even a truncated path won't fit. */
function truncateLinePlain(
  tag: string,
  displayPath: string,
  countStr: string,
  maxWidth: number,
): string {
  const prefix = `${tag} `;
  const suffix = ` ${countStr}`;
  const prefixVis = visibleWidth(prefix);
  const suffixVis = visibleWidth(suffix);
  const avail = maxWidth - prefixVis - suffixVis - 3; // 3 for "..."
  if (avail <= 0) return prefix + "..." + suffix;
  // Truncate from left, preserving rightmost chars
  let kept = displayPath;
  while (visibleWidth(kept) > avail && kept.length > 0) {
    kept = kept.slice(1);
  }
  return prefix + "..." + kept + suffix;
}
