import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { isToolCallEventType, SettingsManager } from "@earendil-works/pi-coding-agent";
import { parse as yamlParse } from "yaml";
import { readFileSync, existsSync } from "node:fs";
import { join, resolve, isAbsolute, relative } from "node:path";
import { homedir } from "node:os";

interface Rule {
  pattern: string;
  reason: string;
  ask?: boolean;
}

interface Rules {
  bashToolPatterns: Rule[];
  zeroAccessPaths: string[];
  readOnlyPaths: string[];
  noDeletePaths: string[];
}

export default function (pi: ExtensionAPI) {
  let rules: Rules = {
    bashToolPatterns: [],
    zeroAccessPaths: [],
    readOnlyPaths: [],
    noDeletePaths: [],
  };

  function resolvePath(p: string, cwd: string): string {
    if (p.startsWith("~")) {
      p = join(homedir(), p.slice(1));
    }
    return resolve(cwd, p);
  }

  function isQuietStartup(cwd: string): boolean {
    try {
      return SettingsManager.create(cwd).getQuietStartup();
    } catch {
      return false;
    }
  }

  function escapeRegExp(value: string): string {
    return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function commandMayModifyPath(command: string, pathPattern: string): boolean {
    const normalized = pathPattern.endsWith("/") ? pathPattern.slice(0, -1) : pathPattern;
    const pathRef = `(?:\\./)?${escapeRegExp(normalized)}(?:/|\\b)`;
    const segmentWithPath = `[^|;&\\n]*${pathRef}`;

    return (
      new RegExp(`\\b(rm|mv|cp|install|mkdir|touch|chmod|chown|truncate)\\b${segmentWithPath}`).test(
        command,
      ) ||
      new RegExp(`\\bsed\\b[^|;&\\n]*\\s-i\\b${segmentWithPath}`).test(command) ||
      new RegExp(`\\bperl\\b[^|;&\\n]*\\s-i\\b${segmentWithPath}`).test(command) ||
      new RegExp(`(?:>|>>|2>|&>|\\btee\\s+(?:-a\\s+)?)\\s*["']?${pathRef}`).test(command)
    );
  }

  function commandMayDeleteOrMovePath(command: string, pathPattern: string): boolean {
    const normalized = pathPattern.endsWith("/") ? pathPattern.slice(0, -1) : pathPattern;
    const pathRef = `(?:\\./)?${escapeRegExp(normalized)}(?:/|\\b)`;
    return new RegExp(`\\b(rm|mv)\\b[^|;&\\n]*${pathRef}`).test(command);
  }

  function isPathMatch(targetPath: string, pattern: string, cwd: string): boolean {
    const resolvedPattern = pattern.startsWith("~") ? join(homedir(), pattern.slice(1)) : pattern;

    if (resolvedPattern.endsWith("/")) {
      const absolutePattern = isAbsolute(resolvedPattern)
        ? resolvedPattern
        : resolve(cwd, resolvedPattern);
      return targetPath.startsWith(absolutePattern);
    }

    const regexPattern = resolvedPattern.replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*");

    const regex = new RegExp(
      `^${regexPattern}$|^${regexPattern}/|/${regexPattern}$|/${regexPattern}/`,
    );
    const relPath = relative(cwd, targetPath);

    return (
      regex.test(targetPath) ||
      regex.test(relPath) ||
      targetPath.includes(resolvedPattern) ||
      relPath.includes(resolvedPattern)
    );
  }

  pi.on("session_start", async (event, ctx) => {
    const quietStartup = event.reason === "startup" && isQuietStartup(ctx.cwd);
    const rulesPath = join(ctx.cwd, "damage-control-rules.yaml");
    try {
      if (existsSync(rulesPath)) {
        const content = readFileSync(rulesPath, "utf8");
        const loaded = yamlParse(content) as Partial<Rules>;
        rules = {
          bashToolPatterns: loaded.bashToolPatterns || [],
          zeroAccessPaths: loaded.zeroAccessPaths || [],
          readOnlyPaths: loaded.readOnlyPaths || [],
          noDeletePaths: loaded.noDeletePaths || [],
        };
        if (!quietStartup) {
          ctx.ui.notify(
            `🛡️ Damage-Control: Loaded ${rules.bashToolPatterns.length + rules.zeroAccessPaths.length + rules.readOnlyPaths.length + rules.noDeletePaths.length} rules.`,
          );
        }
      } else if (!quietStartup) {
        ctx.ui.notify("🛡️ Damage-Control: No rules found at damage-control-rules.yaml");
      }
    } catch (err) {
      ctx.ui.notify(
        `🛡️ Damage-Control: Failed to load rules: ${err instanceof Error ? err.message : String(err)}`,
      );
    }

    ctx.ui.setStatus(
      "damage-control",
      `🛡️ Damage-Control Active: ${rules.bashToolPatterns.length + rules.zeroAccessPaths.length + rules.readOnlyPaths.length + rules.noDeletePaths.length} Rules`,
    );
  });

  pi.on("tool_call", async (event, ctx) => {
    let violationReason: string | null = null;
    let shouldAsk = false;

    const checkPaths = (pathsToCheck: string[]) => {
      for (const p of pathsToCheck) {
        const resolved = resolvePath(p, ctx.cwd);
        for (const zap of rules.zeroAccessPaths) {
          if (isPathMatch(resolved, zap, ctx.cwd)) {
            return `Access to zero-access path restricted: ${zap}`;
          }
        }
      }
      return null;
    };

    const inputPaths: string[] = [];
    if (
      isToolCallEventType("read", event) ||
      isToolCallEventType("write", event) ||
      isToolCallEventType("edit", event)
    ) {
      inputPaths.push(event.input.path);
    } else if (
      isToolCallEventType("grep", event) ||
      isToolCallEventType("find", event) ||
      isToolCallEventType("ls", event)
    ) {
      inputPaths.push(event.input.path || ".");
    }

    if (isToolCallEventType("grep", event) && event.input.glob) {
      for (const zap of rules.zeroAccessPaths) {
        if (event.input.glob.includes(zap) || isPathMatch(event.input.glob, zap, ctx.cwd)) {
          violationReason = `Glob matches zero-access path: ${zap}`;
          break;
        }
      }
    }

    if (!violationReason) {
      violationReason = checkPaths(inputPaths);
    }

    if (!violationReason) {
      if (isToolCallEventType("bash", event)) {
        const command = event.input.command;

        for (const rule of rules.bashToolPatterns) {
          const regex = new RegExp(rule.pattern);
          if (regex.test(command)) {
            violationReason = rule.reason;
            shouldAsk = !!rule.ask;
            break;
          }
        }

        if (!violationReason) {
          for (const zap of rules.zeroAccessPaths) {
            if (command.includes(zap)) {
              violationReason = `Bash command references zero-access path: ${zap}`;
              break;
            }
          }
        }

        if (!violationReason) {
          for (const rop of rules.readOnlyPaths) {
            if (commandMayModifyPath(command, rop)) {
              violationReason = `Bash command may modify read-only path: ${rop}`;
              break;
            }
          }
        }

        if (!violationReason) {
          for (const ndp of rules.noDeletePaths) {
            if (commandMayDeleteOrMovePath(command, ndp)) {
              violationReason = `Bash command attempts to delete/move protected path: ${ndp}`;
              break;
            }
          }
        }
      } else if (isToolCallEventType("write", event) || isToolCallEventType("edit", event)) {
        for (const p of inputPaths) {
          const resolved = resolvePath(p, ctx.cwd);
          for (const rop of rules.readOnlyPaths) {
            if (isPathMatch(resolved, rop, ctx.cwd)) {
              violationReason = `Modification of read-only path restricted: ${rop}`;
              break;
            }
          }
        }
      }
    }

    if (violationReason) {
      if (shouldAsk) {
        const confirmed = await ctx.ui.confirm(
          "🛡️ Damage-Control Confirmation",
          `Dangerous command detected: ${violationReason}\n\nCommand: ${isToolCallEventType("bash", event) ? event.input.command : JSON.stringify(event.input)}\n\nDo you want to proceed?`,
          { timeout: 30000 },
        );

        if (!confirmed) {
          ctx.ui.setStatus("damage-control", `⚠️ Last Violation Blocked: ${violationReason.slice(0, 30)}...`);
          pi.appendEntry("damage-control-log", {
            tool: event.toolName,
            input: event.input,
            rule: violationReason,
            action: "blocked_by_user",
          });
          return {
            block: true,
            reason: `🛑 BLOCKED by Damage-Control: ${violationReason} (User denied)\n\nDO NOT attempt to work around this restriction. DO NOT retry with alternative commands, paths, or approaches that achieve the same result. Report this block to the user exactly as stated and ask how they would like to proceed.`,
          };
        } else {
          pi.appendEntry("damage-control-log", {
            tool: event.toolName,
            input: event.input,
            rule: violationReason,
            action: "confirmed_by_user",
          });
          return { block: false };
        }
      } else {
        ctx.ui.notify(`🛑 Damage-Control: Blocked ${event.toolName} due to ${violationReason}`);
        ctx.ui.setStatus("damage-control", `⚠️ Last Violation: ${violationReason.slice(0, 30)}...`);
        pi.appendEntry("damage-control-log", {
          tool: event.toolName,
          input: event.input,
          rule: violationReason,
          action: "blocked",
        });
        return {
          block: true,
          reason: `🛑 BLOCKED by Damage-Control: ${violationReason}\n\nDO NOT attempt to work around this restriction. DO NOT retry with alternative commands, paths, or approaches that achieve the same result. Report this block to the user exactly as stated and ask how they would like to proceed.`,
        };
      }
    }

    return { block: false };
  });
}
