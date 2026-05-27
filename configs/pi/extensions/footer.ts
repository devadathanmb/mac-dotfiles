/**
 * Footer — Rich custom status bar
 *
 * Line 1: provider/model + [thinking] + context meter, tokens + cost
 * Line 2: cwd (branch) on left, tool tally on right
 * Line 3: OpenAI/Codex limits
 *
 * Usage: pi -e extensions/footer.ts
 *
 * All colors are pulled from the active Pi theme — no hardcoded palette.
 */
import type { AssistantMessage } from "@earendil-works/pi-ai";
import type { ExtensionAPI, Theme, ThemeColor } from "@earendil-works/pi-coding-agent";
import { truncateToWidth, visibleWidth } from "@earendil-works/pi-tui";
import { execFile } from "node:child_process";
import { homedir } from "node:os";
import { relative } from "node:path";
import { promisify } from "node:util";

type FooterModel = {
  provider?: string;
  id?: string;
};
type CodexUsageWindow = {
  usedPercent: number;
  resetsAt?: number;
};
type CodexUsageSnapshot = {
  primary?: CodexUsageWindow;
  secondary?: CodexUsageWindow;
};
type CodexUsageUpdate = {
  snapshot?: CodexUsageSnapshot;
};

const CODEX_USAGE_UPDATE_EVENT = "codex-usage:update";
const CODEX_USAGE_REQUEST_EVENT = "codex-usage:request";
const execFileAsync = promisify(execFile);

// ---------------------------------------------------------------------------
// Build ANSI fg escape from resolved hex (used for dynamic/computed colors
// that don't map directly to a theme token, e.g. the context-meter bar fill).
// ---------------------------------------------------------------------------
function hexFg(hex: string, text: string): string {
  const c = hex.replace(/^#/, "");
  const r = Number.parseInt(c.slice(0, 2), 16);
  const g = Number.parseInt(c.slice(2, 4), 16);
  const b = Number.parseInt(c.slice(4, 6), 16);
  return `\x1b[38;2;${r};${g};${b}m${text}\x1b[39m`;
}

/** Extract hex from a theme fg ANSI escape like \x1b[38;2;R;G;Bm */
function extractHexFromTheme(theme: Theme, color: ThemeColor): string {
  const ansi = theme.getFgAnsi(color);
  // ANSI format: \x1b[38;2;R;G;Bm — extract R, G, B
  const match = ansi.match(/38;2;(\d+);(\d+);(\d+)/);
  if (match) {
    const r = Number.parseInt(match[1]).toString(16).padStart(2, "0");
    const g = Number.parseInt(match[2]).toString(16).padStart(2, "0");
    const b = Number.parseInt(match[3]).toString(16).padStart(2, "0");
    return `#${r}${g}${b}`;
  }
  return "";
}

function isOpenAIModel(model: FooterModel | undefined): boolean {
  if (!model) return false;
  const provider = model.provider ?? "";
  return provider === "openai" || provider.startsWith("openai-") || provider.startsWith("openai/");
}

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(100, Math.max(0, value));
}

function hyperlink(url: string, text: string): string {
  return `\x1b]8;;${url}\x1b\\${text}\x1b]8;;\x1b\\`;
}

async function getCurrentPrLabel(cwd: string): Promise<string | undefined> {
  try {
    const { stdout } = await execFileAsync(
      "gh",
      ["pr", "view", "--json", "number,url", "--jq", "[.number, .url] | @tsv"],
      { cwd, timeout: 2500 },
    );
    const [number, url] = stdout.trim().split("\t");
    if (!number) return undefined;
    const label = `#${number}`;
    return url ? hyperlink(url, label) : label;
  } catch {
    return undefined;
  }
}

function composeLeftRight(left: string, right: string, width: number): string {
  const rightWidth = visibleWidth(right);
  const leftWidth = Math.max(0, width - rightWidth - 1);
  const trimmedLeft = truncateToWidth(left, leftWidth, "");
  const pad = " ".repeat(Math.max(1, width - visibleWidth(trimmedLeft) - rightWidth));
  return truncateToWidth(trimmedLeft + pad + right, width, "");
}

export default function (pi: ExtensionAPI) {
  const counts: Record<string, number> = {};
  let requestFooterRender: (() => void) | undefined;

  pi.on("tool_execution_end", async (event) => {
    counts[event.toolName] = (counts[event.toolName] || 0) + 1;
    requestFooterRender?.();
  });

  pi.on("session_start", async (_event, ctx) => {
    if (!ctx.hasUI) return;
    for (const key of Object.keys(counts)) delete counts[key];
    ctx.ui.setFooter((tui, theme, footerData) => {
      const renderCurrentFooter = () => tui.requestRender();
      requestFooterRender = renderCurrentFooter;
      let prLabel: string | undefined;
      let prLookupKey = "";
      let prLookupInFlight = false;
      let codexUsageSnapshot: CodexUsageSnapshot | undefined;

      // Resolve hex colors from the theme instance for dynamic colors
      const c = {
        muted: extractHexFromTheme(theme, "muted"),
        success: extractHexFromTheme(theme, "success"),
        warning: extractHexFromTheme(theme, "warning"),
        error: extractHexFromTheme(theme, "error"),
        mdCode: extractHexFromTheme(theme, "mdCode"),
        mdHeading: extractHexFromTheme(theme, "mdHeading"),
        mdLink: extractHexFromTheme(theme, "mdLink"),
        toolTitle: extractHexFromTheme(theme, "toolTitle"),
        border: extractHexFromTheme(theme, "border"),
      };

      const refreshPrInfo = () => {
        const branch = footerData.getGitBranch();
        const key = branch ? `${ctx.cwd}\n${branch}` : "";
        if (!key || key === prLookupKey || prLookupInFlight) return;
        prLookupKey = key;
        prLookupInFlight = true;
        void getCurrentPrLabel(ctx.cwd)
          .then((nextPrLabel) => {
            prLabel = nextPrLabel;
            tui.requestRender();
          })
          .finally(() => {
            prLookupInFlight = false;
          });
      };
      refreshPrInfo();

      const unsubBranch = footerData.onBranchChange(() => {
        prLookupKey = "";
        prLabel = undefined;
        refreshPrInfo();
        tui.requestRender();
      });

      const unsubUsage = pi.events.on(CODEX_USAGE_UPDATE_EVENT, (data) => {
        codexUsageSnapshot = isCodexUsageUpdate(data) ? data.snapshot : undefined;
        tui.requestRender();
      });

      pi.events.emit(CODEX_USAGE_REQUEST_EVENT, { model: ctx.model });

      return {
        dispose() {
          unsubBranch();
          unsubUsage();
          if (requestFooterRender === renderCurrentFooter) requestFooterRender = undefined;
        },
        invalidate() { },
        render(width: number): string[] {
          let tokIn = 0;
          let tokOut = 0;
          let cost = 0;
          for (const entry of ctx.sessionManager.getBranch()) {
            if (entry.type === "message" && entry.message.role === "assistant") {
              const m = entry.message as AssistantMessage;
              tokIn += m.usage.input;
              tokOut += m.usage.output;
              cost += m.usage.cost.total;
            }
          }

          const fmt = (n: number) => (n < 1000 ? `${n}` : `${(n / 1000).toFixed(1)}k`);

          const home = homedir();
          const dir = ctx.cwd.startsWith(home) ? `~/${relative(home, ctx.cwd)}` : ctx.cwd;

          const branch = footerData.getGitBranch();

          // Context meter
          const usage = ctx.getContextUsage();
          const pct = usage?.percent ?? 0;
          const filled = Math.round(pct / 10) || 1;
          const ctxBarColor = pct < 50 ? c.success : pct < 70 ? c.warning : c.error;

          // Model display
          const model = ctx.model ? `${ctx.model.provider}/${ctx.model.id}` : "no-model";
          const [modelProvider, ...modelIdParts] = model.split("/");
          const modelId = modelIdParts.join("/");
          const thinkingLevel = pi.getThinkingLevel();
          const thinking = thinkingLevel ? ` [${thinkingLevel}]` : "";
          const ctxWindow = usage ? usage.contextWindow : 0;
          const ctxTokens = usage?.tokens ?? tokIn + tokOut;

          const codexUsage = isOpenAIModel(ctx.model)
            ? formatCodexUsage(codexUsageSnapshot, c)
            : undefined;

          // --- Line 1: left (model + context) | right (tokens + cost) ---
          const modelDisplay = modelId
            ? theme.fg("muted", ` ${modelProvider}/`) + theme.fg("text", modelId)
            : theme.fg("text", ` ${model}`);

          const l1Left =
            modelDisplay +
            hexFg(c.mdLink, thinking) +
            theme.fg("muted", " ") +
            theme.fg("dim", "[") +
            hexFg(ctxBarColor, "#".repeat(filled)) +
            hexFg(c.border, "-".repeat(10 - filled)) +
            theme.fg("dim", "]") +
            theme.fg("muted", " ") +
            hexFg(ctxBarColor, `${Math.round(pct)}%`) +
            theme.fg("muted", ` (${fmt(ctxTokens)}/${fmt(ctxWindow)})`);

          const sep = theme.fg("muted", " · ");

          const l1Right =
            theme.fg("success", `${fmt(tokIn)}`) +
            theme.fg("muted", " in") +
            sep +
            theme.fg("mdCode", `${fmt(tokOut)}`) +
            theme.fg("muted", " out") +
            sep +
            theme.fg("mdHeading", `$${cost.toFixed(4)}`) +
            theme.fg("muted", " ");

          const line1 = composeLeftRight(l1Left, l1Right, width);

          // --- Line 2: cwd + branch (left), tool tally (right) ---
          refreshPrInfo();

          const l2Left =
            theme.fg("muted", ` 󰉋 ${dir}`) +
            (branch
              ? theme.fg("muted", " · ") +
              theme.fg("mdHeading", ` ${branch}`) +
              (prLabel
                ? theme.fg("muted", " ") +
                theme.fg("muted", "(") +
                theme.fg("mdLink", prLabel) +
                theme.fg("muted", ")")
                : "")
              : "");

          const entries = Object.entries(counts);
          const toolStatus =
            entries.length === 0
              ? theme.fg("dim", "idle")
              : entries
                .map(
                  ([name, count]) =>
                    theme.fg("mdCode", name) +
                    theme.fg("muted", " ") +
                    theme.fg("success", `${count}`),
                )
                .join(theme.fg("muted", " │ "));

          const line2 = composeLeftRight(l2Left, toolStatus + theme.fg("muted", " "), width);

          // --- Line 3: Codex usage ---
          const line3 = codexUsage
            ? truncateToWidth(theme.fg("muted", " ") + codexUsage, width, "")
            : undefined;

          return line3 ? [line1, "", line2, "", line3] : [line1, "", line2];
        },
      };
    });
  });
}

// ---------------------------------------------------------------------------
// Codex usage formatting (only runs for OpenAI models)
// ---------------------------------------------------------------------------

interface Colors {
  muted: string;
  success: string;
  warning: string;
  error: string;
  toolTitle: string;
}

function limitColorHex(remainingPercent: number, c: Colors): string {
  if (remainingPercent >= 50) return c.success;
  if (remainingPercent >= 20) return c.warning;
  return c.error;
}

function formatReset(epochSeconds: number | undefined, c: Colors): string {
  if (!epochSeconds) return "";
  const date = new Date(epochSeconds * 1000);
  if (Number.isNaN(date.getTime())) return "";
  const time = `${date.getHours().toString().padStart(2, "0")}:${date
    .getMinutes()
    .toString()
    .padStart(2, "0")}`;
  const now = new Date();
  const reset =
    date.toDateString() === now.toDateString()
      ? time
      : `${date.getDate()} ${date.toLocaleDateString(undefined, { month: "short" })} ${time}`;
  return (
    hexFg(c.muted, "  ") + hexFg(c.toolTitle, "") + hexFg(c.muted, "  ") + hexFg(c.muted, reset)
  );
}

function formatLimitItem(label: string, window: CodexUsageWindow, c: Colors): string {
  const percent = 100 - clampPercent(window.usedPercent);
  return (
    hexFg(c.muted, label) +
    hexFg(limitColorHex(percent, c), ` ${percent.toFixed(0)}%`) +
    formatReset(window.resetsAt, c)
  );
}

function formatCodexUsage(snapshot: CodexUsageSnapshot | undefined, c: Colors): string | undefined {
  if (!snapshot) return undefined;
  const parts: string[] = [];
  if (snapshot.primary) parts.push(formatLimitItem("5h", snapshot.primary, c));
  if (snapshot.secondary) parts.push(formatLimitItem("wk", snapshot.secondary, c));
  return parts.join(hexFg(c.muted, " · "));
}

function isCodexUsageUpdate(data: unknown): data is CodexUsageUpdate {
  return !!data && typeof data === "object" && !Array.isArray(data);
}
