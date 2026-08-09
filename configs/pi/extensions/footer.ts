/**
 * Footer — minimal workspace status.
 *
 * Line 1: context on the left, YOLO on the right when enabled.
 * Line 2: folder/git on the left, provider quota on the right when active
 * (Codex rate-limit windows, or Copilot premium quota).
 */
import type { ExtensionAPI, Theme } from "@earendil-works/pi-coding-agent";
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
  used?: number;
  limit?: number;
  windowMinutes?: number;
  windowLabel?: string;
  resetsAt?: number;
};

type CodexUsageSnapshot = {
  primary?: CodexUsageWindow;
  secondary?: CodexUsageWindow;
};

type CodexUsageUpdate = {
  snapshot?: CodexUsageSnapshot;
  planType?: string;
};

type CopilotQuotaCategory = {
  entitlement?: number;
  remaining?: number;
  percentRemaining?: number;
  unlimited?: boolean;
  overagePermitted?: boolean;
};

type CopilotQuotaReport = {
  capturedAt: number;
  resetDate?: string;
  chat?: CopilotQuotaCategory;
  completions?: CopilotQuotaCategory;
  premiumInteractions?: CopilotQuotaCategory;
};

type CopilotUsageUpdate = {
  report: CopilotQuotaReport;
};

type GitInfo = {
  branch?: string;
  ahead?: number;
  behind?: number;
  prLabel?: string;
  conflicts?: number;
};

type DamageControlStatus = {
  mode?: "off" | "yolo" | "blacklist" | "whitelist" | "ask";
  enabled?: boolean;
  rulesLoaded?: number;
};

const CODEX_PROVIDER_ID = "openai-codex";
const CODEX_USAGE_UPDATE_EVENT = "codex-usage:update";
const CODEX_USAGE_REQUEST_EVENT = "codex-usage:request";
const COPILOT_PROVIDER_ID = "github-copilot";
const COPILOT_USAGE_UPDATE_EVENT = "copilot-usage:update";
const COPILOT_USAGE_REQUEST_EVENT = "copilot-usage:request";
const DAMAGE_CONTROL_STATUS_EVENT = "damage-control:status";
const DAMAGE_CONTROL_STATUS_REQUEST_EVENT = "damage-control:status-request";
const execFileAsync = promisify(execFile);

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(100, Math.max(0, value));
}

function isCodexModel(model: FooterModel | undefined): boolean {
  return model?.provider === CODEX_PROVIDER_ID;
}

function isCopilotModel(model: FooterModel | undefined): boolean {
  return model?.provider === COPILOT_PROVIDER_ID;
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

function buildCodexDisplay(
  snapshot: CodexUsageSnapshot | undefined,
  planType: string | undefined,
  theme: Theme,
): string | undefined {
  if (!snapshot) return undefined;
  const parts: string[] = [];
  if (snapshot.primary) parts.push(formatLimitItem("5h", snapshot.primary, planType, theme));
  if (snapshot.secondary) parts.push(formatLimitItem("wk", snapshot.secondary, undefined, theme));
  return parts.length > 0 ? parts.join(theme.fg("dim", "  ")) : undefined;
}

// resetDateIso is attached to the premium_interactions line, which is the
// quota relevant to premium model usage.
function formatCopilotCategory(
  label: string,
  category: CopilotQuotaCategory,
  theme: Theme,
  resetDateIso?: string,
): string | undefined {
  if (category.unlimited) return theme.fg("muted", `${label} `) + theme.fg("success", "unlimited");
  if (category.percentRemaining == null) return undefined;
  const percent = clampPercent(category.percentRemaining);
  return (
    theme.fg("muted", `${label} `) +
    theme.fg(limitThemeColor(percent), `${percent.toFixed(0)}%`) +
    formatCopilotReset(resetDateIso, theme)
  );
}

function formatCopilotReset(resetDateIso: string | undefined, theme: Theme): string {
  if (!resetDateIso) return "";
  const epochMs = Date.parse(resetDateIso);
  if (Number.isNaN(epochMs)) return "";
  return formatReset(Math.floor(epochMs / 1000), theme);
}

function buildCopilotDisplay(report: CopilotQuotaReport | undefined, theme: Theme): string | undefined {
  if (!report) return undefined;
  const parts: string[] = [];
  // Only premium interactions consume the quota relevant to premium models.
  if (report.premiumInteractions) {
    const item = formatCopilotCategory("prem", report.premiumInteractions, theme, report.resetDate);
    if (item) parts.push(item);
  }
  if (parts.length === 0) return undefined;
  return parts.join(theme.fg("dim", "  "));
}

function buildDamageControlDisplay(status: DamageControlStatus | undefined, fallback: string | undefined, theme: Theme): string {
  const mode = status?.mode ?? parseDamageControlMode(fallback);
  if (mode) {
    if (mode === "yolo") return theme.fg("warning", " YOLO");
    if (mode === "off") return theme.fg("dim", " off");
    const color = mode === "ask" ? "warning" : mode === "whitelist" ? "success" : "muted";
    return theme.fg(color, ` ${mode}`);
  }
  return fallback ?? "";
}

function parseDamageControlMode(status: string | undefined): DamageControlStatus["mode"] | undefined {
  if (!status) return undefined;
  const match = status.match(/(?:DC:\s*|\s*)(off|yolo|YOLO|blacklist|whitelist|ask)/);
  if (!match?.[1]) return undefined;
  const mode = match[1].toLowerCase();
  return isDamageControlMode(mode) ? mode : undefined;
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
      let codexUsagePlanType: string | undefined;
      let copilotUsageReport: CopilotQuotaReport | undefined;
      let damageControlStatus: DamageControlStatus | undefined;
      let disposed = false;

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

      const unsubBranch = footerData.onBranchChange(() => refreshGitInfo?.(true));
      const unsubUsage = pi.events.on(CODEX_USAGE_UPDATE_EVENT, (data) => {
        const update = isCodexUsageUpdate(data) ? data : undefined;
        codexUsageSnapshot = update?.snapshot;
        codexUsagePlanType = update?.planType;
        tui.requestRender();
      });
      const unsubCopilotUsage = pi.events.on(COPILOT_USAGE_UPDATE_EVENT, (data) => {
        copilotUsageReport = isCopilotUsageUpdate(data) ? data.report : undefined;
        tui.requestRender();
      });
      const unsubDamageControl = pi.events.on(DAMAGE_CONTROL_STATUS_EVENT, (data) => {
        damageControlStatus = isDamageControlStatus(data) ? data : undefined;
        tui.requestRender();
      });

      pi.events.emit(CODEX_USAGE_REQUEST_EVENT, { model: ctx.model });
      pi.events.emit(COPILOT_USAGE_REQUEST_EVENT, { model: ctx.model });
      pi.events.emit(DAMAGE_CONTROL_STATUS_REQUEST_EVENT, {});

      return {
        dispose() {
          disposed = true;
          unsubBranch();
          unsubUsage();
          unsubCopilotUsage();
          unsubDamageControl();
          if (requestFooterRender === renderCurrentFooter) requestFooterRender = undefined;
          if (refreshGitInfo) refreshGitInfo = undefined;
        },
        invalidate() {},
        render(width: number): string[] {
          const contextDisplay = theme.fg("muted", " ") + buildContextDisplay(ctx.getContextUsage(), theme);
          const fallbackStatus = footerData.getExtensionStatuses().get("damage-control");
          const modeDisplay = buildDamageControlDisplay(damageControlStatus, fallbackStatus, theme);
          const line1 = composeLeftRight(contextDisplay, modeDisplay, width);

          const gitDisplay = theme.fg("muted", " ") + buildGitDisplay(ctx.cwd, gitInfo, theme);
          const quotaDisplay = isCodexModel(ctx.model)
            ? buildCodexDisplay(codexUsageSnapshot, codexUsagePlanType, theme)
            : isCopilotModel(ctx.model)
              ? buildCopilotDisplay(copilotUsageReport, theme)
              : undefined;
          const line2 = composeLeftRight(gitDisplay, quotaDisplay ?? "", width);

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

function formatLimitItem(
  label: string,
  window: CodexUsageWindow,
  planType: string | undefined,
  theme: Theme,
): string {
  const percent = 100 - clampPercent(window.usedPercent);
  const isIndividualLimit = window.windowLabel === "individual";
  const actualLabel =
    (isIndividualLimit ? formatCodexPlanType(planType) : undefined) ??
    formatCodexWindowLabel(window) ??
    label;
  if (isIndividualLimit) {
    return (
      theme.fg("muted", `${actualLabel} `) +
      theme.fg(limitThemeColor(percent), `${percent.toFixed(0)}%`) +
      formatReset(window.resetsAt, theme)
    );
  }

  const requestUsage =
    window.used !== undefined && window.limit !== undefined
      ? `${formatFooterNumber(window.used)}/${formatFooterNumber(window.limit)} `
      : "";
  return (
    theme.fg("muted", `${actualLabel} ${requestUsage}`) +
    theme.fg(limitThemeColor(percent), `${percent.toFixed(0)}%`) +
    formatReset(window.resetsAt, theme)
  );
}

function formatFooterNumber(value: number): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value);
}

function formatCodexPlanType(planType: string | undefined): string | undefined {
  const normalized = planType?.trim().toLowerCase();
  return normalized || undefined;
}

function formatCodexWindowLabel(window: CodexUsageWindow): string | undefined {
  if (window.windowLabel) return window.windowLabel;
  if (window.windowMinutes === 5 * 60) return "5h";
  if (window.windowMinutes === 7 * 24 * 60) return "wk";
  if (window.windowMinutes && window.windowMinutes % (24 * 60) === 0) {
    return `${window.windowMinutes / (24 * 60)}d`;
  }
  if (window.windowMinutes && window.windowMinutes % 60 === 0) {
    return `${window.windowMinutes / 60}h`;
  }
  return undefined;
}

function isCodexUsageUpdate(data: unknown): data is CodexUsageUpdate {
  return !!data && typeof data === "object" && !Array.isArray(data);
}

function isCopilotUsageUpdate(data: unknown): data is CopilotUsageUpdate {
  return !!data && typeof data === "object" && !Array.isArray(data) && "report" in data;
}

function isDamageControlStatus(data: unknown): data is DamageControlStatus {
  if (!data || typeof data !== "object" || Array.isArray(data)) return false;
  return isDamageControlMode((data as DamageControlStatus).mode);
}

function isDamageControlMode(mode: unknown): mode is NonNullable<DamageControlStatus["mode"]> {
  return mode === "off" || mode === "yolo" || mode === "blacklist" || mode === "whitelist" || mode === "ask";
}
