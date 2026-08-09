/**
 * GitHub Copilot quota tracking.
 *
 * Companion to codex-usage.ts: fetches quota info for the github-copilot
 * provider and emits it over pi.events so footer.ts can render it, the same
 * way it renders Codex 5h/weekly limits.
 *
 * Endpoint and response shape based on
 * https://github.com/slkiser/opencode-quota (src/lib/copilot.ts,
 * `queryCopilotQuota`'s OAuth path). See resolveCopilotOAuthToken() below for
 * which stored credential this actually needs — it's the non-obvious part.
 */
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { appendFileSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const COPILOT_PROVIDER_ID = "github-copilot";
const COPILOT_USER_URL = "https://api.github.com/copilot_internal/user";
const GITHUB_API_VERSION = "2022-11-28";
const CACHE_TTL_MS = 5 * 60 * 1000;
const FETCH_TIMEOUT_MS = 8_000;
const DEBUG_LOG_PATH = join(homedir(), ".pi", "agent", "copilot-usage-debug.log");
const DEBUG_LOG_MAX_BYTES = 512 * 1024;

export const COPILOT_USAGE_UPDATE_EVENT = "copilot-usage:update";
export const COPILOT_USAGE_REQUEST_EVENT = "copilot-usage:request";

const REQUEST_HEADERS: Record<string, string> = {
  Accept: "application/vnd.github+json",
  "X-GitHub-Api-Version": GITHUB_API_VERSION,
  "User-Agent": "pi-copilot-usage",
};

export type CopilotQuotaCategory = {
  entitlement?: number;
  remaining?: number;
  percentRemaining?: number;
  unlimited?: boolean;
  overagePermitted?: boolean;
};

export type CopilotQuotaReport = {
  capturedAt: number;
  resetDate?: string;
  chat?: CopilotQuotaCategory;
  completions?: CopilotQuotaCategory;
  premiumInteractions?: CopilotQuotaCategory;
};

export type CopilotUsageUpdate = {
  report: CopilotQuotaReport;
};

type CachedReport = {
  createdAt: number;
  report: CopilotQuotaReport;
};

type PiModel = NonNullable<ExtensionContext["model"]>;

function isCopilotModel(model: Pick<PiModel, "provider"> | undefined): boolean {
  return model?.provider === COPILOT_PROVIDER_ID;
}

// Debug logging goes to a file rather than console.log/ctx.ui.notify because
// the footer render loop runs during normal TUI operation — writing to
// stdout/stderr there would corrupt the terminal UI. Tail this file to see
// what's happening: `tail -f ~/.pi/agent/copilot-usage-debug.log`
function debugLog(message: string): void {
  const line = `[${new Date().toISOString()}] ${message}\n`;
  try {
    rotateDebugLogIfLarge();
    appendFileSync(DEBUG_LOG_PATH, line, "utf-8");
  } catch {
    // Logging must never break the extension itself.
  }
}

// This log runs for the lifetime of every session using a Copilot model, so
// without a cap it grows forever. Truncate instead of rotating to a numbered
// file — this is a debugging aid, not an audit trail.
function rotateDebugLogIfLarge(): void {
  try {
    if (statSync(DEBUG_LOG_PATH).size > DEBUG_LOG_MAX_BYTES) {
      writeFileSync(DEBUG_LOG_PATH, `[log truncated at ${new Date().toISOString()}]\n`, "utf-8");
    }
  } catch {
    // File doesn't exist yet; nothing to rotate.
  }
}

async function fetchWithTimeout(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

function toCategory(value: unknown): CopilotQuotaCategory | undefined {
  if (!value || typeof value !== "object") return undefined;
  const v = value as Record<string, unknown>;
  const remaining =
    typeof v.remaining === "number"
      ? v.remaining
      : typeof v.quota_remaining === "number"
        ? v.quota_remaining
        : undefined;
  const category: CopilotQuotaCategory = {
    entitlement: typeof v.entitlement === "number" ? v.entitlement : undefined,
    remaining,
    percentRemaining: typeof v.percent_remaining === "number" ? v.percent_remaining : undefined,
    unlimited: typeof v.unlimited === "boolean" ? v.unlimited : undefined,
    overagePermitted: typeof v.overage_permitted === "boolean" ? v.overage_permitted : undefined,
  };
  const hasData = Object.values(category).some((entry) => entry !== undefined);
  return hasData ? category : undefined;
}

// Fill in percentRemaining from entitlement/remaining when GitHub doesn't send
// an explicit percent_remaining field (mirrors opencode-quota's fallback math).
function withComputedPercent(category: CopilotQuotaCategory | undefined): CopilotQuotaCategory | undefined {
  if (!category) return undefined;
  if (category.percentRemaining !== undefined || category.unlimited) return category;
  if (category.entitlement == null || category.entitlement <= 0 || category.remaining == null) {
    return category;
  }
  const percentRemaining = Math.min(100, Math.floor((category.remaining * 100) / category.entitlement));
  return { ...category, percentRemaining };
}

// GitHub Copilot OAuth stores two tokens in auth.json: `access` (a short-lived
// Copilot proxy/session token, format "tid=...;exp=...;proxy-ep=...") used to
// call the model inference API, and `refresh` (a long-lived GitHub
// user-to-server OAuth token, format "ghu_...") used to mint new `access`
// tokens. `GET /copilot_internal/user` only accepts the `refresh` (ghu_)
// token — sending the `access` token gets a 401 "Bad credentials". This was
// verified directly against the live endpoint while debugging.
//
// `authStorage` used to be exposed on ModelRegistry, but was removed from the
// current Pi API. Read through ModelRuntime's credential store instead. This
// keeps credential-path handling inside Pi and avoids reading auth.json here.
type CredentialReader = {
  read(providerId: string): Promise<unknown>;
};

type RegistryWithCredentialReader = {
  runtime?: {
    credentials?: CredentialReader;
  };
};

async function resolveCopilotOAuthToken(ctx: ExtensionContext): Promise<string | undefined> {
  const registry = ctx.modelRegistry as unknown as RegistryWithCredentialReader;
  let credential: unknown;
  try {
    credential = await registry.runtime?.credentials?.read(COPILOT_PROVIDER_ID);
  } catch (error) {
    debugLog(`resolveCopilotOAuthToken: credential store read failed: ${errorMessage(error)}`);
    return undefined;
  }

  if (!credential || typeof credential !== "object") {
    debugLog("resolveCopilotOAuthToken: no github-copilot credential in Pi credential store");
    return undefined;
  }
  const value = credential as { type?: unknown; refresh?: unknown };
  if (value.type !== "oauth") {
    debugLog(`resolveCopilotOAuthToken: github-copilot credential type is "${String(value.type)}", expected oauth`);
    return undefined;
  }
  if (typeof value.refresh !== "string" || !value.refresh) {
    debugLog("resolveCopilotOAuthToken: oauth credential has no refresh token");
    return undefined;
  }
  return value.refresh;
}

async function fetchReport(ctx: ExtensionContext): Promise<CopilotQuotaReport | undefined> {
  const oauthToken = await resolveCopilotOAuthToken(ctx);
  if (!oauthToken) return undefined;

  let response: Response;
  try {
    response = await fetchWithTimeout(
      COPILOT_USER_URL,
      {
        headers: {
          ...REQUEST_HEADERS,
          Authorization: `Bearer ${oauthToken}`,
        },
      },
      FETCH_TIMEOUT_MS,
    );
  } catch (error) {
    debugLog(`fetchReport: request to ${COPILOT_USER_URL} threw: ${errorMessage(error)}`);
    return undefined;
  }

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    debugLog(
      `fetchReport: ${COPILOT_USER_URL} returned ${response.status} ${response.statusText}: ${body.slice(0, 300)}`,
    );
    return undefined;
  }

  const raw = (await response.json().catch((error) => {
    debugLog(`fetchReport: response body was not valid JSON: ${errorMessage(error)}`);
    return undefined;
  })) as Record<string, unknown> | undefined;
  if (!raw) return undefined;

  const snapshots = raw.quota_snapshots;
  const s = snapshots && typeof snapshots === "object" ? (snapshots as Record<string, unknown>) : undefined;

  const resetDate =
    typeof raw.quota_reset_date_utc === "string"
      ? raw.quota_reset_date_utc
      : typeof raw.quota_reset_date === "string"
        ? raw.quota_reset_date
        : undefined;

  const report: CopilotQuotaReport = {
    capturedAt: Date.now(),
    resetDate,
    chat: withComputedPercent(toCategory(s?.chat)),
    completions: withComputedPercent(toCategory(s?.completions)),
    premiumInteractions: withComputedPercent(toCategory(s?.premium_interactions)),
  };

  const hasAnyCategory = report.chat || report.completions || report.premiumInteractions;
  if (!hasAnyCategory) {
    debugLog(`fetchReport: response had no usable quota_snapshots. Raw keys: ${Object.keys(raw).join(", ")}`);
    return undefined;
  }

  debugLog(
    `fetchReport: ok. premium=${JSON.stringify(report.premiumInteractions)} chat=${JSON.stringify(report.chat)} completions=${JSON.stringify(report.completions)}`,
  );
  return report;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export default function copilotUsage(pi: ExtensionAPI) {
  let cache: CachedReport | undefined;
  let inFlight: Promise<CopilotQuotaReport | undefined> | undefined;

  const emitUpdate = (report: CopilotQuotaReport | undefined) => {
    const payload: CopilotUsageUpdate | undefined = report ? { report } : undefined;
    pi.events.emit(COPILOT_USAGE_UPDATE_EVENT, payload);
  };

  pi.events.on(COPILOT_USAGE_REQUEST_EVENT, () => {
    if (cache) emitUpdate(cache.report);
  });

  const refresh = async (ctx: ExtensionContext, force = false) => {
    if (!isCopilotModel(ctx.model)) {
      emitUpdate(undefined);
      return;
    }

    if (!force && cache && Date.now() - cache.createdAt < CACHE_TTL_MS) {
      emitUpdate(cache.report);
      return;
    }

    if (inFlight) {
      await inFlight;
      return;
    }

    debugLog(`refresh: fetching quota for model ${ctx.model?.provider}/${ctx.model?.id} (force=${force})`);
    inFlight = fetchReport(ctx).catch((error) => {
      debugLog(`refresh: fetchReport threw: ${errorMessage(error)}`);
      return undefined;
    });
    const report = await inFlight;
    inFlight = undefined;

    if (report) {
      cache = { createdAt: Date.now(), report };
      emitUpdate(report);
    } else if (cache) {
      // Keep serving stale data rather than blanking the footer on a transient error.
      emitUpdate(cache.report);
    } else {
      debugLog("refresh: no report and no cache — footer will show nothing for copilot quota");
    }
  };

  pi.on("session_start", (_event, ctx) => {
    void refresh(ctx);
  });

  pi.on("session_tree", (_event, ctx) => {
    void refresh(ctx);
  });

  pi.on("model_select", (event, ctx) => {
    if (isCopilotModel(event.model)) void refresh(ctx, false);
    else emitUpdate(undefined);
  });
}
