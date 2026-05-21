/**
 * Footer — Rich custom status bar
 *
 * Line 1: provider/model + [thinking] + context meter on left, tokens + cost on right
 * Line 2: OpenAI/Codex limits, only for OpenAI models
 * Line 3: cwd (branch) on left, tool tally on right
 *
 * Usage: pi -e extensions/footer.ts
 */

import type { AssistantMessage } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { truncateToWidth, visibleWidth } from "@earendil-works/pi-tui";
import os from "node:os";
import path from "node:path";

type FooterModel = {
	provider?: string;
	id?: string;
};

const footerPalette = {
	modelProvider: "#9198a1",
	modelId: "#f0f3f6",
	thinking: "#91cbff",
	bracket: "#3d444d",
	progress: "#4ae168",
	emptyProgress: "#3d444d",
	context: "#71b7ff",
	muted: "#6e7681",
	separator: "#3d444d",
	input: "#4ae168",
	output: "#91cbff",
	cost: "#f0b72f",
	limit5h: "#39c5cf",
	limitWeekly: "#71b7ff",
	cwd: "#9198a1",
	branch: "#f0b72f",
	tool: "#91cbff",
} as const;

function hexFg(hex: string, text: string): string {
	const color = hex.replace(/^#/, "");
	const r = Number.parseInt(color.slice(0, 2), 16);
	const g = Number.parseInt(color.slice(2, 4), 16);
	const b = Number.parseInt(color.slice(4, 6), 16);
	return `\x1b[38;2;${r};${g};${b}m${text}\x1b[39m`;
}

function isOpenAIModel(model: FooterModel | undefined): boolean {
	if (!model) return false;
	const provider = model.provider ?? "";
	return provider === "openai" || provider.startsWith("openai-") || provider.startsWith("openai/");
}

function sanitizeStatusText(text: string): string {
	return text.replace(/[\r\n\t]/g, " ").replace(/ +/g, " ").trim();
}

function formatCodexUsageForFooter(status: string): string | undefined {
	const cleaned = sanitizeStatusText(status).replace(/^📊\s*/, "").trim();
	const match = cleaned.match(/(\d+)%\s+5h(?:\s+(\d+)%\s+wk)?/i);
	if (!match) return cleaned && cleaned !== "checking" ? hexFg(footerPalette.muted, cleaned) : undefined;

	const fiveHour = hexFg(footerPalette.limit5h, `5h ${match[1]}% left`);
	const weekly = match[2]
		? hexFg(footerPalette.muted, " · ") + hexFg(footerPalette.limitWeekly, `weekly ${match[2]}% left`)
		: "";
	return fiveHour + weekly;
}

export default function (pi: ExtensionAPI) {
	const counts: Record<string, number> = {};

	pi.on("tool_execution_end", async (event) => {
		counts[event.toolName] = (counts[event.toolName] || 0) + 1;
	});

	pi.on("session_start", async (_event, ctx) => {
		ctx.ui.setFooter((tui, _theme, footerData) => {
			const unsub = footerData.onBranchChange(() => tui.requestRender());

			return {
				dispose: unsub,
				invalidate() {},
				render(width: number): string[] {
					// --- Line 1: model + context meter (left), tokens + cost (right) ---
					let tokIn = 0;
					let tokOut = 0;
					let cost = 0;
					for (const entry of ctx.sessionManager.getBranch()) {
						if (entry.type === "message" && entry.message.role === "assistant") {
							const m = entry.message as AssistantMessage;
							tokIn += m.usage.input;
							tokOut += m.usage.output;
							cost += m.usage.cost.total;
						}
					}

					const fmt = (n: number) => n < 1000 ? `${n}` : `${(n / 1000).toFixed(1)}k`;
					const home = os.homedir();
					const dir = ctx.cwd.startsWith(home) ? `~/${path.relative(home, ctx.cwd)}` : ctx.cwd;
					const branch = footerData.getGitBranch();

					// --- Line 1: model + context meter (left), tokens + cost (right) ---
					const usage = ctx.getContextUsage();
					const pct = usage?.percent ?? 0;
					const filled = Math.round(pct / 10) || 1;
					const model = ctx.model
						? `${ctx.model.provider}/${ctx.model.id}`
						: "no-model";
					const [modelProvider, ...modelIdParts] = model.split("/");
					const modelId = modelIdParts.join("/");
					const thinkingLevel = pi.getThinkingLevel();
					const thinking = thinkingLevel ? ` [${thinkingLevel}]` : "";

					const ctxWindow = usage ? usage.contextWindow : 0;
					const ctxTokens = usage?.tokens ?? (tokIn + tokOut);
					const codexStatus = isOpenAIModel(ctx.model)
						? footerData.getExtensionStatuses().get("codex-usage")
						: undefined;
					const codexUsage = codexStatus ? formatCodexUsageForFooter(codexStatus) : undefined;

					const modelDisplay = modelId
						? hexFg(footerPalette.modelProvider, ` ${modelProvider}/`) + hexFg(footerPalette.modelId, modelId)
						: hexFg(footerPalette.modelId, ` ${model}`);
					const l1Left =
						modelDisplay +
						hexFg(footerPalette.thinking, thinking) +
						hexFg(footerPalette.muted, " ") +
						hexFg(footerPalette.bracket, "[") +
						hexFg(footerPalette.progress, "#".repeat(filled)) +
						hexFg(footerPalette.emptyProgress, "-".repeat(10 - filled)) +
						hexFg(footerPalette.bracket, "]") +
						hexFg(footerPalette.muted, " ") +
						hexFg(footerPalette.context, `${Math.round(pct)}%`) +
						hexFg(footerPalette.muted, ` (${fmt(ctxTokens)}/${fmt(ctxWindow)})`);

					const sep = hexFg(footerPalette.separator, " · ");
					const sep2 = hexFg(footerPalette.separator, " │ ");
					const l1Right =
						hexFg(footerPalette.input, `${fmt(tokIn)}`) +
						hexFg(footerPalette.muted, " in") + sep +
						hexFg(footerPalette.output, `${fmt(tokOut)}`) +
						hexFg(footerPalette.muted, " out") + sep2 +
						hexFg(footerPalette.cost, `$${cost.toFixed(4)}`) +
						hexFg(footerPalette.muted, " ");

					const pad1 = " ".repeat(Math.max(1, width - visibleWidth(l1Left) - visibleWidth(l1Right)));
					const line1 = truncateToWidth(l1Left + pad1 + l1Right, width, "");

					// --- Line 2: cwd + branch (left), tool tally (right) ---
					const l2Left =
						hexFg(footerPalette.cwd, ` ${dir}`) +
						(branch
							? hexFg(footerPalette.muted, " ") + hexFg(footerPalette.separator, "(") + hexFg(footerPalette.branch, branch) + hexFg(footerPalette.separator, ")")
							: "");

					const entries = Object.entries(counts);
					const l2Right = entries.length === 0
						? hexFg(footerPalette.muted, "waiting for tools ")
						: entries.map(
							([name, count]) =>
								hexFg(footerPalette.tool, name) + hexFg(footerPalette.muted, " ") + hexFg(footerPalette.input, `${count}`)
						).join(hexFg(footerPalette.separator, " │ ")) + hexFg(footerPalette.muted, " ");

					const pad2 = " ".repeat(Math.max(1, width - visibleWidth(l2Left) - visibleWidth(l2Right)));
					const line2 = truncateToWidth(l2Left + pad2 + l2Right, width, "");
					const limitsLine = codexUsage
						? truncateToWidth(hexFg(footerPalette.muted, " limits ") + codexUsage, width, "")
						: undefined;

					return limitsLine ? [line1, limitsLine, line2] : [line1, line2];
				},
			};
		});
	});
}
