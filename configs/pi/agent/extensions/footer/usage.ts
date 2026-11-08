import type { ExtensionContext } from "@earendil-works/pi-coding-agent";

export type Limit = { label: string; used: number; reset?: number; window: number; kind?: "subscription" | "throughput" };
export type UsageSnapshot = { limits: Limit[]; source: string; message?: string; url?: string; capturedAt: number };
const clamp = (n: number) => Math.max(0, Math.min(100, n));
const num = (value: unknown): number | undefined => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value)) ? Number(value) : undefined;
const epoch = (value: unknown) => {
  const n = num(value);
  if (n !== undefined) return n;
  const t = typeof value === "string" ? Date.parse(value) / 1000 : NaN;
  return Number.isFinite(t) ? t : undefined;
};
const label = (seconds: number) => seconds % 86400 === 0 ? `${seconds / 86400}d` : seconds % 3600 === 0 ? `${seconds / 3600}h` : `${seconds / 60}m`;
function duration(value: string | undefined) {
  if (!value || !/^(?:\d+(?:\.\d+)?(?:ms|s|m|h|d))+$/.test(value)) return undefined;
  return [...value.matchAll(/(\d+(?:\.\d+)?)(ms|s|m|h|d)/g)].reduce((sum, m) => sum + Number(m[1]) * ({ ms: .001, s: 1, m: 60, h: 3600, d: 86400 }[m[2]] ?? 0), 0);
}

export function fromHeaders(headers: Record<string, string>, now = Date.now() / 1000): Limit[] {
  const h = Object.fromEntries(Object.entries(headers).map(([k, v]) => [k.toLowerCase(), v]));
  const subscription: Limit[] = [];
  for (const [key, seconds] of [["5h", 18000], ["7d", 604800]] as const) {
    const used = num(h[`anthropic-ratelimit-unified-${key}-utilization`]);
    if (used !== undefined) subscription.push({ label: key, used: clamp(used * 100), reset: epoch(h[`anthropic-ratelimit-unified-${key}-reset`]), window: seconds });
  }
  for (const key of ["primary", "secondary"]) {
    const used = num(h[`x-codex-${key}-used-percent`]);
    if (used === undefined) continue;
    const seconds = (num(h[`x-codex-${key}-window-minutes`]) ?? (key === "primary" ? 300 : 10080)) * 60;
    if (seconds > 0) subscription.push({ label: label(seconds), used: clamp(used), reset: epoch(h[`x-codex-${key}-reset-at`]), window: seconds });
  }
  if (subscription.length) return subscription.slice(0, 2);
  // API throughput is deliberately labeled differently from plan quotas.
  const throughput: Limit[] = [];
  for (const [key, name] of [["requests", "req"], ["tokens", "tok"]]) {
    for (const prefix of ["x-ratelimit", "anthropic-ratelimit"]) {
      const maximum = num(h[`${prefix}-limit-${key}`] ?? h[`${prefix}-${key}-limit`]);
      const remaining = num(h[`${prefix}-remaining-${key}`] ?? h[`${prefix}-${key}-remaining`]);
      if (maximum === undefined || maximum <= 0 || remaining === undefined) continue;
      const raw = h[`${prefix}-reset-${key}`] ?? h[`${prefix}-${key}-reset`];
      const seconds = duration(raw);
      throughput.push({ label: name, used: clamp((1 - remaining / maximum) * 100), reset: seconds !== undefined ? now + seconds : epoch(raw), window: 60, kind: "throughput" });
      break;
    }
  }
  return throughput;
}

type Json = Record<string, any>;
export function fromPayload(payload: Json): Limit[] {
  const bucket = payload.rateLimitsByLimitId?.codex ?? payload.rateLimits ?? payload.rate_limits ?? payload.rate_limit ?? payload;
  const limits: Limit[] = [];
  for (const [key, fallback] of [["primary", 18000], ["secondary", 604800]] as const) {
    const w = bucket[key] ?? bucket[`${key}_window`];
    if (!w) continue;
    const used = num(w.usedPercent ?? w.used_percent);
    const seconds = num(w.limit_window_seconds) ?? (num(w.windowDurationMins) ?? fallback / 60) * 60;
    if (used === undefined || seconds <= 0) continue;
    limits.push({ label: label(seconds), used: clamp(used), reset: epoch(w.resetsAt ?? w.reset_at), window: seconds });
  }
  for (const [key, seconds] of [["five_hour", 18000], ["seven_day", 604800]] as const) {
    const w = payload[key];
    const used = num(w?.utilization);
    if (used !== undefined) limits.push({ label: label(seconds), used: clamp(used), reset: epoch(w.resets_at), window: seconds });
  }
  return limits.slice(0, 2);
}

export interface UsageAdapter {
  id: string;
  matches(ctx: ExtensionContext): boolean;
  endpoint: string;
  url: string;
  headers?: Record<string, string>;
}
// Endpoint credentials only go to these fixed provider origins, never a model's proxy URL.
export const adapters: UsageAdapter[] = [
  { id: "openai", matches: ctx => ["openai", "openai-codex"].includes(ctx.model?.provider ?? ""), endpoint: "https://chatgpt.com/backend-api/wham/usage", url: "https://chatgpt.com/settings/usage" },
  { id: "anthropic", matches: ctx => ctx.model?.provider === "anthropic", endpoint: "https://api.anthropic.com/api/oauth/usage", url: "https://claude.ai/settings/usage", headers: { "anthropic-beta": "oauth-2025-04-20" } },
];

export class UsageMonitor {
  private snapshots = new Map<string, UsageSnapshot>();
  private nextPoll = new Map<string, number>();
  private pending = new Set<string>();
  private abort = new AbortController();
  private stopped = false;
  constructor(private changed: () => void, private request: typeof fetch = fetch) {}
  private key(ctx: ExtensionContext) {
    return `${ctx.model?.provider ?? ""}:${ctx.model?.baseUrl ?? ""}:${ctx.model?.id ?? ""}`;
  }
  get(ctx: ExtensionContext): UsageSnapshot {
    const found = this.snapshots.get(this.key(ctx));
    const now = Date.now() / 1000;
    if (found && now - found.capturedAt <= 300) {
      const limits = found.limits.filter(l => !l.reset || l.reset > now);
      if (limits.length || !found.limits.length) return { ...found, limits };
    }
    return { limits: [], source: "none", capturedAt: now, message: "Usage not reported", url: adapters.find(a => a.matches(ctx))?.url };
  }
  observeHeaders(ctx: ExtensionContext, headers: Record<string, string>) {
    this.observe(ctx, fromHeaders(headers), "response headers");
  }
  observeStream(ctx: ExtensionContext, data: unknown) {
    if (!data || typeof data !== "object") return;
    const event = data as Json;
    if (event.type === "codex.rate_limits" || event.type === "account/rateLimits/updated" || event.method === "account/rateLimits/updated") {
      this.observe(ctx, fromPayload(event.params ?? event), "provider stream");
    }
  }
  private observe(ctx: ExtensionContext, limits: Limit[], source: string) {
    if (!limits.length || this.stopped) return;
    const previous = this.snapshots.get(this.key(ctx));
    if (limits.every(l => l.kind === "throughput") && previous?.limits.some(l => l.kind !== "throughput") && Date.now() / 1000 - previous.capturedAt < 300) return;
    this.snapshots.set(this.key(ctx), { limits, source, capturedAt: Date.now() / 1000 });
    this.changed();
  }
  async poll(ctx: ExtensionContext, force = false) {
    // Freeze model identity across auth/network awaits; the UI may switch models meanwhile.
    ctx = { ...ctx, model: ctx.model };
    const key = this.key(ctx), now = Date.now();
    const adapter = adapters.find(a => a.matches(ctx));
    if (this.stopped || !adapter || this.pending.has(key) || (!force && now < (this.nextPoll.get(key) ?? 0))) return;
    // Do not send API keys to subscription endpoints or borrow another app's login.
    if (!ctx.model || !ctx.modelRegistry.isUsingOAuth(ctx.model)) return;
    let base = "";
    try { base = new URL(ctx.model.baseUrl).hostname; } catch { return; }
    if (adapter.id === "openai" && !["api.openai.com", "chatgpt.com"].includes(base)) return;
    if (adapter.id === "anthropic" && base !== "api.anthropic.com") return;
    this.pending.add(key);
    this.nextPoll.set(key, now + 60000);
    try {
      const resolved = await ctx.modelRegistry.getProviderAuth(ctx.model.provider);
      if (this.stopped || !resolved?.auth.apiKey) return;
      if (resolved.auth.baseUrl && new URL(resolved.auth.baseUrl).hostname !== base) return;
      const headers: Record<string, string> = { ...adapter.headers, Authorization: `Bearer ${resolved.auth.apiKey}` };
      // Preserve workspace selection, but never forward arbitrary inference headers.
      for (const [name, value] of Object.entries(resolved.auth.headers ?? {})) {
        if (name.toLowerCase() === "chatgpt-account-id" && typeof value === "string") headers["ChatGPT-Account-Id"] = value;
      }
      if (adapter.id === "openai" && !headers["ChatGPT-Account-Id"]) {
        try {
          const claims = JSON.parse(Buffer.from(resolved.auth.apiKey.split(".")[1], "base64url").toString());
          const id = claims["https://api.openai.com/auth"]?.chatgpt_account_id;
          if (typeof id === "string") headers["ChatGPT-Account-Id"] = id;
        } catch { /* Not all access tokens are JWTs. */ }
      }
      const response = await this.request(adapter.endpoint, { headers, redirect: "error", signal: AbortSignal.any([this.abort.signal, AbortSignal.timeout(10000)]) });
      if (this.stopped) return;
      if (!response.ok) {
        const message = response.status === 401 || response.status === 403
          ? "Usage API denied this login" : `Usage API HTTP ${response.status}`;
        this.nextPoll.set(key, now + (response.status === 401 || response.status === 403 ? 15 * 60000 : response.status === 429 ? 5 * 60000 : 120000));
        const old = this.get(ctx);
        if (!old.limits.length) this.snapshots.set(key, { limits: [], source: adapter.id, capturedAt: Date.now() / 1000, message, url: adapter.url });
        await response.body?.cancel();
      } else {
        const limits = fromPayload(await response.json());
        if (limits.length) this.observe(ctx, limits, `${adapter.id} usage API`);
        else if (!this.get(ctx).limits.length) this.snapshots.set(key, { limits: [], source: adapter.id, capturedAt: Date.now() / 1000, message: "Usage API returned no windows", url: adapter.url });
      }
      this.changed();
    } catch {
      if (!this.stopped) {
        this.nextPoll.set(key, now + 120000);
        if (!this.get(ctx).limits.length) this.snapshots.set(key, { limits: [], source: adapter.id, capturedAt: Date.now() / 1000, message: "Usage API unavailable", url: adapter.url });
        this.changed();
      }
    } finally { this.pending.delete(key); }
  }
  dispose() { this.stopped = true; this.abort.abort(); }
}
