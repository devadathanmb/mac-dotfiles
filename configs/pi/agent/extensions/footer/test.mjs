import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import { join, dirname } from "node:path";

// PI_PACKAGE points to the installed @earendil-works/pi-coding-agent directory.
const root = process.env.PI_PACKAGE;
assert.ok(root, "Set PI_PACKAGE to Pi's installed package directory");
const require = createRequire(join(root, "package.json"));
const { createJiti } = require("jiti");
const tuiPath = require.resolve("@earendil-works/pi-tui");
const { visibleWidth } = await import(pathToFileURL(tuiPath));
const jiti = createJiti(import.meta.url, { alias: { "@earendil-works/pi-tui": tuiPath } });
const { default: extension } = await jiti.import(join(dirname(new URL(import.meta.url).pathname), "index.ts"));
const events = new Map();
let component;
let context = { tokens: 430000, percent: 43, contextWindow: 1000000 };
let entries = [{ type: "message", message: { role: "assistant", provider: "anthropic", model: "opus", timestamp: Date.now(), usage: { input: 100, cacheRead: 9900, cacheWrite: 0, cost: { total: 18.05 } } } }];
const api = {
  on: (name, fn) => events.set(name, fn),
  registerCommand() {},
  appendEntry: (customType, data) => entries.push({ type: "custom", customType, data }),
  registerShortcut() {},
  getThinkingLevel: () => "medium",
  exec: async (_cmd, args) => ({ code: 0, stdout: args.includes("status") ? "## redesign...origin/redesign [ahead 1]\n M index.ts\n" : "1483\t0\tindex.ts\n" }),
};
const ctx = {
  mode: "tui", cwd: "/Users/example/repos/nokku",
  model: { name: "Opus 5.5", id: "opus", provider: "anthropic", api: "anthropic-messages", baseUrl: "https://api.anthropic.com", contextWindow: 1000000 },
  modelRegistry: { isUsingOAuth: () => false },
  getContextUsage: () => context,
  sessionManager: {
    getEntries: () => entries, getBranch: () => entries, getLeafId: () => String(entries.length),
    getHeader: () => ({ timestamp: new Date(Date.now() - 79 * 60000).toISOString() }),
  },
  ui: { setFooter: factory => { component = factory({ requestRender() {} }, {}, {
    onBranchChange: () => () => {}, getGitBranch: () => "redesign",
    getExtensionStatuses: () => new Map(),
  }); } },
};
const plain = s => s.replace(/\x1b\[[0-9;]*m/g, "");
extension(api);
await events.get("session_start")({}, ctx);
await new Promise(resolve => setTimeout(resolve, 10));
try {
  await events.get("after_provider_response")({ headers: {
    "anthropic-ratelimit-unified-5h-utilization": "0.41",
    "anthropic-ratelimit-unified-5h-reset": String(Math.floor(Date.now() / 1000 + 15060)),
    "anthropic-ratelimit-unified-7d-utilization": "0.5",
    "anthropic-ratelimit-unified-7d-reset": String(Math.floor(Date.now() / 1000 + 172800)),
  } }, ctx);
  const full = component.render(180).map(plain);
  assert.match(full[0], /cache 99% TTL \?/);
  assert.match(full[0], /◆ Opus 5.5 · medium/);
  assert.match(full[0], /43%.*430k\/1M.*cache 99%.*\$18.05.*1h19m/);
  assert.match(full[0], /5h.*41%/);
  assert.match(full[1], /redesign\* ↑1.*\+1483.*−0.*7d.*50%/);
  for (let width = 1; width <= 240; width++) {
    for (const line of component.render(width)) assert.ok(visibleWidth(line) <= width, `overflow at ${width}: ${plain(line)}`);
  }
  ctx.model = { name: "模型 😀", provider: "openai", contextWindow: 200000 };
  context = { tokens: null, percent: null, contextWindow: 200000 };
  entries = [];
  assert.doesNotMatch(component.render(180).map(plain).join("\n"), /5h|7d|cache|\$18/);
  assert.match(component.render(180).map(plain)[0], /\?%.*\?\/200k/);
  for (let width = 1; width <= 120; width++) {
    for (const line of component.render(width)) assert.ok(visibleWidth(line) <= width);
  }
  await events.get("after_provider_response")({ headers: { "x-codex-primary-used-percent": "25", "x-codex-primary-window-minutes": "300" } }, ctx);
  assert.match(component.render(180).map(plain)[0], /5h.*25%/);
  console.log(full.join("\n"));
  console.log("PASS: reference layout, 240 widths, Unicode, unknown context, provider switch, both header formats, cleanup");
} finally { component.dispose(); }

// Replacing the footer must not permanently stop the session-wide usage monitor.
await events.get("session_start")({}, ctx);
await events.get("after_provider_response")({ headers: { "x-codex-primary-used-percent": "35", "x-codex-primary-window-minutes": "300" } }, ctx);
assert.match(component.render(180).map(plain)[0], /5h.*35%/);
component.dispose();
events.get("session_shutdown")();

const { UsageMonitor, fromHeaders, fromPayload } = await jiti.import(join(dirname(new URL(import.meta.url).pathname), "usage.ts"));
const timestamp = Math.floor(Date.now() / 1000);
assert.deepEqual(fromPayload({ rate_limit: { primary_window: { used_percent: 32, limit_window_seconds: 18000, reset_at: timestamp + 600 } } }), [{ label: "5h", used: 32, reset: timestamp + 600, window: 18000 }]);
assert.equal(fromPayload({ rateLimitsByLimitId: { codex: { primary: { usedPercent: 12, windowDurationMins: 300 } } } })[0].used, 12);
assert.equal(fromPayload({ five_hour: { utilization: 45, resets_at: new Date((timestamp + 100) * 1000).toISOString() } })[0].reset, timestamp + 100);
assert.deepEqual(fromPayload({ rate_limit: { primary_window: { used_percent: "invalid" } } }), []);
assert.equal(fromHeaders({ "X-RateLimit-Limit-Requests": "100", "x-ratelimit-remaining-requests": "60", "x-ratelimit-reset-requests": "6m0s" }, timestamp)[0].reset, timestamp + 360);
assert.equal(fromHeaders({ "anthropic-ratelimit-tokens-limit": "1000", "anthropic-ratelimit-tokens-remaining": "200" })[0].kind, "throughput");
assert.equal(fromHeaders({ "x-ratelimit-limit-tokens": "0", "x-ratelimit-remaining-tokens": "0" }).length, 0);

const providerCtx = {
  model: { provider: "openai", id: "test", baseUrl: "https://api.openai.com/v1" },
  modelRegistry: { isUsingOAuth: () => true, getProviderAuth: async () => ({ auth: { apiKey: "test-token" } }) },
};
let calls = 0;
let monitor = new UsageMonitor(() => {}, async (url, init) => {
  calls++;
  assert.equal(url, "https://chatgpt.com/backend-api/wham/usage");
  assert.equal(init.headers.Authorization, "Bearer test-token");
  return new Response(JSON.stringify({ rate_limit: { primary_window: { used_percent: 20, limit_window_seconds: 18000, reset_at: timestamp + 600 } } }));
});
await Promise.all([monitor.poll(providerCtx), monitor.poll(providerCtx)]);
assert.equal(calls, 1, "deduplicate concurrent polling");
assert.equal(monitor.get(providerCtx).limits[0].used, 20);
await monitor.poll(providerCtx);
assert.equal(calls, 1, "poll interval respected");
monitor.observeHeaders(providerCtx, { "x-ratelimit-limit-requests": "10", "x-ratelimit-remaining-requests": "1" });
assert.equal(monitor.get(providerCtx).limits[0].label, "5h", "throughput cannot replace subscription quota");
monitor.observeStream(providerCtx, { type: "codex.rate_limits", rate_limits: { primary: { used_percent: 27, windowDurationMins: 300 } } });
assert.equal(monitor.get(providerCtx).limits[0].used, 27);
assert.equal(monitor.get({ ...providerCtx, model: { ...providerCtx.model, id: "other" } }).limits.length, 0);
monitor.dispose();

calls = 0;
monitor = new UsageMonitor(() => {}, async () => { calls++; return new Response("{}", { status: 401 }); });
await monitor.poll(providerCtx);
await monitor.poll(providerCtx);
assert.equal(calls, 1, "denied credentials back off");
assert.match(monitor.get(providerCtx).message, /denied this login/);
assert.equal(monitor.get(providerCtx).limits.length, 0, "denial is not zero usage");
monitor.dispose();

calls = 0;
monitor = new UsageMonitor(() => {}, async () => { calls++; throw new Error("must not request"); });
await monitor.poll({ ...providerCtx, modelRegistry: { isUsingOAuth: () => false } });
await monitor.poll({ ...providerCtx, model: { ...providerCtx.model, baseUrl: "https://proxy.example/v1" } });
await monitor.poll({ ...providerCtx, model: { ...providerCtx.model, baseUrl: "invalid" } });
assert.equal(calls, 0, "API keys, proxies and invalid URLs cannot trigger credential forwarding");
monitor.dispose();

let release;
const oldModel = providerCtx.model;
monitor = new UsageMonitor(() => {}, () => new Promise(resolve => { release = resolve; }));
const pending = monitor.poll(providerCtx);
await new Promise(resolve => setTimeout(resolve, 0));
providerCtx.model = { provider: "anthropic", id: "other", baseUrl: "https://api.anthropic.com" };
release(new Response(JSON.stringify({ rate_limit: { primary_window: { used_percent: 44, limit_window_seconds: 18000 } } })));
await pending;
assert.equal(monitor.get(providerCtx).limits.length, 0, "in-flight response cannot contaminate new provider");
assert.equal(monitor.get({ ...providerCtx, model: oldModel }).limits[0].used, 44);
monitor.dispose();
providerCtx.model = oldModel;

monitor = new UsageMonitor(() => {}, async (_url, init) => new Promise((_resolve, reject) => {
  init.signal.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
}));
const aborted = monitor.poll(providerCtx);
await new Promise(resolve => setTimeout(resolve, 0));
monitor.dispose();
await aborted;
assert.equal(monitor.get(providerCtx).limits.length, 0);
console.log("PASS: usage endpoints, payload/header/stream normalization, isolation, auth guards, deduplication, backoff and abort");

const { CacheTracker, CACHE_ENTRY, cachePolicy, cacheSummary } = await jiti.import(join(dirname(new URL(import.meta.url).pathname), "cache.ts"));
const openai = { provider: "openai", id: "gpt-6.1-sol", api: "openai-responses", baseUrl: "https://api.openai.com/v1", compat: { supportsExplicitPromptCacheMode: true } };
const shortPayload = { input: [{ content: "private" }], prompt_cache_options: { ttl: "30m" } };
const at = 1800000000000;
const message = { role: "assistant", provider: openai.provider, model: openai.id, timestamp: at, stopReason: "stop", usage: { input: 100, cacheRead: 900, cacheWrite: 0 } };
const tracker = new CacheTracker();
const history = [{ type: "message", message }];
assert.equal(cacheSummary(history, openai, at).state, "TTL ?", "historical counts alone cannot establish TTL");
tracker.observeRequest(openai, shortPayload, at);
const record = tracker.finish(openai, message);
history.push({ type: "custom", customType: CACHE_ENTRY, data: record });
assert.doesNotMatch(JSON.stringify(record), /private|input|prompt_cache_options/);
assert.equal(cacheSummary(history, openai, at + 60000).state, "~29m");
assert.equal(cacheSummary(history, openai, at + 1770000).state, "~30s");
assert.equal(cacheSummary(history, openai, at + 1800000).state, "TTL elapsed");
assert.equal(cacheSummary(history, { ...openai, baseUrl: "https://proxy.example" }, at).state, "TTL ?");
assert.equal(cacheSummary(history, { ...openai, id: "other" }, at), undefined, "model isolation");
assert.equal(cacheSummary(history.slice(0, 1), openai, at).state, "TTL ?", "branch excludes other branch metadata");
assert.equal(cachePolicy(openai, { prompt_cache_options: { ttl: "bogus" } }).seconds, undefined);
assert.equal(cachePolicy({ ...openai, baseUrl: "https://api.openai.com.evil" }, shortPayload).seconds, undefined);
assert.equal(cachePolicy(openai, {}).seconds, 1800, "modern default comes from explicit-cache capability, not model name guessing");
assert.equal(cachePolicy(openai, { prompt_cache_options: { ttl: "12h" } }).seconds, 1800, "reads do not restart a 12h clock");
assert.equal(cachePolicy(openai, { prompt_cache_options: { mode: "explicit" } }).seconds, undefined, "disabled implicit writes");
assert.equal(cachePolicy({ ...openai, compat: {} }, { prompt_cache_retention: "24h" }).seconds, undefined, "24h is not a guaranteed expiry");
assert.equal(cachePolicy({ ...openai, baseUrl: "https://proxy.example" }, {}).seconds, undefined);

tracker.observeRequest(openai, { prompt_cache_options: { ttl: "12h" } }, at);
tracker.observeStream({ type: "response.completed", response: { usage: { input_tokens_details: { cached_tokens: 0, cache_write_tokens_details: { ttl_12h_tokens: 1000, ttl_30m_tokens: 0 } } } } });
assert.equal(tracker.finish(openai, { ...message, provider: openai.provider, model: openai.id }).seconds, 43200);
tracker.observeRequest(openai, shortPayload, at);
assert.equal(tracker.finish(openai, { ...message, stopReason: "aborted" }), undefined);
tracker.observeRequest(openai, shortPayload, at);
assert.equal(tracker.finish({ ...openai, id: "other" }, message), undefined, "in-flight model change cannot contaminate expiry");
history.push({ type: "message", message: { ...message, timestamp: at + 1000, usage: { input: 1000, cacheRead: 0, cacheWrite: 0 } } });
assert.equal(cacheSummary(history, openai, at).ratio, 45, "cumulative ratio includes reads, writes and ordinary input");
assert.equal(cacheSummary(history, openai, at).state, "miss", "last request did not cache; old countdown cannot survive");
history.push({ type: "usage", source: "cache_warm", provider: openai.provider, model: openai.id, timestamp: new Date(at + 5000).toISOString(), usage: { cacheRead: 1000 } });
assert.equal(cacheSummary(history, openai, at).state, "TTL ?", "warm reuse is observed, not a fabricated refresh deadline");
assert.equal(cacheSummary(history, openai, at).ratio, 45, "warming does not inflate hit ratio");
assert.equal(cacheSummary([{ type: "message", message: { ...message, usage: { input: NaN, cacheRead: 0, cacheWrite: 0 } } }], openai, at), undefined);
console.log("PASS: cache request policies, raw usage, countdown, expiry, misses, branch/model/endpoint isolation, persistence, warming and invalid data");
