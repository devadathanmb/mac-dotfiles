import { homedir } from "node:os";
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { truncateToWidth, visibleWidth } from "@earendil-works/pi-tui";
import { UsageMonitor, type Limit } from "./usage.ts";
import { CACHE_ENTRY, CacheTracker, cacheSummary } from "./cache.ts";
const guardrailsPath = join(homedir(), ".pi", "agent", "extensions", "guardrails.json");
async function guardrailsState(ctx: ExtensionContext) {
  const global = JSON.parse(await readFile(guardrailsPath, "utf8"));
  let project: any = {};
  if (ctx.isProjectTrusted?.()) {
    try { project = JSON.parse(await readFile(join(ctx.cwd, ".pi", "extensions", "guardrails.json"), "utf8")); }
    catch (error: any) { if (error.code !== "ENOENT") throw error; }
  }
  return { global, enabled: project.enabled ?? global.enabled ?? true, gate: project.features?.permissionGate ?? global.features?.permissionGate ?? true, overridden: typeof project.enabled === "boolean" };
}

const palette = {
  fg: "d1d5db", muted: "8b949e", label: "767f8a", dim: "636c76",
  faint: "373e47", accent: "9a8cf5", ghost: "535a63",
  ok: "56d364", warn: "e3b341", crit: "ff7b72", sep: "4b525b",
};
type Tone = keyof typeof palette;
const color = (tone: Tone, text: string) => {
  const hex = palette[tone];
  return `\x1b[38;2;${parseInt(hex.slice(0, 2), 16)};${parseInt(hex.slice(2, 4), 16)};${parseInt(hex.slice(4), 16)}m${text}\x1b[0m`;
};
const clean = (s: string) => s.replace(/[\x00-\x1f\x7f-\x9f]/g, " ");
const sep = color("sep", " ⏐ ");
const clamp = (n: number) => Math.max(0, Math.min(100, n));
const tokens = (n: number) => n >= 1e6 ? `${+(n / 1e6).toFixed(1)}M` : n >= 1000 ? `${Math.floor(n / 1000)}k` : `${Math.floor(n)}`;

function bar(used: number, width: number, tone: Tone, pace = 0) {
  const full = Math.min(width, Math.max(used > 0 ? 1 : 0, Math.round(clamp(used) * width / 100)));
  const ghost = Math.max(full, Math.round(clamp(pace) * width / 100));
  return color(tone, "━".repeat(full)) + color("ghost", "━".repeat(ghost - full)) + color("faint", "─".repeat(width - ghost));
}

function resetTime(reset: number, now: number) {
  const seconds = Math.max(0, reset - now);
  if (!seconds) return "now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${String(Math.floor(seconds % 3600 / 60)).padStart(2, "0")}m`;
  const date = new Date(reset * 1000);
  return `${date.toLocaleDateString("en-US", { weekday: "short" })} ${date.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true }).replace(" ", "").toLowerCase()}`;
}

function limitRows(limits: Limit[], mode: number, now: number) {
  const times = limits.map(l => mode < 2 && l.reset ? resetTime(l.reset, now) : "");
  const timeWidth = Math.max(0, ...times.map(visibleWidth));
  const labelWidth = Math.max(2, ...limits.map(l => l.label.length));
  return limits.map((limit, i) => {
    const paced = limit.kind !== "throughput" && limit.reset !== undefined;
    const pace = paced ? clamp((1 - (limit.reset! - now) / limit.window) * 100) : 0;
    const tone: Tone = limit.used >= 90 || (paced && limit.used > pace + 20) ? "crit"
      : limit.used >= 75 || (paced && limit.used > pace + 5) ? "warn" : "ok";
    return color("label", limit.label.padEnd(labelWidth)) + " " + (mode === 0 ? bar(limit.used, 10, tone, pace) + " " : "")
      + color(tone, `${Math.floor(limit.used)}%`.padStart(4))
      + (times[i] ? color("label", " " + times[i].padStart(timeWidth)) : "");
  });
}

type GitStatus = { branch: string; dirty: boolean; ahead: number; behind: number; added: number; removed: number };

function emptyGitStatus(): GitStatus {
  return { branch: "", dirty: false, ahead: 0, behind: 0, added: 0, removed: 0 };
}

async function readGitStatus(pi: ExtensionAPI, cwd: string): Promise<GitStatus> {
  const options = { cwd, timeout: 2500, maxBuffer: 1024 * 1024 };
  const status = await pi.exec("git", ["--no-optional-locks", "status", "--porcelain=v1", "--branch", "--untracked-files=normal"], options);
  if (status.code !== 0) return emptyGitStatus();

  const [header, ...files] = status.stdout.trimEnd().split("\n");
  const branch = header.slice(3).split("...")[0].split(" [")[0].replace(/^(No commits yet on |Initial commit on )/, "");
  const diff = await pi.exec("git", ["--no-optional-locks", "diff", "--no-ext-diff", "--numstat", "HEAD", "--"], options);
  let added = 0, removed = 0;
  for (const row of diff.code === 0 ? diff.stdout.split("\n") : []) {
    const [a, r] = row.split("\t");
    added += Number(a) || 0;
    removed += Number(r) || 0;
  }
  return {
    branch: clean(branch), dirty: files.some(Boolean),
    ahead: Number(header.match(/ahead (\d+)/)?.[1] ?? 0),
    behind: Number(header.match(/behind (\d+)/)?.[1] ?? 0), added, removed,
  };
}

function layoutRows(width: number, leftOptions: string[], secondOptions: string[], rightOptions: string[][]): string[] {
  const available = Math.max(0, width - 4);
  const fits = (a: string, b = "") => visibleWidth(a) + (b ? visibleWidth(b) + 2 : 0) <= available;
  let left = leftOptions[0], second = secondOptions[0], right: string[] = [];
  for (const candidate of rightOptions) {
    right = candidate;
    left = leftOptions.find(option => fits(option, right[0])) ?? leftOptions.at(-1)!;
    second = secondOptions.find(option => fits(option, right[1])) ?? secondOptions.at(-1)!;
    if (fits(left, right[0]) && fits(second, right[1])) break;
  }
  const join = (a: string, b = "") => {
    if (!available) return "";
    if (b && visibleWidth(b) + 2 < available) {
      a = truncateToWidth(a, available - visibleWidth(b) - 2, "…");
      return "  " + a + " ".repeat(Math.max(2, available - visibleWidth(a) - visibleWidth(b))) + b;
    }
    return truncateToWidth("  " + a, Math.max(0, width), "…");
  };
  return [join(left, right[0]), join(second, right[1])];
}

export default function (pi: ExtensionAPI) {
  let requestRender = () => {};
  pi.registerCommand("guardrails-toggle", {
    description: "Toggle Guardrails globally and reload",
    handler: async (_args, ctx) => {
      try {
        const state = await guardrailsState(ctx);
        if (state.overridden) {
          ctx.ui.notify("Project Guardrails settings override the global toggle; change them in /guardrails:settings", "warning");
          return;
        }
        await writeFile(guardrailsPath, JSON.stringify({ ...state.global, enabled: !state.enabled }, null, 2) + "\n");
      } catch {
        ctx.ui.notify("Could not change Guardrails settings", "error");
        return;
      }
      await ctx.reload();
    },
  });
  pi.registerShortcut("ctrl+alt+g", {
    description: "Toggle Guardrails globally",
    handler: () => { pi.sendUserMessage("/guardrails-toggle", { expandPromptTemplates: true }); },
  });
  const cacheTracker = new CacheTracker();
  pi.on("before_provider_request", (event, ctx) => cacheTracker.observeRequest(ctx.model, event.payload));
  pi.on("message_end", (event, ctx) => {
    const record = cacheTracker.finish(ctx.model, event.message);
    if (record) pi.appendEntry(CACHE_ENTRY, record);
    requestRender();
  });
  pi.registerCommand("cache", {
    description: "Explain prompt-cache hit ratio and estimated TTL",
    handler: async (_args, ctx) => {
      const summary = cacheSummary(ctx.sessionManager.getBranch(), ctx.model);
      ctx.ui.notify(summary
        ? `Cache ${summary.ratio}% · ${summary.state}\n${summary.description}\nRatio: cache reads / (uncached input + cache reads + cache writes), cumulative on the active branch for this model; warming excluded.\n~ = estimated from request start, not a server expiry timestamp. TTL elapsed does not prove eviction or guarantee the next request will miss.`
        : "No successful prompt usage recorded for the selected model on this branch.", "info");
    },
  });
  const usageMonitor = new UsageMonitor(() => requestRender());
  pi.on("after_provider_response", (event, ctx) => usageMonitor.observeHeaders(ctx, event.headers));
  pi.on("provider_stream_event", (event, ctx) => {
    cacheTracker.observeStream(event.data);
    usageMonitor.observeStream(ctx, event.data);
  });
  pi.on("model_select", (_event, ctx) => { void usageMonitor.poll(ctx); requestRender(); });
  pi.on("agent_settled", (_event, ctx) => { void usageMonitor.poll(ctx); });
  pi.on("session_shutdown", () => usageMonitor.dispose());
  pi.registerCommand("usage", {
    description: "Refresh provider quota and explain usage availability",
    handler: async (_args, ctx) => {
      await usageMonitor.poll(ctx, true);
      const snapshot = usageMonitor.get(ctx);
      const text = snapshot.limits.length
        ? snapshot.limits.map(l => `${l.label}: ${l.used.toFixed(1)}% used${l.reset ? `; resets ${resetTime(l.reset, Date.now() / 1000)}` : ""}`).join("\n") + `\nSource: ${snapshot.source}`
        : `${snapshot.message ?? "Usage not reported"}.${snapshot.url ? `\nCheck ${snapshot.url}` : ""}\nAPI throughput limits and subscription quotas are separate; only exposed data can be displayed.`;
      ctx.ui.notify(text, snapshot.limits.length ? "info" : "warning");
    },
  });

  pi.on("session_start", (_event, ctx) => {
    if (ctx.mode !== "tui") return;
    ctx.ui.setFooter((tui, _theme, footerData) => {
      let disposed = false;
      let guardStatus: { enabled: boolean; gate: boolean } | undefined;
      const refreshGuardStatus = async () => {
        try { guardStatus = await guardrailsState(ctx); } catch { guardStatus = undefined; }
        requestRender();
      };
      let refreshing = false;
      let git = emptyGitStatus();
      let statsKey = "";
      let cost = 0;
      let cacheEntries: ReturnType<typeof ctx.sessionManager.getBranch> = [];
      requestRender = () => { if (!disposed) tui.requestRender(); };
      const unsub = footerData.onBranchChange(requestRender);

      const refreshGit = async () => {
        if (disposed || refreshing) return;
        refreshing = true;
        try {
          const next = await readGitStatus(pi, ctx.cwd);
          if (!disposed) {
            git = next;
            requestRender();
          }
        } catch { /* A missing Git executable must not break the footer. */ }
        finally { refreshing = false; }
      };
      void refreshGit();
      void refreshGuardStatus();
      void usageMonitor.poll(ctx);
      const timer = setInterval(() => { void refreshGit(); void refreshGuardStatus(); void usageMonitor.poll(ctx); requestRender(); }, 5000);
      timer.unref();

      return {
        dispose() { disposed = true; clearInterval(timer); unsub(); requestRender = () => {}; },
        invalidate() {},
        render(width: number): string[] {
          const entries = ctx.sessionManager.getEntries();
          const key = `${entries.length}:${ctx.sessionManager.getLeafId()}`;
          if (key !== statsKey) {
            statsKey = key;
            cost = 0;
            cacheEntries = ctx.sessionManager.getBranch();
            for (const entry of entries) {
              const usage = entry.type === "message" && (entry.message.role === "assistant" || entry.message.role === "toolResult")
                ? entry.message.usage : "usage" in entry ? entry.usage : undefined;
              if (usage) cost += usage.cost?.total ?? 0;
            }
          }
          const now = Date.now() / 1000;
          const usage = ctx.getContextUsage();
          const percent = usage?.percent;
          const tone: Tone = (percent ?? 0) >= 80 ? "crit" : (percent ?? 0) >= 60 ? "warn" : "accent";
          const effort = pi.getThinkingLevel();
          const model = color("accent", "◆") + " " + color("fg", clean(ctx.model?.name || ctx.model?.id || "no model"))
            + color("faint", " · ") + color(effort === "max" || effort === "xhigh" ? "warn" : effort === "high" ? "fg" : "dim", effort);
          const context = bar(percent ?? 0, 12, tone) + " " + color(tone === "accent" ? "fg" : tone, percent == null ? "?%" : `${Math.floor(percent)}%`);
          const tokenCount = color("dim", `  ${usage?.tokens == null ? "?" : tokens(usage.tokens)}/${tokens(usage?.contextWindow ?? ctx.model?.contextWindow ?? 0)}`);
          const cacheStats = cacheSummary(cacheEntries, ctx.model);
          const cache = !cacheStats ? "" : sep + color("dim", "cache ") + color("muted", `${cacheStats.ratio}%`)
            + " " + color(cacheStats.state === "miss" || cacheStats.state === "TTL elapsed" ? "warn" : "dim", cacheStats.state);
          const price = cost > 0 ? sep + color("muted", `$${cost.toFixed(2)}`) : "";
          const started = ctx.sessionManager.getHeader()?.timestamp;
          const elapsed = started ? Math.max(0, Math.floor((Date.now() - Date.parse(started)) / 1000)) : 0;
          const duration = sep + color("dim", elapsed >= 3600 ? `${Math.floor(elapsed / 3600)}h${Math.floor(elapsed % 3600 / 60)}m` : elapsed >= 60 ? `${Math.floor(elapsed / 60)}m` : `${elapsed}s`);
          const home = homedir();
          const path = clean(ctx.cwd === home ? "~" : ctx.cwd.startsWith(home + "/") ? "~" + ctx.cwd.slice(home.length) : ctx.cwd);
          const pathSegment = (short: boolean) => {
            const parts = path.split("/");
            const leaf = parts.pop() ?? path;
            const parent = short && parts.length > 2 ? "…/" + parts.slice(-1).join("/") : parts.join("/");
            return (parent ? color("dim", parent + "/") : "") + color("fg", `\x1b[1m${leaf}`);
          };
          const branch = git.branch || footerData.getGitBranch();
          const branchSegment = branch ? sep + color("dim", "󰘬 ") + color("muted", clean(branch) + (git.dirty ? "*" : "") + (git.ahead ? ` ↑${git.ahead}` : "") + (git.behind ? ` ↓${git.behind}` : "")) : "";
          const changes = git.added || git.removed ? sep + color("ok", `+${git.added}`) + " " + color("crit", `−${git.removed}`) : "";
          const usageSnapshot = usageMonitor.get(ctx);
          const activeLimits = usageSnapshot.limits;
          const usageFallback = usageSnapshot.url
            ? color("dim", "usage ") + `\x1b]8;;${usageSnapshot.url}\x07` + color("label", "↗ /usage") + "\x1b]8;;\x07"
            : "";
          const leftOptions = [model + sep + context + tokenCount + cache + price + duration, model + sep + context + tokenCount + cache + price, model + sep + context + tokenCount + cache, model + sep + context + cache, model + sep + context, model];
          const secondOptions = [pathSegment(false) + branchSegment + changes, pathSegment(true) + branchSegment + changes, pathSegment(true) + branchSegment, pathSegment(true)];
          const rightOptions = [0, 1, 2].map(mode => activeLimits.length
            ? limitRows(activeLimits, mode, now) : usageFallback ? [usageFallback] : []);
          const lines = layoutRows(width, leftOptions, secondOptions, rightOptions);
          const status = !guardStatus ? color("warn", "guardrails status unavailable")
            : !guardStatus.enabled ? color("crit", "▶▶ bypass guardrails on")
            : !guardStatus.gate ? color("warn", "guardrails on · command gate off") : color("ok", "guardrails on");
          lines.push(truncateToWidth("  " + status + color("dim", "  ctrl+alt+g"), Math.max(0, width), "…"));
          const statuses = [...footerData.getExtensionStatuses().entries()].sort(([a], [b]) => a.localeCompare(b)).map(([, s]) => s.replace(/[\r\n\t]/g, " "));
          if (statuses.length) lines.push(truncateToWidth("  " + statuses.join(" "), Math.max(0, width), "…"));
          return lines;
        },
      };
    });
  });
}
