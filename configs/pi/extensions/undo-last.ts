import type {
	ExtensionAPI,
	ExtensionCommandContext,
	ExtensionContext,
} from "@earendil-works/pi-coding-agent";

type SessionEntryLike = {
	id: string;
	parentId: string | null;
	type: string;
	message?: {
		role?: string;
		content?: unknown;
	};
};

type TextBlock = {
	type: "text";
	text: string;
};

type PendingReEdit = {
	restoreLeafId: string | null;
	previousEditorText: string;
};

const STATUS_KEY = "undo-last";
let pendingReEdits: PendingReEdit[] = [];

function updatePendingReEditStatus(ctx?: ExtensionContext | ExtensionCommandContext) {
	if (!ctx || pendingReEdits.length === 0) {
		ctx?.ui.setStatus(STATUS_KEY, undefined);
		return;
	}

	const count = pendingReEdits.length;
	const message = `amending ${count} message${count === 1 ? "" : "s"} — /undo-cancel cancels the latest`;
	ctx.ui.setStatus(STATUS_KEY, ctx.ui.theme.fg("warning", message));
}

function clearPendingReEdits(ctx?: ExtensionContext | ExtensionCommandContext) {
	pendingReEdits = [];
	updatePendingReEditStatus(ctx);
}

function isTextBlock(block: unknown): block is TextBlock {
	return (
		typeof block === "object" &&
		block !== null &&
		(block as { type?: unknown }).type === "text" &&
		typeof (block as { text?: unknown }).text === "string"
	);
}

function getEditableUserText(entry: SessionEntryLike): string | undefined {
	if (entry.type !== "message" || entry.message?.role !== "user") return undefined;

	const content = entry.message.content;
	if (typeof content === "string") return content.length > 0 ? content : undefined;

	if (!Array.isArray(content)) return undefined;

	const text = content.filter(isTextBlock).map((block) => block.text).join("\n");
	return text.length > 0 ? text : undefined;
}

function hasNonTextContent(entry: SessionEntryLike): boolean {
	const content = entry.message?.content;
	return Array.isArray(content) && content.some((block) => !isTextBlock(block));
}

function parseOffset(args: string, ctx: ExtensionCommandContext): number | undefined {
	const trimmed = args.trim();
	if (!trimmed) return 1;

	const offset = Number(trimmed);
	if (Number.isInteger(offset) && offset > 0) return offset;

	ctx.ui.notify("Usage: /undo [positive-number]", "warning");
	return undefined;
}

async function restoreLatestPendingReEdit(ctx: ExtensionCommandContext, notify: boolean): Promise<boolean> {
	const pending = pendingReEdits.at(-1);
	if (!pending) return false;

	if (pending.restoreLeafId) {
		const result = await ctx.navigateTree(pending.restoreLeafId, { summarize: false });
		if (result.cancelled) return false;
	}

	pendingReEdits.pop();
	ctx.ui.setEditorText(pending.previousEditorText);
	updatePendingReEditStatus(ctx);
	if (notify) ctx.ui.notify("Cancelled message edit", "info");
	return true;
}

async function reEditUserMessage(args: string, ctx: ExtensionCommandContext) {
	await ctx.waitForIdle();

	const offset = parseOffset(args, ctx);
	if (offset === undefined) return;

	const restoreLeafId = ctx.sessionManager.getLeafId();
	const previousEditorText = ctx.ui.getEditorText();
	const userEntries = ctx.sessionManager
		.getBranch()
		.filter((entry: SessionEntryLike) => getEditableUserText(entry) !== undefined);
	const target = userEntries.at(-offset);

	if (!target) {
		ctx.ui.notify("No previous user message found", "warning");
		return;
	}

	const text = getEditableUserText(target);
	if (!text) {
		ctx.ui.notify("That user message has no editable text", "warning");
		return;
	}

	if (!target.parentId) {
		await ctx.fork(target.id, {
			position: "before",
			withSession: async (newCtx) => {
				newCtx.ui.setEditorText(text);
			},
		});
		return;
	}

	const result = await ctx.navigateTree(target.parentId, { summarize: false });
	if (result.cancelled) return;

	pendingReEdits.push({ restoreLeafId, previousEditorText });
	ctx.ui.setEditorText(text);
	updatePendingReEditStatus(ctx);

	if (hasNonTextContent(target)) {
		ctx.ui.notify("Re-editing text only; attachments are not restored", "warning");
	}
}

async function cancelReEdit(_args: string, ctx: ExtensionCommandContext) {
	await ctx.waitForIdle();

	if (!(await restoreLatestPendingReEdit(ctx, true))) {
		ctx.ui.notify("No pending message edit to cancel", "info");
	}
}

export default function (pi: ExtensionAPI) {
	pi.on("session_start", (_event, ctx) => clearPendingReEdits(ctx));

	pi.on("input", (event, ctx) => {
		if (pendingReEdits.length > 0 && event.source === "interactive") clearPendingReEdits(ctx);
	});

	pi.registerCommand("undo", {
		description: "Re-edit the previous user message. Repeat to walk backward; use /undo 2 to skip messages.",
		handler: reEditUserMessage,
	});

	pi.registerCommand("undo-cancel", {
		description: "Cancel a pending /undo edit.",
		handler: cancelReEdit,
	});
}
