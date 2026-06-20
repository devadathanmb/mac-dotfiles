import { DynamicBorder, type ExtensionAPI, type ExtensionContext, type ToolCallEvent } from "@earendil-works/pi-coding-agent";
import { Box, Container, SelectList, Spacer, Text, type SelectItem } from "@earendil-works/pi-tui";
import { readFile } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { isAbsolute, relative, resolve } from "node:path";
import { parse as parseYaml } from "yaml";

type Mode = "off" | "yolo" | "blacklist" | "whitelist" | "ask";
type Action = "allow" | "ask" | "block";
type Operation = "read" | "list" | "write" | "edit" | "delete" | "move" | "execute";

type Rule = {
  id: string;
  description: string;
  match: RuleMatch;
  action: Action;
  feedback?: { agentHint?: string };
};

type RuleMatch = {
  tool?: string;
  toolsAny?: string[];
  commandRegex?: string;
  command?: CommandMatch;
  path?: PathMatch;
};

type CommandMatch = {
  program?: string;
  argsSequence?: string[];
  flagsAny?: string[];
  flagsAll?: string[];
  startsWith?: string;
  includesAny?: string[];
};

type PathMatch = {
  globAny?: string[];
  except?: string[];
  operationsAny?: Operation[];
};

type Config = {
  mode: Mode;
  cycleModes: Mode[];
  keymaps: {
    cycleMode?: string;
    toggleYolo?: string;
  };
  ui: {
    footerStatus: boolean;
    notifyOnBlock: boolean;
    notifyOnAsk: boolean;
    showChatMessages: boolean;
  };
  feedback: {
    blockedToolResult: "continue" | "abort";
    includeAdaptationHints: boolean;
  };
  rules: Rule[];
  /** Rule ids to drop after merging (lets a project relax a global rule). */
  disableRules: string[];
};

type ConfigLoad = { config: Config; source: string; warnings: string[] };

type Decision = {
  action: Action;
  reason: string;
  rule?: Rule;
  source: "rule" | "mode" | "session" | "yolo" | "off";
};

type Invocation = {
  toolName: string;
  input: Record<string, unknown>;
  display: string;
  command?: string;
  tokens: string[];
  program?: string;
  paths: string[];
  operations: Operation[];
  cwd: string;
};

type DamageControlStatus = {
  enabled: boolean;
  mode: Mode;
  rulesLoaded: number;
  configSource: string;
  lastDecision?: {
    action: Action;
    tool: string;
    reason?: string;
    at: number;
  };
};

const EXTENSION_NAME = "damage-control";
const STATUS_EVENT = "damage-control:status";
const STATUS_REQUEST_EVENT = "damage-control:status-request";
const PERMISSION_REQUEST_EVENT = "damage-control:permission-request";
const MESSAGE_TYPE = "damage-control";
const DEFAULT_CYCLE_MODES: Mode[] = ["blacklist", "whitelist", "ask", "yolo"];
const ACTION_WEIGHT: Record<Action, number> = { allow: 1, ask: 2, block: 3 };

const CONFIG_PATHS = [resolve(homedir(), ".pi", "agent", "damage-control.yaml")];
const DISPLAY_MAX_LENGTH = 500;
/** Nerd Font shield glyph used in the brand mark. */
const SHIELD = "";

const DEFAULT_CONFIG: Config = {
  mode: "blacklist",
  cycleModes: DEFAULT_CYCLE_MODES,
  keymaps: { cycleMode: "shift+tab", toggleYolo: "ctrl+shift+y" },
  ui: { footerStatus: true, notifyOnBlock: true, notifyOnAsk: false, showChatMessages: true },
  feedback: { blockedToolResult: "continue", includeAdaptationHints: true },
  rules: [],
  disableRules: [],
};

export default function localDamageControl(pi: ExtensionAPI): void {
  let configLoad = loadGlobalConfigSync();
  let config = configLoad.config;
  let mode: Mode = config.mode;
  let configSource = configLoad.source;
  let activeCtx: ExtensionContext | undefined;
  let modeBeforeYolo: Mode | undefined;
  let status: DamageControlStatus = createStatus(config, mode, configSource);
  let lastFooterText: string | undefined;
  const sessionApprovals = new Set<string>();
  const ruleApprovals = new Set<string>();

  registerRenderers(pi);
  registerCommands(pi);
  registerShortcuts(pi);

  pi.events.on(STATUS_REQUEST_EVENT, () => {
    if (activeCtx) {
      publishStatus(activeCtx);
      return;
    }
    pi.events.emit(STATUS_EVENT, status);
  });

  pi.on("session_start", async (_event, ctx) => {
    activeCtx = ctx;
    sessionApprovals.clear();
    ruleApprovals.clear();
    await reloadConfig(ctx);
    publishStatus(ctx);
  });

  pi.on("session_shutdown", () => {
    activeCtx = undefined;
  });

  pi.on("tool_call", async (event, ctx) => {
    const invocation = buildInvocation(event, ctx.cwd);
    const decision = decide(invocation);

    if (decision.action === "allow") {
      await recordDecision(ctx, invocation, decision);
      return undefined;
    }

    if (decision.action === "ask") {
      const askDecision = await askUser(ctx, invocation, decision);
      await recordDecision(ctx, invocation, askDecision);
      if (askDecision.action === "allow") return undefined;
      return blockResult(invocation, askDecision, ctx);
    }

    await recordDecision(ctx, invocation, decision);
    return blockResult(invocation, decision, ctx);
  });

  async function reloadConfig(ctx?: ExtensionContext): Promise<void> {
    configLoad = await loadConfig(ctx?.cwd);
    config = configLoad.config;
    mode = config.mode;
    configSource = configLoad.source;
    if (ctx) {
      publishStatus(ctx);
      warnAboutConfig(ctx);
    } else {
      recomputeStatus();
    }
  }

  /** Surface invalid rules and footguns loudly so a broken rule never fails open silently. */
  function warnAboutConfig(ctx: ExtensionContext): void {
    for (const warning of configLoad.warnings) {
      ctx.ui.notify(` Damage Control: ${warning}`, "warning");
    }
    if (mode === "whitelist" && !config.rules.some((rule) => rule.action === "allow")) {
      ctx.ui.notify(
        " Damage Control: whitelist mode is active but no 'allow' rules exist; only read-only operations will pass.",
        "warning",
      );
    }
  }

  /** Drop the in-memory mode override and fall back to the configured mode. */
  function clearModeOverride(ctx?: ExtensionContext): void {
    mode = config.mode;
    modeBeforeYolo = undefined;
    if (ctx) {
      publishStatus(ctx);
      ctx.ui.notify(` Damage Control reset to configured mode: ${mode}`, "info");
    } else {
      recomputeStatus();
    }
  }

  function setMode(nextMode: Mode, ctx?: ExtensionContext): void {
    mode = nextMode;
    const target = ctx ?? activeCtx;
    if (target) {
      publishStatus(target);
    } else {
      recomputeStatus();
    }
    ctx?.ui.notify(` Damage Control: ${mode}`, mode === "yolo" ? "warning" : "info");
  }

  function cycleMode(ctx: ExtensionContext): void {
    const modes = config.cycleModes.length > 0 ? config.cycleModes : DEFAULT_CYCLE_MODES;
    const currentIndex = modes.indexOf(mode);
    const nextMode = modes[(currentIndex + 1) % modes.length] ?? modes[0] ?? "blacklist";
    setMode(nextMode, ctx);
  }

  function decide(invocation: Invocation): Decision {
    if (mode === "off") return { action: "allow", reason: "Damage Control is off", source: "off" };
    if (mode === "yolo") return { action: "allow", reason: "YOLO mode", source: "yolo" };

    const approvalKey = getApprovalKey(invocation);
    if (sessionApprovals.has(approvalKey)) {
      return { action: "allow", reason: "Approved for this session", source: "session" };
    }

    const matched = config.rules.filter((rule) => ruleMatches(rule, invocation));
    // Most-restrictive action wins; on a tie the first matching rule wins so the
    // reported reason is stable against YAML reordering.
    const strongest = matched.reduce<Rule | undefined>((best, rule) => {
      if (!best) return rule;
      if (ACTION_WEIGHT[rule.action] > ACTION_WEIGHT[best.action]) return rule;
      return best;
    }, undefined);

    if (strongest) {
      // An "ask" rule the user approved for the session passes without re-prompting,
      // even when the exact command differs (a flag added, etc.). Block always re-blocks.
      if (strongest.action === "ask" && ruleApprovals.has(strongest.id)) {
        return { action: "allow", reason: `Rule "${strongest.id}" approved for this session`, rule: strongest, source: "session" };
      }
      return {
        action: strongest.action,
        reason: strongest.description,
        rule: strongest,
        source: "rule",
      };
    }

    if (mode === "whitelist") {
      // A whitelist with only deny rules would block everything, including benign
      // reads. Let pure read/list operations through unless a block rule matched above.
      if (isReadOnly(invocation)) {
        return { action: "allow", reason: "Read-only operation allowed in whitelist mode", source: "mode" };
      }
      return { action: "block", reason: "No whitelist rule matched", source: "mode" };
    }
    if (mode === "ask") return { action: "ask", reason: "Ask mode requires approval", source: "mode" };
    return { action: "allow", reason: "No blacklist rule matched", source: "mode" };
  }

  async function askUser(ctx: ExtensionContext, invocation: Invocation, decision: Decision): Promise<Decision> {
    if (!ctx.hasUI) {
      // No interactive UI means we can't ask, so fail safe: block and tell the agent why.
      ctx.ui.notify(`${SHIELD} Damage Control can't prompt without a UI; blocking ${invocation.toolName}`, "warning");
      return { ...decision, action: "block", reason: `${decision.reason} (no UI to approve; blocked)` };
    }

    pi.events.emit(PERMISSION_REQUEST_EVENT, {
      tool: invocation.toolName,
      ruleId: decision.rule?.id,
      reason: decision.reason,
      command: invocation.command,
      display: invocation.display,
      mode,
    });

    if (config.ui.notifyOnAsk) {
      ctx.ui.notify(` Damage Control asks before ${invocation.toolName}`, "warning");
    }

    const choice = await showPermissionDialog(ctx, invocation, decision, mode);

    if (choice === "allow_once") return { ...decision, action: "allow", reason: `${decision.reason} (approved once)` };
    if (choice === "allow_session") {
      sessionApprovals.add(getApprovalKey(invocation));
      return { ...decision, action: "allow", reason: `${decision.reason} (approved for session)` };
    }
    if (choice === "allow_rule_session" && decision.rule) {
      ruleApprovals.add(decision.rule.id);
      return { ...decision, action: "allow", reason: `${decision.reason} (rule approved for session)` };
    }
    return { ...decision, action: "block", reason: `${decision.reason} (denied by user)` };
  }

  async function recordDecision(ctx: ExtensionContext, invocation: Invocation, decision: Decision): Promise<void> {
    const details = {
      at: new Date().toISOString(),
      mode,
      tool: invocation.toolName,
      action: decision.action,
      reason: decision.reason,
      ruleId: decision.rule?.id,
      input: sanitizeInput(invocation.input),
    };

    status = createStatus(config, mode, configSource, {
      action: decision.action,
      tool: invocation.toolName,
      reason: decision.reason,
      at: Date.now(),
    });
    publishStatus(ctx);

    if (config.ui.showChatMessages && decision.action === "block") {
      pi.sendMessage({
        customType: MESSAGE_TYPE,
        content: `${invocation.toolName} blocked: ${decision.reason}`,
        display: true,
        details,
      });
    }
  }

  function blockResult(invocation: Invocation, decision: Decision, ctx: ExtensionContext) {
    if (config.ui.notifyOnBlock) {
      ctx.ui.notify(`🛑 Damage Control blocked ${invocation.toolName}: ${decision.reason}`, "error");
    }
    if (config.feedback.blockedToolResult === "abort") ctx.abort();
    return { block: true, reason: buildAgentFeedback(invocation, decision, config) };
  }

  /** Rebuild the cached status without a ctx (e.g. before a later STATUS_REQUEST_EVENT). */
  function recomputeStatus(): void {
    status = createStatus(config, mode, configSource, status.lastDecision);
  }

  function publishStatus(ctx: ExtensionContext): void {
    recomputeStatus();
    pi.events.emit(STATUS_EVENT, status);
    if (!ctx.hasUI || !config.ui.footerStatus) return;
    // Footer text depends only on the mode, so skip the redundant setStatus that
    // would otherwise fire on every allowed tool call via recordDecision.
    const text = formatStatusText(status);
    if (text === lastFooterText) return;
    lastFooterText = text;
    ctx.ui.setStatus(EXTENSION_NAME, text);
  }

  function registerCommands(piApi: ExtensionAPI): void {
    piApi.registerCommand("dc", {
      description: "Damage Control status and mode controls",
      handler: async (args, ctx) => {
        const [subcommand, value] = args.trim().split(/\s+/);
        if (!subcommand || subcommand === "status") {
          ctx.ui.notify(
            `Damage Control: ${mode} · ${config.rules.length} rules · cycle ${config.keymaps.cycleMode ?? "unbound"} · yolo ${config.keymaps.toggleYolo ?? "unbound"}`,
            "info",
          );
          return;
        }
        if (subcommand === "reload") {
          await reloadConfig(ctx);
          ctx.ui.notify(`Damage Control reloaded: ${config.rules.length} rules`, "info");
          return;
        }
        if (subcommand === "mode") {
          if (value === "reset") {
            clearModeOverride(ctx);
            return;
          }
          if (!isMode(value)) {
            ctx.ui.notify("Usage: /dc mode off|yolo|blacklist|whitelist|ask|reset", "warning");
            return;
          }
          setMode(value, ctx);
          return;
        }
        if (subcommand === "reset" || subcommand === "clear") {
          clearModeOverride(ctx);
          return;
        }
        if (subcommand === "cycle") {
          cycleMode(ctx);
          return;
        }
        if (subcommand === "rules") {
          const preview = config.rules.map((rule) => `${rule.action.padEnd(5)} ${rule.id}`).join("\n");
          pi.sendMessage({ customType: MESSAGE_TYPE, content: preview || "No Damage Control rules loaded", display: true });
          return;
        }
        ctx.ui.notify("Usage: /dc [status|reload|cycle|rules|reset|mode <mode>]", "warning");
      },
    });
  }

  function registerShortcuts(piApi: ExtensionAPI): void {
    if (config.keymaps.cycleMode) {
      piApi.registerShortcut(config.keymaps.cycleMode as Parameters<ExtensionAPI["registerShortcut"]>[0], {
        description: "Cycle Damage Control mode",
        handler: (ctx) => cycleMode(ctx),
      });
    }
    if (config.keymaps.toggleYolo) {
      piApi.registerShortcut(config.keymaps.toggleYolo as Parameters<ExtensionAPI["registerShortcut"]>[0], {
        description: "Toggle Damage Control YOLO mode",
        handler: (ctx) => toggleYolo(ctx),
      });
    }
  }

  function toggleYolo(ctx: ExtensionContext): void {
    if (mode === "yolo") {
      // Restore whatever mode was active before YOLO rather than a hardcoded default.
      const restore = modeBeforeYolo ?? config.mode;
      modeBeforeYolo = undefined;
      setMode(restore, ctx);
      return;
    }
    modeBeforeYolo = mode;
    setMode("yolo", ctx);
  }
}

type DialogChoice = "allow_once" | "allow_session" | "allow_rule_session" | "deny";

async function showPermissionDialog(
  ctx: ExtensionContext,
  invocation: Invocation,
  decision: Decision,
  currentMode: Mode,
): Promise<DialogChoice | null> {
  if (ctx.mode !== "tui") return showPermissionSelectFallback(ctx, invocation, decision, currentMode);

  return await ctx.ui.custom<DialogChoice | null>((tui, theme, _keybindings, done) => {
    const container = new Container();
    const accent = "warning" as const;
    const ruleLabel = decision.rule?.id ?? currentMode;
    const operationLabel = invocation.operations.filter((op) => op !== "execute").join(", ") || "execute";
    const hint = decision.rule?.feedback?.agentHint;

    const PAD_X = 2;
    const sep = theme.fg("dim", "  ·  ");
    const pair = (label: string, value: string, valueColor: Parameters<typeof theme.fg>[0] = "text"): string =>
      `${theme.fg("dim", label)} ${theme.fg(valueColor, theme.bold(value))}`;
    const rule = (): DynamicBorder => new DynamicBorder((s: string) => theme.fg(accent, s));

    container.addChild(new Spacer(1));
    container.addChild(rule());
    container.addChild(new Spacer(1));

    // Brand + intent
    container.addChild(
      new Text(
        `${theme.fg(accent, theme.bold(`${SHIELD}  Damage Control`))}${sep}${theme.fg("muted", "needs your permission")}`,
        PAD_X,
        0,
      ),
    );
    container.addChild(new Spacer(1));

    // Metadata strip
    container.addChild(
      new Text(
        [
          pair("tool", invocation.toolName),
          pair("rule", ruleLabel),
          pair("op", operationLabel),
          pair("mode", currentMode),
        ].join(sep),
        PAD_X,
        0,
      ),
    );
    container.addChild(new Spacer(1));

    // Why we are asking
    container.addChild(new Text(`${theme.fg(accent, "▌")} ${theme.fg(accent, decision.reason)}`, PAD_X, 0));
    container.addChild(new Spacer(1));

    // The command / input, in a padded card
    container.addChild(new Text(theme.fg("muted", invocation.command ? "Command" : "Input"), PAD_X, 0));
    const card = new Box(PAD_X, 1, (line: string) => theme.bg("toolPendingBg", line));
    card.addChild(new Text(theme.fg("toolOutput", invocation.display)));
    container.addChild(card);

    if (hint) {
      container.addChild(new Spacer(1));
      container.addChild(
        new Text(`${theme.fg(accent, "◆")} ${theme.fg("muted", "Preference")}  ${theme.fg("text", hint)}`, PAD_X, 0),
      );
    }
    container.addChild(new Spacer(1));

    // Choices
    const items: SelectItem[] = [
      { value: "allow_once", label: "Allow once", description: "Run this exact tool call now" },
      { value: "allow_session", label: "Allow for session", description: "Don't ask again for this exact invocation" },
    ];
    if (decision.rule) {
      items.push({
        value: "allow_rule_session",
        label: "Allow rule for session",
        description: `Don't ask again for the "${decision.rule.id}" rule this session`,
      });
    }
    items.push({ value: "deny", label: "Deny", description: "Block it and tell the agent to adapt" });
    const selectList = new SelectList(items, items.length, {
      selectedPrefix: (s: string) => theme.fg(accent, s),
      selectedText: (s: string) => theme.fg(accent, theme.bold(s)),
      description: (s: string) => theme.fg("muted", s),
      scrollInfo: (s: string) => theme.fg("dim", s),
      noMatch: (s: string) => theme.fg("warning", s),
    });
    selectList.onSelect = (item) => done(item.value as DialogChoice);
    selectList.onCancel = () => done("deny");
    const choices = new Box(PAD_X, 0);
    choices.addChild(selectList);
    container.addChild(choices);
    container.addChild(new Spacer(1));

    // Key hints
    container.addChild(
      new Text(
        [
          `${theme.fg(accent, "↑↓")} ${theme.fg("dim", "navigate")}`,
          `${theme.fg(accent, "⏎")} ${theme.fg("dim", "confirm")}`,
          `${theme.fg(accent, "esc")} ${theme.fg("dim", "deny")}`,
        ].join(sep),
        PAD_X,
        0,
      ),
    );
    container.addChild(new Spacer(1));
    container.addChild(rule());
    container.addChild(new Spacer(1));

    return {
      render: (width: number) => container.render(width),
      invalidate: () => container.invalidate(),
      handleInput: (data: string) => {
        selectList.handleInput?.(data);
        tui.requestRender();
      },
    };
  });
}

async function showPermissionSelectFallback(
  ctx: ExtensionContext,
  invocation: Invocation,
  decision: Decision,
  currentMode: Mode,
): Promise<DialogChoice | null> {
  const ruleLine = decision.rule ? `Rule: ${decision.rule.id}` : `Mode: ${currentMode}`;
  const choices: string[] = decision.rule
    ? ["Allow once", "Allow for session", "Allow rule for session", "Deny"]
    : ["Allow once", "Allow for session", "Deny"];
  const choice = await ctx.ui.select(
    [
      " Damage Control",
      "",
      `Tool: ${invocation.toolName}`,
      ruleLine,
      "",
      decision.reason,
      "",
      invocation.display,
      "",
      "Choose an action:",
    ]
      .filter(Boolean)
      .join("\n"),
    choices,
  );
  if (choice === "Allow once") return "allow_once";
  if (choice === "Allow for session") return "allow_session";
  if (choice === "Allow rule for session") return "allow_rule_session";
  return "deny";
}

function registerRenderers(piApi: ExtensionAPI): void {
  piApi.registerMessageRenderer(MESSAGE_TYPE, (message, options, theme) => {
    const details = isRecord(message.details) ? message.details : {};
    const action = typeof details.action === "string" ? details.action : undefined;
    const isDecision = action === "block" || action === "ask" || action === "allow";

    // Informational messages (e.g. /dc rules) have no decision action; render them
    // plainly instead of borrowing the decision header with a bogus "· tool".
    if (!isDecision) {
      const header = theme.fg("accent", theme.bold(" Damage Control"));
      return new Text(`${header}\n${theme.fg("text", String(message.content))}`, 0, 0);
    }

    const tool = typeof details.tool === "string" ? details.tool : "tool";
    const ruleId = typeof details.ruleId === "string" ? details.ruleId : undefined;
    const reason = typeof details.reason === "string" ? details.reason : message.content;
    const color = action === "block" ? "error" : action === "ask" ? "warning" : "success";
    const title = `${theme.fg(color, theme.bold(" Damage Control"))} ${theme.fg(color, action.toUpperCase())}`;
    const meta = [
      `${theme.fg("muted", "tool")} ${theme.fg("text", tool)}`,
      ruleId ? `${theme.fg("muted", "rule")} ${theme.fg("text", ruleId)}` : undefined,
    ]
      .filter(Boolean)
      .join(theme.fg("dim", "  ·  "));
    let text = `${title}\n${meta}\n${theme.fg("text", String(reason))}`;
    if (options.expanded && isRecord(details.input)) {
      text += `\n${theme.fg("dim", JSON.stringify(details.input, null, 2))}`;
    }
    return new Text(text, 1, 1, (line: string) => theme.bg(action === "block" ? "toolErrorBg" : "toolPendingBg", line));
  });
}

async function loadConfig(cwd?: string): Promise<ConfigLoad> {
  const global = loadGlobalConfigSync();
  const projectPath = cwd ? resolve(cwd, ".pi", "damage-control.yaml") : undefined;
  if (!projectPath || !existsSync(projectPath)) return global;

  try {
    const raw = await readFile(projectPath, "utf8");
    const projectConfig = normalizeConfig(parseYaml(raw));
    const merged = applyDisableRules(mergeConfig(global.config, projectConfig));
    return { config: merged, source: `${global.source}+project`, warnings: validateRules(merged.rules) };
  } catch {
    return global;
  }
}

function loadGlobalConfigSync(): ConfigLoad {
  for (const configPath of unique(CONFIG_PATHS)) {
    if (!existsSync(configPath)) continue;
    try {
      const raw = readFileSync(configPath, "utf8");
      const config = applyDisableRules(normalizeConfig(parseYaml(raw)));
      return { config, source: configPath, warnings: validateRules(config.rules) };
    } catch {
      return { config: DEFAULT_CONFIG, source: "default(config-error)", warnings: ["config file could not be parsed; using defaults"] };
    }
  }
  return { config: DEFAULT_CONFIG, source: "default", warnings: [] };
}

/** Drop rules whose id appears in disableRules (lets a project relax global rules). */
function applyDisableRules(config: Config): Config {
  const disabled = new Set(config.disableRules);
  if (disabled.size === 0) return config;
  return { ...config, rules: config.rules.filter((rule) => !disabled.has(rule.id)) };
}

/** Validate rule patterns at load time so a broken rule is loud, never a silent fail-open. */
function validateRules(rules: Rule[]): string[] {
  const warnings: string[] = [];
  for (const rule of rules) {
    if (rule.match.commandRegex) {
      try {
        new RegExp(rule.match.commandRegex);
      } catch (error) {
        warnings.push(`rule "${rule.id}" has an invalid commandRegex and will never match: ${formatError(error)}`);
      }
    }
    for (const pattern of [...(rule.match.path?.globAny ?? []), ...(rule.match.path?.except ?? [])]) {
      // Only * and ** are supported; ?, [], {} are matched literally, which silently
      // breaks intent like *.{pem,key}. Warn so the limitation is loud, not a fail-open.
      if (/[?[\]{}]/.test(pattern)) {
        warnings.push(
          `rule "${rule.id}" glob "${pattern}" uses ? [ ] or { } which match literally; only * and ** are supported`,
        );
      }
    }
  }
  return warnings;
}

function normalizeConfig(value: unknown): Config {
  if (!isRecord(value)) return DEFAULT_CONFIG;
  return {
    ...DEFAULT_CONFIG,
    mode: isMode(value.mode) ? value.mode : DEFAULT_CONFIG.mode,
    cycleModes: Array.isArray(value.cycleModes) ? value.cycleModes.filter(isMode) : DEFAULT_CONFIG.cycleModes,
    keymaps: { ...DEFAULT_CONFIG.keymaps, ...(isRecord(value.keymaps) ? value.keymaps : {}) },
    ui: { ...DEFAULT_CONFIG.ui, ...(isRecord(value.ui) ? value.ui : {}) },
    feedback: { ...DEFAULT_CONFIG.feedback, ...(isRecord(value.feedback) ? value.feedback : {}) },
    rules: Array.isArray(value.rules) ? value.rules.filter(isRule) : DEFAULT_CONFIG.rules,
    disableRules: Array.isArray(value.disableRules)
      ? value.disableRules.filter((id): id is string => typeof id === "string")
      : DEFAULT_CONFIG.disableRules,
  };
}

function mergeConfig(base: Config, override: Config): Config {
  return {
    ...base,
    ...override,
    keymaps: { ...base.keymaps, ...override.keymaps },
    ui: { ...base.ui, ...override.ui },
    feedback: { ...base.feedback, ...override.feedback },
    rules: [...base.rules, ...override.rules],
    disableRules: [...base.disableRules, ...override.disableRules],
  };
}

function createStatus(config: Config, mode: Mode, source: string, lastDecision?: DamageControlStatus["lastDecision"]): DamageControlStatus {
  return { enabled: mode !== "off", mode, rulesLoaded: config.rules.length, configSource: source, lastDecision };
}

function formatStatusText(status: DamageControlStatus): string {
  if (status.mode === "off") return " off";
  if (status.mode === "yolo") return " YOLO";
  return ` ${status.mode}`;
}

function buildInvocation(event: ToolCallEvent, cwd: string): Invocation {
  const rawInput = event.input as unknown;
  const input = isRecord(rawInput) ? rawInput : {};
  const command = typeof input.command === "string" ? input.command : undefined;
  const tokens = command ? tokenizeShell(command) : [];
  const program = tokens[0];
  const operations = inferOperations(event.toolName, command, tokens);
  const paths = extractPaths(event.toolName, input, tokens);
  return {
    toolName: event.toolName,
    input,
    display: command ?? truncate(JSON.stringify(input), DISPLAY_MAX_LENGTH),
    command,
    tokens,
    program,
    paths,
    operations,
    cwd,
  };
}

function inferOperations(toolName: string, command: string | undefined, tokens: string[]): Operation[] {
  if (toolName === "read") return ["read"];
  if (["grep", "find", "ls"].includes(toolName)) return ["read", "list"];
  if (toolName === "write") return ["write"];
  if (toolName === "edit") return ["edit", "write"];
  if (toolName !== "bash") return ["execute"];

  const operations = new Set<Operation>(["execute"]);
  if (/\brm\b/.test(command ?? "") || tokens.includes("rm")) operations.add("delete");
  if (/\bmv\b/.test(command ?? "") || tokens.includes("mv")) operations.add("move");
  if (/(^|\s)(>|>>|tee\b)/.test(command ?? "")) operations.add("write");
  if (/\bsed\b.*\s-i\b/.test(command ?? "")) operations.add("edit");
  // So path rules scoped to "read" can also catch bash readers like `cat ~/.ssh/id_rsa`.
  if (tokens[0] && READ_PROGRAMS.has(tokens[0])) operations.add("read");
  return [...operations];
}

const READ_PROGRAMS = new Set([
  "cat", "less", "more", "head", "tail", "bat", "view", "stat", "file", "wc", "nl", "od", "xxd", "strings",
]);

function extractPaths(toolName: string, input: Record<string, unknown>, tokens: string[]): string[] {
  const paths: string[] = [];
  if (["read", "write", "edit", "grep", "find", "ls"].includes(toolName)) {
    paths.push(typeof input.path === "string" ? input.path : ".");
  }
  if (toolName === "grep" && typeof input.glob === "string") paths.push(input.glob);
  if (toolName === "bash") paths.push(...tokens.filter(looksLikePath));
  return unique(paths);
}

function ruleMatches(rule: Rule, invocation: Invocation): boolean {
  const match = rule.match;
  if (match.tool && match.tool !== invocation.toolName) return false;
  if (match.toolsAny && !match.toolsAny.includes(invocation.toolName)) return false;
  if (match.commandRegex && !matchesRegex(invocation.command ?? "", match.commandRegex)) return false;
  if (match.command && !commandMatches(match.command, invocation)) return false;
  if (match.path && !pathMatches(match.path, invocation)) return false;
  return true;
}

function commandMatches(match: CommandMatch, invocation: Invocation): boolean {
  const command = invocation.command ?? "";
  if (match.program && invocation.program !== match.program) return false;
  if (match.startsWith && !command.trimStart().startsWith(match.startsWith)) return false;
  if (match.includesAny && !match.includesAny.some((part) => command.includes(part))) return false;
  if (match.argsSequence && !containsSequence(invocation.tokens, match.argsSequence)) return false;
  if (match.flagsAny && !match.flagsAny.some((flag) => invocation.tokens.some((token) => flagMatches(token, flag)))) return false;
  if (match.flagsAll && !match.flagsAll.every((flag) => invocation.tokens.some((token) => flagMatches(token, flag)))) return false;
  return true;
}

function pathMatches(match: PathMatch, invocation: Invocation): boolean {
  if (match.operationsAny && !match.operationsAny.some((operation) => invocation.operations.includes(operation))) return false;
  const patterns = match.globAny ?? [];
  if (patterns.length === 0) return true;
  return invocation.paths.some((candidate) => {
    const matched = patterns.some((pattern) => pathGlobMatches(candidate, pattern, invocation.cwd));
    if (!matched) return false;
    return !(match.except ?? []).some((pattern) => pathGlobMatches(candidate, pattern, invocation.cwd));
  });
}

function matchesRegex(value: string, pattern: string): boolean {
  try {
    return new RegExp(pattern).test(value);
  } catch {
    return false;
  }
}

function pathGlobMatches(candidate: string, pattern: string, cwd: string): boolean {
  const candidateVariants = pathVariants(candidate, cwd);
  const patternVariants = pathVariants(pattern, cwd);
  return patternVariants.some((glob) => {
    const regex = globToRegExp(toPosixPath(glob));
    return candidateVariants.some((variant) => regex.test(toPosixPath(variant)));
  });
}

function pathVariants(value: string, cwd: string): string[] {
  const expanded = expandHome(value);
  const absolute = isAbsolute(expanded) ? expanded : resolve(cwd, expanded);
  return unique([value, expanded, absolute, relative(cwd, absolute)]);
}

const globRegexCache = new Map<string, RegExp>();

function globToRegExp(glob: string): RegExp {
  const cached = globRegexCache.get(glob);
  if (cached) return cached;
  let pattern = "";
  for (let i = 0; i < glob.length; i++) {
    const char = glob[i];
    const next = glob[i + 1];
    if (char === "*" && next === "*") {
      pattern += ".*";
      i++;
    } else if (char === "*") {
      pattern += "[^/]*";
    } else {
      pattern += escapeRegex(char ?? "");
    }
  }
  const regex = new RegExp(`(^|.*/)${pattern}($|/.*)`);
  globRegexCache.set(glob, regex);
  return regex;
}

function tokenizeShell(command: string): string[] {
  const tokens: string[] = [];
  let current = "";
  let quote: "'" | '"' | undefined;
  let escaped = false;

  for (const char of command) {
    if (escaped) {
      current += char;
      escaped = false;
      continue;
    }
    if (char === "\\" && quote !== "'") {
      escaped = true;
      continue;
    }
    if ((char === "'" || char === '"') && !quote) {
      quote = char;
      continue;
    }
    if (char === quote) {
      quote = undefined;
      continue;
    }
    if (/\s/.test(char) && !quote) {
      if (current) tokens.push(current);
      current = "";
      continue;
    }
    current += char;
  }
  if (current) tokens.push(current);
  return tokens;
}

function looksLikePath(token: string): boolean {
  if (!token || token.startsWith("-")) return false;
  return token.startsWith(".") || token.startsWith("/") || token.startsWith("~") || token.includes("/");
}

function containsSequence(tokens: string[], sequence: string[]): boolean {
  if (sequence.length === 0) return true;
  for (let index = 0; index <= tokens.length - sequence.length; index++) {
    if (sequence.every((expected, offset) => tokens[index + offset] === expected)) return true;
  }
  return false;
}

function flagMatches(token: string, flag: string): boolean {
  if (token === flag) return true;
  if (!flag.startsWith("-") || flag.startsWith("--") || !token.startsWith("-") || token.startsWith("--")) return false;
  const shortFlag = flag.replace(/^-+/, "");
  return shortFlag.length === 1 && token.slice(1).includes(shortFlag);
}

function buildAgentFeedback(invocation: Invocation, decision: Decision, config: Config): string {
  const lines = [
    ` Damage Control blocked ${invocation.toolName}: ${decision.reason}`,
    "",
    "Attempted:",
    invocation.display,
    "",
    "Do not retry this exact call or attempt an equivalent workaround.",
  ];
  const hint = decision.rule?.feedback?.agentHint;
  if (hint) lines.push("", `User preference: ${hint}`);
  if (config.feedback.includeAdaptationHints) {
    lines.push(
      "",
      "If this was destructive, stop and ask the user how to proceed.",
      "If this was only a verification step, continue without the protected data or ask the user explicitly.",
    );
  }
  return lines.join("\n");
}

function getApprovalKey(invocation: Invocation): string {
  if (invocation.command) return `${invocation.toolName}:${invocation.command}`;
  // For non-command tools, key on a stable (key-sorted) and length-bounded view of
  // the input so the cache is order-independent and never stores full file payloads.
  return `${invocation.toolName}:${stableStringify(sanitizeInput(invocation.input))}`;
}

/** Deterministic JSON: object keys sorted at every depth so key order never changes the result. */
function stableStringify(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  if (isRecord(value)) {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value) ?? "null";
}

/** True when the invocation only reads/lists, so it is safe to allow in whitelist mode. */
function isReadOnly(invocation: Invocation): boolean {
  return invocation.operations.length > 0 && invocation.operations.every((op) => op === "read" || op === "list");
}

function truncate(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max)}… (${value.length - max} more chars)` : value;
}

/** Clip long string fields so dialogs and logs never dump full file contents (e.g. write payloads). */
function sanitizeInput(input: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, val] of Object.entries(input)) {
    result[key] = typeof val === "string" ? truncate(val, DISPLAY_MAX_LENGTH) : val;
  }
  return result;
}

function isRule(value: unknown): value is Rule {
  if (!isRecord(value) || !isRecord(value.match)) return false;
  return typeof value.id === "string" && typeof value.description === "string" && isAction(value.action);
}

function isAction(value: unknown): value is Action {
  return value === "allow" || value === "ask" || value === "block";
}

function isMode(value: unknown): value is Mode {
  return value === "off" || value === "yolo" || value === "blacklist" || value === "whitelist" || value === "ask";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function expandHome(value: string): string {
  return value === "~" ? homedir() : value.startsWith("~/") ? resolve(homedir(), value.slice(2)) : value;
}

function toPosixPath(value: string): string {
  return value.replace(/\\/g, "/");
}

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function unique<T>(items: T[]): T[] {
  return [...new Set(items)];
}

function formatError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export type { DamageControlStatus };
