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
let entries = [{ type: "message", message: { role: "assistant", usage: { input: 100, cacheRead: 9900, cacheWrite: 0, cost: { total: 18.05 } } } }];
const api = {
  on: (name, fn) => events.set(name, fn),
  registerCommand() {},
  getThinkingLevel: () => "medium",
  exec: async (_cmd, args) => ({ code: 0, stdout: args.includes("status") ? "## redesign...origin/redesign [ahead 1]\n M index.ts\n" : "1483\t0\tindex.ts\n" }),
};
const ctx = {
  mode: "tui", cwd: "/Users/example/repos/nokku",
  model: { name: "Opus 5.5", provider: "anthropic", contextWindow: 1000000 },
  modelRegistry: { isUsingOAuth: () => false },
  getContextUsage: () => context,
  sessionManager: {
    getEntries: () => entries, getLeafId: () => String(entries.length),
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
