// Based on pi-filechanges by Johnny Wu (@johnnywu)
// Original: https://github.com/jwu/pi-filechanges.git
// Licensed under MIT

import type {
  ExtensionAPI,
  ExtensionCommandContext,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import {
  isEditToolResult,
  isToolCallEventType,
  isWriteToolResult,
  keyHint,
} from "@earendil-works/pi-coding-agent";
import { readFile } from "node:fs/promises";

import {
  normalizeToolPath,
  countDiffLines,
  patchFromBaseline,
  splitArgs,
  formatStatus,
  buildWidgetLines,
  type Baseline,
  type TrackedFile,
  type PendingSnapshot,
  type ThemeLike,
} from "./utils.js";

// Custom session entry types
const ENTRY_BASELINE = "filechanges:baseline";
const ENTRY_CLEAR = "filechanges:clear";
const ENTRY_UNTRACK = "filechanges:untrack";

async function readTextOrNull(absPath: string): Promise<string | null> {
  try {
    return await readFile(absPath, "utf-8");
  } catch {
    return null;
  }
}

export default function (pi: ExtensionAPI) {
  // In-memory state (reconstructed on session_start from custom entries)
  const baselines = new Map<string, Baseline>(); // key: relPath
  const tracked = new Map<string, TrackedFile>(); // key: relPath
  // Per-tool-call snapshot, only committed on successful tool_result
  const pendingByToolCallId = new Map<string, PendingSnapshot>();

  // Widget is shown by default; `/filechanges` toggles it.
  let showWidget = true;

  // Minimal shape of the internal TUI instance — not exported by pi-tui.
  // Only the methods we actually call are declared here.
  interface TuiLike {
    getWidth?(): number;
    truncateToWidth?(line: string, width: number): string;
  }

  function updateUi(ctx?: ExtensionContext) {
    if (!ctx?.hasUI) return;
    ctx.ui.setStatus("filechanges", formatStatus(tracked, ctx.ui.theme));
    if (!showWidget) {
      ctx.ui.setWidget("filechanges", undefined);
      return;
    }
    // Use a factory so render() reads the live tools-expanded state on every TUI redraw.
    // When tools are expanded (ctrl+o), show all tracked files; otherwise cap at 8.
    ctx.ui.setWidget("filechanges", (_tui: unknown, theme: ThemeLike) => {
      const tui = _tui as TuiLike;
      return {
        render: () => {
          // getToolsExpanded is an internal Pi method not exposed in public types.
          // Safe to access via optional chaining — returns false when unavailable.
          const expanded =
            (
              ctx as ExtensionContext & { ui: { getToolsExpanded?(): boolean } }
            )?.ui?.getToolsExpanded?.() ?? false;
          const maxLines = expanded ? 9999 : 8;
          const termWidth = tui.getWidth?.() ?? process.stdout.columns ?? 80;
          const lines = buildWidgetLines(tracked, theme, maxLines, termWidth) ?? [];
          if (!expanded && tracked.size > maxLines) {
            const rest = tracked.size - maxLines;
            const hint = keyHint("app.tools.expand", "to expand");
            // buildWidgetLines() appends a blank spacer line; keep it after the Ctrl+O hint.
            const spacerIndex = lines.length > 0 && lines[lines.length - 1] === "" ? lines.length - 1 : lines.length;
            lines.splice(spacerIndex, 0, theme.fg("dim", `... (${rest} more files, ${hint})`));
          }
          // Safety net: brute-force truncate any line that still exceeds terminal width
          for (let i = 0; i < lines.length; i++) {
            if (typeof tui.truncateToWidth === "function") {
              lines[i] = tui.truncateToWidth(lines[i], termWidth);
            }
          }
          return lines;
        },
        invalidate: () => { },
      };
    });
  }

  async function recomputeTrackedFile(relPath: string) {
    const baseline = baselines.get(relPath);
    if (!baseline) return;

    const current = await readTextOrNull(baseline.absPath);
    if (baseline.originalContent === null) {
      // file was created
      if (current === null) {
        tracked.delete(relPath);
        return;
      }
      const displayPath = baseline.path;
      const diff = patchFromBaseline(displayPath, null, current);
      const { added, removed } = countDiffLines(diff);
      tracked.set(relPath, {
        path: baseline.path,
        absPath: baseline.absPath,
        displayPath,
        originalContent: null,
        currentContent: current,
        added,
        removed,
        kind: "new",
        updatedAt: Date.now(),
      });
      return;
    }

    // file existed before
    if (current === null) {
      // Deleted outside of tracked tools (or manually). Still track as edited; diff will show removal.
      const displayPath = baseline.path;
      const diff = patchFromBaseline(displayPath, baseline.originalContent, "");
      const { added, removed } = countDiffLines(diff);
      tracked.set(relPath, {
        path: baseline.path,
        absPath: baseline.absPath,
        displayPath,
        originalContent: baseline.originalContent,
        currentContent: "",
        added,
        removed,
        kind: "edited",
        updatedAt: Date.now(),
      });
      return;
    }

    if (current === baseline.originalContent) {
      // back to original; untrack
      tracked.delete(relPath);
      return;
    }

    const displayPath = baseline.path;
    const diff = patchFromBaseline(displayPath, baseline.originalContent, current);
    const { added, removed } = countDiffLines(diff);
    tracked.set(relPath, {
      path: baseline.path,
      absPath: baseline.absPath,
      displayPath,
      originalContent: baseline.originalContent,
      currentContent: current,
      added,
      removed,
      kind: "edited",
      updatedAt: Date.now(),
    });
  }

  async function clearLog(ctx?: ExtensionCommandContext) {
    baselines.clear();
    tracked.clear();
    pendingByToolCallId.clear();
    pi.appendEntry(ENTRY_CLEAR, { timestamp: Date.now(), reason: "clear" });
    updateUi(ctx);
  }

  pi.registerCommand("filechanges", {
    description: "Toggle the tracked file changes widget. Usage: /filechanges [clear]",
    getArgumentCompletions: (prefix) => {
      const trimmed = prefix.trimStart();
      if (trimmed.includes(" ")) return null;
      if (!"clear".startsWith(trimmed)) return null;
      return [{ value: "clear", label: "clear", description: "Clear the tracked changes log" }];
    },
    handler: async (args, ctx) => {
      const tokens = splitArgs(args);
      if (tokens.length === 0) {
        showWidget = !showWidget;
        updateUi(ctx);

        const message = showWidget ? "file changes shown" : "file changes hidden";
        if (ctx.hasUI) ctx.ui.notify(message, "info");
        else console.log(message);
        return;
      }

      if (tokens[0] === "clear") {
        const count = tracked.size;
        await clearLog(ctx);

        const message = `filechanges: cleared ${count} tracked file(s).`;
        if (ctx.hasUI) ctx.ui.notify(message, "info");
        else console.log(message);
        return;
      }

      const message = "filechanges: usage: /filechanges [clear]";
      if (ctx.hasUI) ctx.ui.notify(message, "info");
      else console.log(message);
    },
  });

  async function rebuildFromSession(ctx: ExtensionContext): Promise<void> {
    baselines.clear();
    tracked.clear();
    pendingByToolCallId.clear();

    // Replay custom entries on current branch
    for (const entry of ctx.sessionManager.getBranch()) {
      if (entry.type !== "custom") continue;

      if (entry.customType === ENTRY_CLEAR) {
        baselines.clear();
        tracked.clear();
        continue;
      }

      if (entry.customType === ENTRY_BASELINE) {
        const data = entry.data as any;
        if (!data?.path) continue;
        const { absPath, relPath } = normalizeToolPath(ctx.cwd, data.path);
        baselines.set(relPath, {
          path: relPath,
          absPath,
          originalContent: typeof data.originalContent === "string" ? data.originalContent : null,
          createdAt: typeof data.timestamp === "number" ? data.timestamp : Date.now(),
        });
        continue;
      }

      if (entry.customType === ENTRY_UNTRACK) {
        const data = entry.data as any;
        if (!data?.path) continue;
        const { relPath } = normalizeToolPath(ctx.cwd, data.path);
        baselines.delete(relPath);
        tracked.delete(relPath);
        continue;
      }
    }

    // Compute current change counts
    for (const relPath of baselines.keys()) {
      await recomputeTrackedFile(relPath);
    }

    updateUi(ctx);
  }

  // Rebuild state on any session/branch navigation events
  pi.on("session_start", async (_event, ctx) => {
    await rebuildFromSession(ctx);
  });

  pi.on("session_tree", async (_event, ctx) => {
    await rebuildFromSession(ctx);
  });

  pi.on("session_before_fork", async (_event, ctx) => {
    await rebuildFromSession(ctx);
  });

  // Capture before snapshots for edit/write
  pi.on("tool_call", async (event, ctx) => {
    if (isToolCallEventType("edit", event) || isToolCallEventType("write", event)) {
      const { absPath, relPath } = normalizeToolPath(ctx.cwd, event.input.path);
      const before = await readTextOrNull(absPath);
      pendingByToolCallId.set(event.toolCallId, { path: relPath, absPath, before });
    }
  });

  // Commit on successful results
  pi.on("tool_result", async (event, ctx) => {
    if (event.isError) {
      pendingByToolCallId.delete(event.toolCallId);
      return;
    }

    if (!isEditToolResult(event) && !isWriteToolResult(event)) return;

    const pending = pendingByToolCallId.get(event.toolCallId);
    pendingByToolCallId.delete(event.toolCallId);
    if (!pending) return;

    // If no baseline exists yet for this file, create one now from the successful call's snapshot.
    if (!baselines.has(pending.path)) {
      baselines.set(pending.path, {
        path: pending.path,
        absPath: pending.absPath,
        originalContent: pending.before,
        createdAt: Date.now(),
      });
      pi.appendEntry(ENTRY_BASELINE, {
        path: pending.path,
        originalContent: pending.before,
        timestamp: Date.now(),
      });
    }

    // Recompute cumulative change counts against baseline
    await recomputeTrackedFile(pending.path);

    // If file is back to baseline, untrack + persist
    const baseline = baselines.get(pending.path);
    const current = await readTextOrNull(pending.absPath);
    if (baseline) {
      const backToOriginal =
        (baseline.originalContent !== null && current === baseline.originalContent) ||
        (baseline.originalContent === null && current === null);

      if (backToOriginal) {
        baselines.delete(pending.path);
        tracked.delete(pending.path);
        pi.appendEntry(ENTRY_UNTRACK, { path: pending.path, timestamp: Date.now() });
      }
    }

    updateUi(ctx);
  });
}
