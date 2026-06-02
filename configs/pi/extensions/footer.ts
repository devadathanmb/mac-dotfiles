/**
 * Footer — minimal workspace status.
 *
 * Line 1: context on the left, YOLO on the right when enabled.
 * Line 2: folder/git on the left, Codex quota on the right when active.
 */
import type { ExtensionAPI, Theme } from "@earendil-works/pi-coding-agent";
import { truncateToWidth, visibleWidth } from "@earendil-works/pi-tui";
import { execFile } from "node:child_process";
import { readFile } from "node:fs/promises";
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

type GitInfo = {
  branch?: string;
  ahead?: number;
  behind?: number;
  prLabel?: string;
  conflicts?: number;
};

const CODEX_PROVIDER_ID = "openai-codex";
const CODEX_USAGE_UPDATE_EVENT = "codex-usage:update";
const CODEX_USAGE_REQUEST_EVENT = "codex-usage:request";
const PERMISSION_CONFIG_PATH = `${homedir()}/.pi/agent/extensions/pi-permission-system/config.json`;
const execFileAsync = promisify(execFile);

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(100, Math.max(0, value));
}

function isCodexModel(model: FooterModel | undefined): boolean {
  return model?.provider === CODEX_PROVIDER_ID;
}

function hyperlink(url: string, text: string): string {
  return `\x1b]8;;${url}\x1b\\${text}\x1b]8;;\x1b\\`;
}

function fmt(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "?";
  return n < 1000 ? `${n}` : `${(n / 1000).toFixed(1)}k`;
}

function formatCwd(cwd: string): string {
  const home = homedir();
  if (cwd === home) return "~";
  return cwd.startsWith(`${home}/`) ? `~/${relative(home, cwd)}` : cwd;
}

function composeLeftRight(left: string, right: string, width: number): string {
  const rightWidth = visibleWidth(right);
  if (rightWidth >= width) return truncateToWidth(right, width, "");

  const leftWidth = Math.max(0, width - rightWidth - 1);
  const trimmedLeft = truncateToWidth(left, leftWidth, "");
  const pad = " ".repeat(Math.max(1, width - visibleWidth(trimmedLeft) - rightWidth));
  return truncateToWidth(trimmedLeft + pad + right, width, "");
}

async function runGit(cwd: string, args: string[]): Promise<string | undefined> {
  try {
    const { stdout } = await execFileAsync("git", args, { cwd, timeout: 1800 });
    return stdout.trim();
  } catch {
    return undefined;
  }
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

async function getGitInfo(cwd: string, branchFromFooter?: string | null): Promise<GitInfo | undefined> {
  const isRepo = await runGit(cwd, ["rev-parse", "--is-inside-work-tree"]);
  if (isRepo !== "true") return undefined;

  const [branchFallback, aheadBehind, conflictsRaw, prLabel] = await Promise.all([
    runGit(cwd, ["branch", "--show-current"]),
    runGit(cwd, ["rev-list", "--left-right", "--count", "HEAD...@{upstream}"]),
    runGit(cwd, ["diff", "--name-only", "--diff-filter=U"]),
    getCurrentPrLabel(cwd),
  ]);

  const [aheadRaw, behindRaw] = aheadBehind?.split(/\s+/) ?? [];
  const ahead = aheadRaw ? Number.parseInt(aheadRaw, 10) : undefined;
  const behind = behindRaw ? Number.parseInt(behindRaw, 10) : undefined;
  const conflicts = conflictsRaw ? conflictsRaw.split("\n").filter(Boolean).length : 0;

  return {
    branch: branchFromFooter || branchFallback || undefined,
    ahead: Number.isFinite(ahead) ? ahead : undefined,
    behind: Number.isFinite(behind) ? behind : undefined,
    prLabel,
    conflicts,
  };
}

async function getYoloMode(): Promise<boolean> {
  try {
    const raw = await readFile(PERMISSION_CONFIG_PATH, "utf8");
    const parsed = JSON.parse(raw) as { yoloMode?: unknown };
    return parsed.yoloMode === true;
  } catch {
    return false;
  }
}

function buildContextDisplay(
  usage: { percent: number | null; tokens: number | null; contextWindow: number } | undefined,
  theme: Theme,
): string {
  const percent = clampPercent(usage?.percent ?? 0);
  const color = percent < 50 ? "success" : percent < 75 ? "warning" : "error";
  const barWidth = 14;
  const filled = Math.round((percent / 100) * barWidth);
  const bar =
    theme.fg("text", "[") +
    theme.fg(color, "#".repeat(filled)) +
    theme.fg("borderMuted", "—".repeat(barWidth - filled)) +
    theme.fg("text", "]");

  return (
    bar +
    theme.fg(color, ` ${Math.round(percent)}%`) +
    theme.fg("muted", ` (${fmt(usage?.tokens ?? null)}/${fmt(usage?.contextWindow ?? null)})`)
  );
}

function buildGitDisplay(cwd: string, gitInfo: GitInfo | undefined, theme: Theme): string {
  const sep = theme.fg("dim", "  ");
  const parts = [theme.fg("accent", "󰉋 ") + theme.fg("text", formatCwd(cwd))];

  if (gitInfo?.branch) {
    const pr = gitInfo.prLabel ? theme.fg("dim", " (") + theme.fg("mdLink", gitInfo.prLabel) + theme.fg("dim", ")") : "";
    parts.push(theme.fg("accent", " ") + theme.fg("text", gitInfo.branch) + pr);
  }

  const sync = [
    gitInfo?.ahead ? theme.fg("warning", `⇡${gitInfo.ahead}`) : undefined,
    gitInfo?.behind ? theme.fg("warning", `⇣${gitInfo.behind}`) : undefined,
  ].filter(Boolean);
  if (sync.length > 0) parts.push(sync.join(theme.fg("dim", " ")));

  if (gitInfo?.conflicts) parts.push(theme.fg("error", `conflicts ${gitInfo.conflicts}`));

  return parts.join(sep);
}

function buildCodexDisplay(snapshot: CodexUsageSnapshot | undefined, theme: Theme): string | undefined {
  if (!snapshot) return undefined;
  const parts: string[] = [];
  if (snapshot.primary) parts.push(formatLimitItem("5h", snapshot.primary, theme));
  if (snapshot.secondary) parts.push(formatLimitItem("wk", snapshot.secondary, theme));
  return parts.length > 0 ? parts.join(theme.fg("dim", "  ")) : undefined;
}

export default function (pi: ExtensionAPI) {
  let requestFooterRender: (() => void) | undefined;
  let refreshGitInfo: ((force?: boolean) => void) | undefined;

  pi.on("tool_execution_end", async () => {
    refreshGitInfo?.(true);
    requestFooterRender?.();
  });

  pi.on("session_start", async (_event, ctx) => {
    if (!ctx.hasUI) return;

    ctx.ui.setFooter((tui, theme, footerData) => {
      const renderCurrentFooter = () => tui.requestRender();
      requestFooterRender = renderCurrentFooter;

      let gitInfo: GitInfo | undefined;
      let gitRefreshInFlight = false;
      let codexUsageSnapshot: CodexUsageSnapshot | undefined;
      let yoloMode = false;
      let disposed = false;

      const refreshYoloMode = () => {
        void getYoloMode().then((next) => {
          if (disposed || next === yoloMode) return;
          yoloMode = next;
          tui.requestRender();
        });
      };

      refreshGitInfo = (force = false) => {
        if (gitRefreshInFlight && !force) return;
        gitRefreshInFlight = true;
        void getGitInfo(ctx.cwd, footerData.getGitBranch())
          .then((next) => {
            if (disposed) return;
            gitInfo = next;
            tui.requestRender();
          })
          .finally(() => {
            gitRefreshInFlight = false;
          });
      };

      refreshGitInfo(true);
      refreshYoloMode();
      const yoloTimer = setInterval(refreshYoloMode, 2500);
      yoloTimer.unref?.();

      const unsubBranch = footerData.onBranchChange(() => refreshGitInfo?.(true));
      const unsubUsage = pi.events.on(CODEX_USAGE_UPDATE_EVENT, (data) => {
        codexUsageSnapshot = isCodexUsageUpdate(data) ? data.snapshot : undefined;
        tui.requestRender();
      });

      pi.events.emit(CODEX_USAGE_REQUEST_EVENT, { model: ctx.model });

      return {
        dispose() {
          disposed = true;
          clearInterval(yoloTimer);
          unsubBranch();
          unsubUsage();
          if (requestFooterRender === renderCurrentFooter) requestFooterRender = undefined;
          if (refreshGitInfo) refreshGitInfo = undefined;
        },
        invalidate() {},
        render(width: number): string[] {
          const contextDisplay = theme.fg("muted", " ") + buildContextDisplay(ctx.getContextUsage(), theme);
          const modeDisplay = yoloMode ? theme.fg("warning", "YOLO") : "";
          const line1 = composeLeftRight(contextDisplay, modeDisplay, width);

          const gitDisplay = theme.fg("muted", " ") + buildGitDisplay(ctx.cwd, gitInfo, theme);
          const codexDisplay = isCodexModel(ctx.model) ? buildCodexDisplay(codexUsageSnapshot, theme) : undefined;
          const line2 = composeLeftRight(gitDisplay, codexDisplay ?? "", width);

          return [line1, "", line2];
        },
      };
    });
  });
}

function limitThemeColor(remainingPercent: number): "success" | "warning" | "error" {
  if (remainingPercent >= 50) return "success";
  if (remainingPercent >= 20) return "warning";
  return "error";
}

function formatReset(epochSeconds: number | undefined, theme: Theme): string {
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
  return theme.fg("muted", `  ${reset}`);
}

function formatLimitItem(label: string, window: CodexUsageWindow, theme: Theme): string {
  const percent = 100 - clampPercent(window.usedPercent);
  return (
    theme.fg("muted", `${label} `) +
    theme.fg(limitThemeColor(percent), `${percent.toFixed(0)}%`) +
    formatReset(window.resetsAt, theme)
  );
}

function isCodexUsageUpdate(data: unknown): data is CodexUsageUpdate {
  return !!data && typeof data === "object" && !Array.isArray(data);
}
