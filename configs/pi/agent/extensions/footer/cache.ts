type Model = { provider: string; id?: string; baseUrl?: string; api?: string; compat?: { supportsExplicitPromptCacheMode?: boolean } };
type Policy = { seconds?: number; description: string };
export type CacheRecord = Policy & { key: string; messageTimestamp: number; startedAt: number };
export const CACHE_ENTRY = "footer-cache-v1";
export const cacheKey = (model: Model) => JSON.stringify([model.provider, model.id, model.baseUrl ?? "", model.api ?? ""]);
const object = (value: unknown): Record<string, any> => value && typeof value === "object" ? value as Record<string, any> : {};
const ttl = (value: unknown) => value === "30m" ? 1800 : value === "12h" ? 43200 : undefined;

// Inspect only cache markers, never retain prompt text or credentials.
function markers(value: unknown, field: string): Record<string, any>[] {
  if (!value || typeof value !== "object") return [];
  if (Array.isArray(value)) return value.flatMap(item => markers(item, field));
  const node = object(value);
  return [...(node[field] ? [object(node[field])] : []), ...Object.entries(node)
    .filter(([key, child]) => key !== field && child && typeof child === "object")
    .flatMap(([, child]) => markers(child, field))];
}

export function cachePolicy(model: Model, payload: unknown): Policy {
  const p = object(payload);
  let origin = "";
  try { origin = new URL(model.baseUrl ?? "").origin; } catch { /* Unknown endpoints have no verified retention semantics. */ }
  if (origin === "https://api.openai.com" && model.api === "openai-responses") {
    const options = object(p.prompt_cache_options);
    if (model.compat?.supportsExplicitPromptCacheMode) {
      const breakpoints = markers(p, "prompt_cache_breakpoint");
      if (options.mode === "explicit" && !breakpoints.length) return { description: "Explicit-only caching without breakpoints; no cache writes requested" };
      const durations = [options.ttl === undefined ? 1800 : ttl(options.ttl), ...breakpoints.map(b => ttl(b.ttl ?? options.ttl ?? "30m"))];
      // Reads refresh only 30 minutes, even when the original write used 12h.
      return { seconds: durations.every(n => n !== undefined) ? Math.min(1800, ...durations as number[]) : undefined,
        description: `OpenAI minimum coverage; requested write TTL ${options.ttl ?? "30m"}; reads refresh 30m, entries may survive longer` };
    }
    return { description: p.prompt_cache_retention === "24h"
      ? "OpenAI extended retention: typically ~30m, up to 24h; exact expiry not exposed"
      : p.prompt_cache_retention === "in_memory"
        ? "OpenAI in-memory retention: typically 5–10m idle, up to 1h; exact expiry not exposed"
        : "OpenAI retention is model/organization dependent; exact expiry not exposed" };
  }
  return { description: "Provider/transport retention unknown; no verified expiry available" };
}

export class CacheTracker {
  private pending?: CacheRecord;
  observeRequest(model: Model | undefined, payload: unknown, now = Date.now()) {
    this.pending = model ? { ...cachePolicy(model, payload), key: cacheKey(model), startedAt: now, messageTimestamp: 0 } : undefined;
  }
  observeStream(data: unknown) {
    if (!this.pending?.seconds) return;
    const event = object(data);
    const usage = object(object(event.response).usage);
    const details = object(usage.input_tokens_details);
    const writes = object(details.cache_write_tokens_details);
    if (writes.ttl_12h_tokens > 0 && writes.ttl_30m_tokens === 0 && details.cached_tokens === 0) {
      this.pending.seconds = 43200;
      this.pending.description = "OpenAI reports exclusively 12h cache writes; minimum coverage, not a deletion deadline";
    }
  }
  finish(model: Model | undefined, message: any): CacheRecord | undefined {
    if (message.role !== "assistant") return;
    const pending = this.pending;
    this.pending = undefined;
    if (!model || !pending || pending.key !== cacheKey(model) || message.provider !== model.provider || message.model !== model.id
      || message.stopReason === "error" || message.stopReason === "aborted" || !Number.isFinite(message.timestamp)) return;
    return { ...pending, messageTimestamp: message.timestamp };
  }
}

export function cacheSummary(entries: readonly any[], model: Model | undefined, now = Date.now()) {
  if (!model) return undefined;
  let read = 0, prompt = 0;
  let latest: any;
  let record: CacheRecord | undefined;
  let warmedAt: number | undefined;
  for (const entry of entries) {
    if (entry.type === "message" && entry.message.role === "assistant") {
      const m = entry.message;
      if (m.provider !== model.provider || m.model !== model.id || m.stopReason === "error" || m.stopReason === "aborted") continue;
      const u = m.usage;
      const counts = [u?.input, u?.cacheRead, u?.cacheWrite];
      if (!counts.every(n => typeof n === "number" && Number.isFinite(n) && n >= 0)) continue;
      read += u.cacheRead;
      prompt += u.input + u.cacheRead + u.cacheWrite;
      latest = m;
      warmedAt = undefined;
    } else if (entry.type === "custom" && entry.customType === CACHE_ENTRY && entry.data?.key === cacheKey(model)) {
      record = entry.data;
    } else if (entry.type === "usage" && entry.source === "cache_warm" && entry.provider === model.provider && entry.model === model.id
      && (entry.usage?.cacheRead > 0 || entry.usage?.cacheWrite > 0)) {
      warmedAt = Date.parse(entry.timestamp);
    }
  }
  if (!latest || prompt <= 0) return undefined;
  const ratio = Math.floor(read / prompt * 100);
  const cached = latest.usage.cacheRead + latest.usage.cacheWrite > 0 || warmedAt !== undefined;
  const matched = record?.messageTimestamp === latest.timestamp ? record : undefined;
  // A cache-warmer usage entry has no request start or endpoint: do not fabricate a refreshed deadline.
  const expiresAt = cached && warmedAt === undefined && matched?.seconds && Number.isFinite(matched.seconds) && matched.seconds > 0 && Number.isFinite(matched.startedAt)
    ? matched.startedAt + matched.seconds * 1000 : undefined;
  const remaining = expiresAt === undefined ? undefined : Math.max(0, Math.floor((expiresAt - now) / 1000));
  const state = !cached ? "miss" : remaining === 0 ? "TTL elapsed" : remaining === undefined ? "TTL ?"
    : `~${remaining >= 3600 ? `${Math.floor(remaining / 3600)}h${Math.floor(remaining % 3600 / 60)}m` : remaining >= 60 ? `${Math.floor(remaining / 60)}m` : `${remaining}s`}`;
  return { ratio, state, remaining, description: warmedAt !== undefined
    ? "Cache warming reported reuse; refreshed expiry unavailable"
    : matched?.description ?? "Historical usage has no recorded request TTL/endpoint; expiry unknown" };
}
