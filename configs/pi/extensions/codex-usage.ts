// Local copy of @narumitw/pi-codex-usage, patched for this config.
// Upstream: https://github.com/narumiruna/pi-extensions/blob/main/extensions/pi-codex-usage/src/codex-usage.ts

import type {
  ExtensionAPI,
  ExtensionCommandContext,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent";

const COMMAND_NAME = "codex-status";
const CODEX_PROVIDER_ID = "openai-codex";
const CODEX_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage";
const DEFAULT_TIMEOUT_MS = 15_000;
const CACHE_TTL_MS = 5 * 60 * 1000;
const STATUS_KEY = "codex-usage";
const USAGE_UPDATE_EVENT = "codex-usage:update";
const USAGE_REQUEST_EVENT = "codex-usage:request";
const USAGE_SETTINGS_URL = "https://chatgpt.com/codex/settings/usage";
const BAR_SEGMENTS = 20;
const LIMIT_VALUE_COLUMN = 29;
const MAX_ERROR_BODY_CHARS = 600;
const RESET_FOREGROUND = "\x1b[39m";

type UsageSource = "pi-auth";
type PiModel = NonNullable<ExtensionContext["model"]>;
export type CodexUsageModel = Pick<PiModel, "id" | "name" | "provider">;

type QueryUsageOptions = {
  clearStatusline: boolean;
  refresh: boolean;
  statusline: boolean;
  timeoutMs: number;
};

type CachedReport = {
  createdAt: number;
  report: CodexUsageReport;
};

type UsageUpdateEvent = {
  report: CodexUsageReport;
  snapshot?: NormalizedRateLimitSnapshot;
  planType?: string;
  statusText: string;
  model?: CodexUsageModel;
  capturedAt: number;
};

type UsageRequestEvent = {
  model?: CodexUsageModel;
};

type QueryUsageResult =
  | { ok: true; report: CodexUsageReport }
  | { ok: false; errors: UsageQueryError[] };

type UsageQueryError = {
  source: UsageSource;
  message: string;
  cause?: unknown;
};

type CodexUsageReport = {
  source: UsageSource;
  capturedAt: number;
  planType?: string;
  snapshots: NormalizedRateLimitSnapshot[];
};

type NormalizedRateLimitSnapshot = {
  limitId: string;
  limitName?: string;
  primary?: NormalizedRateLimitWindow;
  secondary?: NormalizedRateLimitWindow;
  credits?: NormalizedCredits;
};

type NormalizedRateLimitWindow = {
  usedPercent: number;
  used?: number;
  limit?: number;
  windowMinutes?: number;
  windowLabel?: string;
  resetsAt?: number;
};

type NormalizedCredits = {
  hasCredits: boolean;
  unlimited: boolean;
  balance?: string;
};

type RateLimitStatusPayload = {
  plan_type?: unknown;
  rate_limit?: unknown;
  individual_limit?: unknown;
  individualLimit?: unknown;
  spend_control?: unknown;
  additional_rate_limits?: unknown;
  credits?: unknown;
};

type BackendRateLimitDetails = {
  primary_window?: unknown;
  secondary_window?: unknown;
  individual_limit?: unknown;
  individualLimit?: unknown;
};

type BackendWindowSnapshot = {
  used_percent?: unknown;
  limit_window_seconds?: unknown;
  reset_at?: unknown;
};

type BackendAdditionalRateLimit = {
  limit_name?: unknown;
  metered_feature?: unknown;
  rate_limit?: unknown;
};

type BackendCreditsSnapshot = {
  has_credits?: unknown;
  unlimited?: unknown;
  balance?: unknown;
};

export default function codexUsage(pi: ExtensionAPI) {
  let cache: CachedReport | undefined;
  let statuslineClearTimer: ReturnType<typeof setTimeout> | undefined;
  let statuslineRefreshTimer: ReturnType<typeof setTimeout> | undefined;
  let statuslineRequestId = 0;

  const emitUsageUpdate = (
    report: CodexUsageReport,
    model: CodexUsageModel | undefined,
    statusText = formatCodexUsageStatusline(report, model),
  ) => {
    const payload: UsageUpdateEvent = {
      report,
      snapshot: selectSnapshotForModel(report, model),
      planType: report.planType,
      statusText,
      model,
      capturedAt: Date.now(),
    };
    pi.events.emit(USAGE_UPDATE_EVENT, payload);
  };

  const emitUsageClear = () => {
    pi.events.emit(USAGE_UPDATE_EVENT, undefined);
  };

  pi.events.on(USAGE_REQUEST_EVENT, (data) => {
    if (!cache) return;
    const request = isPlainObject(data) ? (data as UsageRequestEvent) : {};
    emitUsageUpdate(cache.report, request.model);
  });

  const clearStatuslineTimers = () => {
    if (statuslineClearTimer) clearTimeout(statuslineClearTimer);
    if (statuslineRefreshTimer) clearTimeout(statuslineRefreshTimer);
    statuslineClearTimer = undefined;
    statuslineRefreshTimer = undefined;
  };

  const clearUsageStatusline = (ctx: ExtensionContext) => {
    statuslineRequestId += 1;
    clearStatuslineTimers();
    ctx.ui.setStatus(STATUS_KEY, undefined);
    emitUsageClear();
  };

  const scheduleTemporaryStatuslineClear = (ctx: ExtensionContext) => {
    if (statuslineClearTimer) clearTimeout(statuslineClearTimer);
    statuslineClearTimer = setTimeout(() => {
      ctx.ui.setStatus(STATUS_KEY, undefined);
      emitUsageClear();
      statuslineClearTimer = undefined;
    }, CACHE_TTL_MS);
    statuslineClearTimer.unref?.();
  };

  const scheduleStatuslineRefresh = (ctx: ExtensionContext) => {
    if (statuslineRefreshTimer) clearTimeout(statuslineRefreshTimer);
    statuslineRefreshTimer = setTimeout(() => {
      void refreshCurrentCodexUsageStatusline(ctx, true);
    }, CACHE_TTL_MS);
    statuslineRefreshTimer.unref?.();
  };

  const setUsageStatusline = (
    ctx: ExtensionContext,
    report: CodexUsageReport,
    options: { autoRefresh: boolean; model: CodexUsageModel | undefined },
  ) => {
    if (statuslineClearTimer) clearTimeout(statuslineClearTimer);
    statuslineClearTimer = undefined;
    const statusText = formatCodexUsageStatusline(report, options.model);
    ctx.ui.setStatus(STATUS_KEY, statusText);
    emitUsageUpdate(report, options.model, statusText);
    if (options.autoRefresh) scheduleStatuslineRefresh(ctx);
    else scheduleTemporaryStatuslineClear(ctx);
  };

  const refreshCurrentCodexUsageStatusline = async (
    ctx: ExtensionContext,
    force: boolean,
    model = ctx.model,
  ) => {
    if (!isOpenAICodexModel(model)) {
      clearUsageStatusline(ctx);
      return;
    }

    const requestId = statuslineRequestId + 1;
    statuslineRequestId = requestId;
    const cached = cache && Date.now() - cache.createdAt < CACHE_TTL_MS ? cache : undefined;
    if (cached && !force) {
      setUsageStatusline(ctx, cached.report, { autoRefresh: true, model });
      return;
    }

    ctx.ui.setStatus(STATUS_KEY, "📊 checking");
    const result = await queryUsage(ctx, { timeoutMs: DEFAULT_TIMEOUT_MS });
    if (requestId !== statuslineRequestId) return;
    if (!isOpenAICodexModel(ctx.model)) {
      clearUsageStatusline(ctx);
      return;
    }

    if (!result.ok) {
      ctx.ui.setStatus(STATUS_KEY, "📊 usage error");
      scheduleStatuslineRefresh(ctx);
      return;
    }

    cache = { createdAt: Date.now(), report: result.report };
    setUsageStatusline(ctx, result.report, { autoRefresh: true, model });
  };

  pi.registerCommand(COMMAND_NAME, {
    description: "Show Codex ChatGPT subscription usage and rate-limit windows",
    handler: async (args, ctx) => {
      const options = parseArgs(args);
      if (!options.ok) {
        ctx.ui.notify(options.error, "warning");
        return;
      }

      if (options.value.clearStatusline) {
        clearUsageStatusline(ctx);
        ctx.ui.notify("Codex usage statusline cleared.", "info");
        return;
      }

      const cached = cache && Date.now() - cache.createdAt < CACHE_TTL_MS ? cache : undefined;
      if (cached && !options.value.refresh) {
        if (options.value.statusline) {
          setUsageStatusline(ctx, cached.report, {
            autoRefresh: isOpenAICodexModel(ctx.model),
            model: ctx.model,
          });
        }
        showReport(ctx, cached.report, true);
        return;
      }

      let keepStatusline = false;
      if (options.value.statusline) ctx.ui.setStatus(STATUS_KEY, "📊 checking");
      try {
        const result = await queryUsage(ctx, options.value);
        if (!result.ok) {
          ctx.ui.notify(formatQueryErrors(result.errors), "error");
          return;
        }

        cache = { createdAt: Date.now(), report: result.report };
        if (options.value.statusline) {
          setUsageStatusline(ctx, result.report, {
            autoRefresh: isOpenAICodexModel(ctx.model),
            model: ctx.model,
          });
          keepStatusline = true;
        }
        showReport(ctx, result.report, false);
      } finally {
        if (options.value.statusline && !keepStatusline) ctx.ui.setStatus(STATUS_KEY, undefined);
      }
    },
  });

  pi.on("session_start", (_event, ctx) => {
    if (isOpenAICodexModel(ctx.model)) void refreshCurrentCodexUsageStatusline(ctx, false);
    else clearUsageStatusline(ctx);
  });

  pi.on("session_tree", (_event, ctx) => {
    if (isOpenAICodexModel(ctx.model)) void refreshCurrentCodexUsageStatusline(ctx, false);
    else clearUsageStatusline(ctx);
  });

  pi.on("model_select", (event, ctx) => {
    if (isOpenAICodexModel(event.model)) {
      void refreshCurrentCodexUsageStatusline(ctx, false, event.model);
    } else {
      clearUsageStatusline(ctx);
    }
  });

  pi.on("session_shutdown", (_event, ctx) => clearUsageStatusline(ctx));
}

function parseArgs(
  args: string,
): { ok: true; value: QueryUsageOptions } | { ok: false; error: string } {
  const tokens = args.trim().split(/\s+/).filter(Boolean);
  let clearStatusline = false;
  let refresh = false;
  let statusline = true;
  let timeoutMs = DEFAULT_TIMEOUT_MS;

  for (let index = 0; index < tokens.length; index++) {
    const token = tokens[index];
    if (token === "--clear-statusline") {
      clearStatusline = true;
      continue;
    }
    if (token === "--no-statusline") {
      statusline = false;
      continue;
    }
    if (token === "--refresh") {
      refresh = true;
      continue;
    }
    if (token === "--timeout") {
      const rawValue = tokens[index + 1];
      if (!rawValue)
        return {
          ok: false,
          error: "Usage: /codex-status [--refresh] [--timeout seconds]",
        };
      const parsed = Number(rawValue);
      if (!Number.isFinite(parsed) || parsed <= 0 || parsed > 120) {
        return {
          ok: false,
          error: "--timeout must be a number of seconds between 1 and 120.",
        };
      }
      timeoutMs = Math.round(parsed * 1000);
      index += 1;
      continue;
    }
    return {
      ok: false,
      error: `Unknown option: ${token}. Usage: /codex-status [--refresh] [--no-statusline] [--clear-statusline] [--timeout seconds]`,
    };
  }

  return {
    ok: true,
    value: { clearStatusline, refresh, statusline, timeoutMs },
  };
}

function isOpenAICodexModel(model: Pick<PiModel, "provider"> | undefined): boolean {
  return model?.provider === CODEX_PROVIDER_ID;
}

async function queryUsage(
  ctx: ExtensionContext,
  options: Pick<QueryUsageOptions, "timeoutMs">,
): Promise<QueryUsageResult> {
  try {
    const report = await queryViaPiAuth(ctx, options.timeoutMs);
    return { ok: true, report };
  } catch (cause) {
    return {
      ok: false,
      errors: [{ source: "pi-auth", message: errorMessage(cause), cause }],
    };
  }
}

async function queryViaPiAuth(ctx: ExtensionContext, timeoutMs: number): Promise<CodexUsageReport> {
  const auth = await resolvePiCodexAuth(ctx);
  if (!auth) {
    throw new Error(
      "No Pi OpenAI Codex subscription auth was available. Use a Pi OpenAI Codex model or run /login for OpenAI ChatGPT Plus/Pro (Codex).",
    );
  }

  const response = await fetchWithTimeout(CODEX_USAGE_URL, { headers: auth.headers }, timeoutMs);
  const text = await response.text();
  if (!response.ok) {
    throw new Error(
      `Codex usage endpoint returned ${response.status} ${response.statusText}: ${redactErrorBody(text)}`,
    );
  }

  const payload = parseJsonObject(text, "Codex usage endpoint response");
  return normalizeBackendPayload(payload as RateLimitStatusPayload, Date.now(), "pi-auth");
}

async function resolvePiCodexAuth(
  ctx: ExtensionContext,
): Promise<{ headers: Record<string, string> } | undefined> {
  const models = codexAuthCandidateModels(ctx);
  const errors: string[] = [];

  for (const model of models) {
    const auth = await ctx.modelRegistry.getApiKeyAndHeaders(model);
    if (!auth.ok) {
      errors.push(auth.error);
      continue;
    }

    const headers = { ...(auth.headers ?? {}) };
    if (!hasHeader(headers, "Authorization") && auth.apiKey) {
      headers.Authorization = `Bearer ${auth.apiKey}`;
    }
    if (!hasHeader(headers, "User-Agent")) {
      headers["User-Agent"] = "pi-codex-usage";
    }
    if (hasHeader(headers, "Authorization")) {
      return { headers };
    }
  }

  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
  return undefined;
}

function codexAuthCandidateModels(ctx: ExtensionContext): PiModel[] {
  const candidates: PiModel[] = [];
  const seen = new Set<string>();
  const add = (model: PiModel | undefined) => {
    if (!model || model.provider !== CODEX_PROVIDER_ID) return;
    const key = `${model.provider}/${model.id}`;
    if (seen.has(key)) return;
    seen.add(key);
    candidates.push(model);
  };

  add(ctx.model);
  for (const model of ctx.modelRegistry.getAvailable()) add(model);
  for (const model of ctx.modelRegistry.getAll()) add(model);
  return candidates;
}

async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error(
        `Timed out after ${Math.round(timeoutMs / 1000)}s while fetching Codex usage.`,
      );
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

function normalizeBackendPayload(
  payload: RateLimitStatusPayload,
  capturedAt: number,
  source: UsageSource,
): CodexUsageReport {
  const snapshots: NormalizedRateLimitSnapshot[] = [];
  const planType = asString(payload.plan_type);
  const primary = normalizeBackendSnapshot("codex", undefined, payload.rate_limit, payload.credits);
  const spendControl =
    payload.spend_control && typeof payload.spend_control === "object" && !Array.isArray(payload.spend_control)
      ? (payload.spend_control as Record<string, unknown>)
      : undefined;
  const individualLimit = normalizeIndividualLimit(
    payload.individual_limit ??
      payload.individualLimit ??
      spendControl?.individual_limit ??
      spendControl?.individualLimit,
  );
  if (primary && individualLimit && !primary.primary) {
    primary.primary = individualLimit;
  }
  if (primary) snapshots.push(primary);

  const additional = Array.isArray(payload.additional_rate_limits)
    ? payload.additional_rate_limits
    : [];
  for (const item of additional) {
    const additionalLimit = assertObject(
      item,
      "additional rate limit",
    ) as BackendAdditionalRateLimit;
    const limitId =
      asString(additionalLimit.metered_feature) ?? asString(additionalLimit.limit_name);
    if (!limitId) continue;
    const snapshot = normalizeBackendSnapshot(
      limitId,
      asString(additionalLimit.limit_name),
      additionalLimit.rate_limit,
      undefined,
    );
    if (snapshot) snapshots.push(snapshot);
  }

  if (snapshots.length === 0) {
    throw new Error("Codex usage endpoint returned no displayable rate-limit windows.");
  }

  return { source, capturedAt, planType, snapshots };
}

function normalizeBackendSnapshot(
  limitId: string,
  limitName: string | undefined,
  rateLimit: unknown,
  credits: unknown,
): NormalizedRateLimitSnapshot | undefined {
  if (rateLimit === null || rateLimit === undefined) {
    const normalizedCredits = normalizeBackendCredits(credits);
    return normalizedCredits ? { limitId, limitName, credits: normalizedCredits } : undefined;
  }

  const details = assertObject(rateLimit, "rate limit") as BackendRateLimitDetails;
  const individualLimit = normalizeIndividualLimit(
    details.individual_limit ?? details.individualLimit,
  );
  const primary = normalizeBackendWindow(details.primary_window) ?? individualLimit;
  const secondary = normalizeBackendWindow(details.secondary_window);
  const normalizedCredits = normalizeBackendCredits(credits);

  if (!primary && !secondary && !normalizedCredits) return undefined;
  return { limitId, limitName, primary, secondary, credits: normalizedCredits };
}

function normalizeIndividualLimit(value: unknown): NormalizedRateLimitWindow | undefined {
  if (value === null || value === undefined) return undefined;
  const limit = assertObject(value, "individual limit");
  const remainingPercent = asNumber(limit.remaining_percent ?? limit.remainingPercent);
  const usedPercent = asNumber(limit.used_percent ?? limit.usedPercent) ??
    (remainingPercent === undefined ? undefined : 100 - clampPercent(remainingPercent));
  if (usedPercent === undefined) return undefined;
  return {
    usedPercent: clampPercent(usedPercent),
    used: asNumber(limit.used),
    limit: asNumber(limit.limit),
    windowLabel: "individual",
    resetsAt: asNumber(limit.reset_at ?? limit.resetAt),
  };
}

function normalizeBackendWindow(value: unknown): NormalizedRateLimitWindow | undefined {
  if (value === null || value === undefined) return undefined;
  const window = assertObject(value, "rate-limit window") as BackendWindowSnapshot;
  const usedPercent = asNumber(window.used_percent);
  if (usedPercent === undefined) return undefined;
  const limitSeconds = asNumber(window.limit_window_seconds);
  const resetsAt = asNumber(window.reset_at);
  return {
    usedPercent,
    windowMinutes: limitSeconds && limitSeconds > 0 ? Math.ceil(limitSeconds / 60) : undefined,
    resetsAt,
  };
}

function normalizeBackendCredits(value: unknown): NormalizedCredits | undefined {
  if (value === null || value === undefined) return undefined;
  const credits = assertObject(value, "credits") as BackendCreditsSnapshot;
  const hasCredits = asBoolean(credits.has_credits);
  const unlimited = asBoolean(credits.unlimited);
  if (hasCredits === undefined || unlimited === undefined) return undefined;
  return { hasCredits, unlimited, balance: asString(credits.balance) };
}

function formatCodexUsageReport(report: CodexUsageReport, _cacheAgeMs?: number): string {
  const lines = [
    "  >_ OpenAI Codex Usage",
    "",
    `Visit ${USAGE_SETTINGS_URL} for up-to-date`,
    "information on rate limits and credits",
    "",
  ];

  for (const snapshot of report.snapshots) {
    const label = snapshot.limitName ?? snapshot.limitId;
    if (!isPrimaryCodexSnapshot(snapshot)) {
      lines.push(`  ${label} limit:`);
    }
    if (snapshot.primary) lines.push(formatWindowLine(`${formatWindowLabel(snapshot.primary)} limit:`, snapshot.primary));
    if (snapshot.secondary) lines.push(formatWindowLine(`${formatWindowLabel(snapshot.secondary)} limit:`, snapshot.secondary));
    if (!snapshot.primary && !snapshot.secondary) {
      lines.push("  Limits unavailable for this account");
    }
  }

  return lines.join("\n");
}

function formatCodexUsageStatusline(report: CodexUsageReport, model?: CodexUsageModel): string {
  const snapshot = selectSnapshotForModel(report, model);
  if (!snapshot) return "📊 usage unavailable";

  const parts = [`📊 ${formatStatuslinePrefix(snapshot)}`];
  if (snapshot.primary) parts.push(formatWindowStatus(snapshot.primary));
  if (snapshot.secondary) parts.push(formatWindowStatus(snapshot.secondary));
  if (parts.length === 1 && snapshot.credits) parts.push(formatCredits(snapshot.credits));
  return parts.join(" ");
}

function selectSnapshotForModel(
  report: CodexUsageReport,
  model: CodexUsageModel | undefined,
): NormalizedRateLimitSnapshot | undefined {
  const codexSnapshot = report.snapshots.find(isPrimaryCodexSnapshot);
  if (!model || !isOpenAICodexModel(model)) return codexSnapshot ?? report.snapshots[0];

  const modelKeys = normalizedModelUsageKeys(model);
  const exactMatch = report.snapshots.find((snapshot) =>
    normalizedSnapshotUsageKeys(snapshot).some((key) => modelKeys.has(key)),
  );
  if (exactMatch) return exactMatch;

  const variants = codexModelVariantKeys(modelKeys);
  for (const variant of variants) {
    const matches = report.snapshots.filter(
      (snapshot) =>
        !isPrimaryCodexSnapshot(snapshot) &&
        normalizedSnapshotUsageKeys(snapshot).some((key) => normalizedKeyHasToken(key, variant)),
    );
    if (matches.length === 1) return matches[0];
  }

  return codexSnapshot ?? report.snapshots[0];
}

function normalizedModelUsageKeys(model: CodexUsageModel): Set<string> {
  const keys = new Set<string>();
  addNormalizedUsageKey(keys, model.id);
  addNormalizedUsageKey(keys, model.name);

  for (const key of [...keys]) {
    const codexIndex = key.indexOf("codex");
    if (codexIndex >= 0) keys.add(key.slice(codexIndex));
  }

  return keys;
}

function normalizedSnapshotUsageKeys(snapshot: NormalizedRateLimitSnapshot): string[] {
  return [normalizedUsageKey(snapshot.limitId), normalizedUsageKey(snapshot.limitName)].filter(
    (key): key is string => key !== undefined,
  );
}

function addNormalizedUsageKey(keys: Set<string>, value: string | undefined): void {
  const key = normalizedUsageKey(value);
  if (key) keys.add(key);
}

function normalizedUsageKey(value: string | undefined): string | undefined {
  const key = value
    ?.toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return key || undefined;
}

function codexModelVariantKeys(modelKeys: Set<string>): string[] {
  const variants = new Set<string>();
  for (const key of modelKeys) {
    const match = key.match(/(?:^|-)codex-(.+)$/);
    if (match?.[1]) variants.add(match[1]);
  }
  return [...variants];
}

function normalizedKeyHasToken(key: string, token: string): boolean {
  return (
    key === token ||
    key.startsWith(`${token}-`) ||
    key.endsWith(`-${token}`) ||
    key.includes(`-${token}-`)
  );
}

function formatStatuslinePrefix(snapshot: NormalizedRateLimitSnapshot): string {
  if (isPrimaryCodexSnapshot(snapshot)) return "codex";
  const label = snapshot.limitName ?? snapshot.limitId;
  return `codex ${compactLimitLabel(label)}`;
}

function compactLimitLabel(label: string): string {
  const normalized = label.replace(/[_-]+/g, " ").trim();
  const codexVariant = normalized.match(/\bcodex\s+(.+)$/i)?.[1]?.trim();
  const compact = codexVariant || normalized;
  return compact.toLowerCase().replace(/\s+/g, " ");
}

function formatWindowStatus(window: NormalizedRateLimitWindow): string {
  const parts = [formatRemainingPercent(window), formatWindowLabel(window)];
  const requestUsage = formatRequestUsage(window);
  if (requestUsage) parts.unshift(`${requestUsage} requests`);
  if (window.resetsAt) parts.push(`resets ${formatReset(window.resetsAt)}`);
  return parts.join(" ");
}

function formatRemainingPercent(window: NormalizedRateLimitWindow): string {
  return `${(100 - clampPercent(window.usedPercent)).toFixed(0)}%`;
}

function formatRequestUsage(window: NormalizedRateLimitWindow): string | undefined {
  if (window.used === undefined || window.limit === undefined) return undefined;
  return `${formatNumber(window.used, "?")}/${formatNumber(window.limit, "?")}`;
}

function showReport(
  ctx: ExtensionCommandContext,
  report: CodexUsageReport,
  fromCache: boolean,
): void {
  const text = formatCodexUsageReport(
    report,
    fromCache ? Date.now() - report.capturedAt : undefined,
  );
  ctx.ui.notify(ctx.hasUI ? brightenInfoNotification(text) : text, "info");
}

function brightenInfoNotification(text: string): string {
  return `${RESET_FOREGROUND}${text}`;
}

function isPrimaryCodexSnapshot(snapshot: NormalizedRateLimitSnapshot): boolean {
  return (
    normalizedUsageKey(snapshot.limitId) === "codex" ||
    normalizedUsageKey(snapshot.limitName) === "codex"
  );
}

function formatWindowLabel(window: NormalizedRateLimitWindow): string {
  if (window.windowLabel) return window.windowLabel;
  if (window.windowMinutes === 5 * 60) return "5h";
  if (window.windowMinutes === 7 * 24 * 60) return "Weekly";
  if (window.windowMinutes && window.windowMinutes % (24 * 60) === 0) {
    return `${window.windowMinutes / (24 * 60)}d`;
  }
  if (window.windowMinutes && window.windowMinutes % 60 === 0) {
    return `${window.windowMinutes / 60}h`;
  }
  return "window";
}

function formatWindowLine(label: string, window: NormalizedRateLimitWindow): string {
  return `  ${label.padEnd(LIMIT_VALUE_COLUMN)}${formatWindow(window)}`;
}

function formatWindow(window: NormalizedRateLimitWindow): string {
  const remaining = 100 - clampPercent(window.usedPercent);
  const requestUsage = formatRequestUsage(window);
  const usage = requestUsage ? `${requestUsage} requests, ` : "";
  const reset = window.resetsAt ? ` (resets ${formatReset(window.resetsAt)})` : "";
  return `${progressBar(remaining)} ${usage}${remaining.toFixed(0)}% left${reset}`;
}

function progressBar(percentRemaining: number): string {
  const filled = Math.round((clampPercent(percentRemaining) / 100) * BAR_SEGMENTS);
  return `[${"█".repeat(filled)}${"░".repeat(BAR_SEGMENTS - filled)}]`;
}

function formatCredits(credits: NormalizedCredits): string {
  if (!credits.hasCredits) return "no credits";
  if (credits.unlimited) return "unlimited credits";
  const balance = credits.balance?.trim();
  if (!balance) return "credits available";
  return `${formatNumber(Number(balance), balance)} credits`;
}

function formatReset(epochSeconds: number): string {
  const reset = new Date(epochSeconds * 1000);
  if (Number.isNaN(reset.getTime())) return "at an unknown time";

  const now = new Date();
  const time = `${reset.getHours().toString().padStart(2, "0")}:${reset
    .getMinutes()
    .toString()
    .padStart(2, "0")}`;
  if (reset.toDateString() === now.toDateString()) return time;
  const day = reset.getDate().toString();
  const month = reset.toLocaleDateString(undefined, { month: "short" });
  return `${time} on ${day} ${month}`;
}

function formatQueryErrors(errors: UsageQueryError[]): string {
  const lines = ["Unable to read Codex usage."];
  for (const error of errors) {
    lines.push(`- Pi auth direct: ${error.message}`);
  }
  lines.push("");
  lines.push("Tip: use a Pi OpenAI Codex model or run /login to configure Codex subscription auth.");
  return lines.join("\n");
}

function formatNumber(value: number, fallback: string): string {
  if (!Number.isFinite(value)) return fallback;
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value);
}

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(100, Math.max(0, value));
}

function parseJsonObject(text: string, description: string): Record<string, unknown> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text) as unknown;
  } catch (error) {
    throw new Error(`${description} was not valid JSON: ${errorMessage(error)}`);
  }
  return assertObject(parsed, description);
}

function assertObject(value: unknown, description: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${description} was not an object.`);
  }
  return value as Record<string, unknown>;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function asNumber(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

function asBoolean(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function hasHeader(headers: Record<string, string>, name: string): boolean {
  return Object.keys(headers).some((key) => key.toLowerCase() === name.toLowerCase());
}

function redactErrorBody(body: string): string {
  return truncateEnd(
    body
      .replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/gi, "Bearer <redacted>")
      .replace(/"access_token"\s*:\s*"[^"]+"/gi, '"access_token":"<redacted>"')
      .trim(),
    MAX_ERROR_BODY_CHARS,
  );
}

function truncateEnd(value: string, maxChars: number): string {
  if (value.length <= maxChars) return value;
  return `${value.slice(0, maxChars - 1)}…`;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
