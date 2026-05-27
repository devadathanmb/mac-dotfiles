import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import type { AutocompleteItem } from "@earendil-works/pi-tui";
import { execFile } from "node:child_process";
import { statSync } from "node:fs";
import { basename, isAbsolute, join } from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const MAX_RESULTS = 100;
const MAX_ITEMS = 20;
const FD_COMMAND = process.env.PI_FD_COMMAND || "fd";
const PATH_DELIMITERS = new Set([" ", "\t", '"', "'", "="]);

function toDisplayPath(value: string): string {
  return value.replace(/\\/g, "/");
}

function findLastDelimiter(text: string): number {
  for (let i = text.length - 1; i >= 0; i -= 1) {
    if (PATH_DELIMITERS.has(text[i] ?? "")) return i;
  }
  return -1;
}

function findUnclosedQuoteStart(text: string): number | undefined {
  let quoteStart: number | undefined;
  let inQuotes = false;
  for (let i = 0; i < text.length; i += 1) {
    if (text[i] === '"') {
      inQuotes = !inQuotes;
      quoteStart = inQuotes ? i : undefined;
    }
  }
  return quoteStart;
}

function extractAtPrefix(text: string): string | undefined {
  const quoteStart = findUnclosedQuoteStart(text);
  if (quoteStart !== undefined && quoteStart > 0 && text[quoteStart - 1] === "@") {
    const tokenStart = quoteStart - 1;
    if (tokenStart === 0 || PATH_DELIMITERS.has(text[tokenStart - 1] ?? "")) {
      return text.slice(tokenStart);
    }
  }

  const lastDelimiter = findLastDelimiter(text);
  const tokenStart = lastDelimiter === -1 ? 0 : lastDelimiter + 1;
  return text[tokenStart] === "@" ? text.slice(tokenStart) : undefined;
}

function parseAtPrefix(prefix: string): { rawQuery: string; quoted: boolean } {
  if (prefix.startsWith('@"')) return { rawQuery: prefix.slice(2), quoted: true };
  return { rawQuery: prefix.slice(1), quoted: false };
}

function completionValue(displayPath: string, quoted: boolean): string {
  const needsQuotes = quoted || displayPath.includes(" ");
  return needsQuotes ? `@"${displayPath}"` : `@${displayPath}`;
}

function trimTrailingSlashes(value: string): string {
  return value.replace(/\/+$/g, "");
}

function scoreEntry(filePath: string, query: string, isDirectory: boolean): number {
  if (!query) return isDirectory ? 2 : 1;
  const filename = basename(trimTrailingSlashes(filePath)).toLowerCase();
  const lowerPath = filePath.toLowerCase();
  const lowerQuery = query.toLowerCase();
  let score = 0;
  if (filename === lowerQuery) score = 100;
  else if (filename.startsWith(lowerQuery)) score = 80;
  else if (filename.includes(lowerQuery)) score = 50;
  else if (lowerPath.includes(lowerQuery)) score = 30;
  if (isDirectory && score > 0) score += 10;
  return score;
}

function scopedQuery(
  cwd: string,
  rawQuery: string,
): { baseDir: string; fdQuery: string; displayBase: string } {
  const normalized = toDisplayPath(rawQuery);
  const slashIndex = normalized.lastIndexOf("/");
  if (slashIndex === -1) return { baseDir: cwd, fdQuery: normalized, displayBase: "" };

  const displayBase = normalized.slice(0, slashIndex + 1);
  const fdQuery = normalized.slice(slashIndex + 1);
  const baseDir = isAbsolute(displayBase) ? displayBase : join(cwd, displayBase);
  try {
    if (statSync(baseDir).isDirectory()) return { baseDir, fdQuery, displayBase };
  } catch {
    // Fall back to searching from cwd if the scoped directory does not exist.
  }
  return { baseDir: cwd, fdQuery: normalized, displayBase: "" };
}

async function getNoIgnoreAtSuggestions(
  cwd: string,
  query: string,
  quoted: boolean,
): Promise<AutocompleteItem[]> {
  const scope = scopedQuery(cwd, query);
  const fdArgs = [
    "--base-directory",
    scope.baseDir,
    "--max-results",
    String(MAX_RESULTS),
    "--type",
    "f",
    "--type",
    "d",
    "--follow",
    "--hidden",
    "--no-ignore",
    "--exclude",
    ".git",
    "--exclude",
    ".git/*",
    "--exclude",
    ".git/**",
  ];
  if (scope.fdQuery.includes("/")) fdArgs.push("--full-path");
  if (scope.fdQuery) fdArgs.push(scope.fdQuery);

  try {
    const { stdout } = await execFileAsync(FD_COMMAND, fdArgs, {
      timeout: 1500,
      maxBuffer: 512 * 1024,
    });
    return stdout
      .split("\n")
      .map((line) => trimTrailingSlashes(toDisplayPath(line.trim())))
      .filter(Boolean)
      .map((filePath) => {
        let isDirectory = false;
        try {
          isDirectory = statSync(join(scope.baseDir, filePath)).isDirectory();
        } catch {
          // Keep the result as a file if it disappears or cannot be stat'ed.
        }
        const displayPath = `${scope.displayBase}${filePath}`;
        return {
          filePath,
          displayPath,
          isDirectory,
          score: scoreEntry(filePath, scope.fdQuery, isDirectory),
        };
      })
      .filter((entry) => entry.score > 0)
      .sort((a, b) => b.score - a.score || a.displayPath.localeCompare(b.displayPath))
      .slice(0, MAX_ITEMS)
      .map(({ displayPath, isDirectory }) => {
        const completedPath = isDirectory ? `${displayPath}/` : displayPath;
        return {
          value: completionValue(completedPath, quoted),
          label: basename(displayPath) + (isDirectory ? "/" : ""),
          description: completedPath,
        };
      });
  } catch {
    return [];
  }
}

export default function gitignoredAtFiles(pi: ExtensionAPI) {
  pi.on("session_start", (_event, ctx) => {
    // Probe for fd availability so the user knows why autocomplete may not work.
    void (async () => {
      try {
        await execFileAsync(FD_COMMAND, ["--version"], { timeout: 2000 });
      } catch {
        ctx.ui.notify(
          `gitignored @-autocomplete requires '${FD_COMMAND}' (https://github.com/sharkdp/fd). Install it or set PI_FD_COMMAND.`,
          "warning",
        );
      }
    })();

    ctx.ui.addAutocompleteProvider((current) => ({
      async getSuggestions(lines, cursorLine, cursorCol, options) {
        const line = lines[cursorLine] ?? "";
        const beforeCursor = line.slice(0, cursorCol);
        const atPrefix = extractAtPrefix(beforeCursor);
        if (!atPrefix) return current.getSuggestions(lines, cursorLine, cursorCol, options);

        const { rawQuery, quoted } = parseAtPrefix(atPrefix);
        const items = await getNoIgnoreAtSuggestions(ctx.cwd, rawQuery, quoted);
        if (items.length === 0)
          return current.getSuggestions(lines, cursorLine, cursorCol, options);
        return { prefix: atPrefix, items };
      },

      applyCompletion(lines, cursorLine, cursorCol, item, prefix) {
        return current.applyCompletion(lines, cursorLine, cursorCol, item, prefix);
      },

      shouldTriggerFileCompletion(lines, cursorLine, cursorCol) {
        return current.shouldTriggerFileCompletion?.(lines, cursorLine, cursorCol) ?? true;
      },
    }));
  });
}
