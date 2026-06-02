/**
 * Prompt status editor — owns only the prompt box.
 *
 * Top border: provider/model + thinking level.
 */
import {
  CustomEditor,
  type ExtensionAPI,
  type KeybindingsManager,
  type Theme,
} from "@earendil-works/pi-coding-agent";
import type { EditorTheme, TUI } from "@earendil-works/pi-tui";
import { truncateToWidth, visibleWidth } from "@earendil-works/pi-tui";

type PromptModel = {
  provider?: string;
  id?: string;
};

function fitBorder(
  left: string,
  right: string,
  width: number,
  border: (text: string) => string,
  fill: (text: string) => string = border,
): string {
  if (width <= 0) return "";
  if (width === 1) return border("─");

  let leftText = left;
  let rightText = right;
  const fixedWidth = 2;
  const minimumGap = 3;

  while (
    fixedWidth + visibleWidth(leftText) + visibleWidth(rightText) + minimumGap > width &&
    visibleWidth(rightText) > 0
  ) {
    rightText = truncateToWidth(rightText, Math.max(0, visibleWidth(rightText) - 1), "");
  }
  while (
    fixedWidth + visibleWidth(leftText) + visibleWidth(rightText) + minimumGap > width &&
    visibleWidth(leftText) > 0
  ) {
    leftText = truncateToWidth(leftText, Math.max(0, visibleWidth(leftText) - 1), "");
  }

  const leftPrefix = leftText ? border("──") : border("─");
  const gapWidth = Math.max(
    0,
    width - visibleWidth(leftPrefix) - visibleWidth(leftText) - visibleWidth(rightText) - 1,
  );
  return `${leftPrefix}${leftText}${fill("─".repeat(gapWidth))}${rightText}${border("─")}`;
}

function blue(text: string): string {
  return `\x1b[38;2;88;166;255m${text}\x1b[39m`;
}

function formatModel(model: PromptModel | undefined, thinking: string | undefined, theme: Theme): string {
  const provider = model?.provider;
  const id = model?.id ?? "no-model";
  const maxModelWidth = 46;
  const rawModelText = provider ? `${provider}/${id}` : id;

  let modelText: string;
  if (visibleWidth(rawModelText) > maxModelWidth) {
    modelText = theme.fg("text", truncateToWidth(rawModelText, maxModelWidth, "…"));
  } else if (provider) {
    modelText = theme.fg("muted", `${provider}/`) + theme.fg("text", id);
  } else {
    modelText = theme.fg("text", id);
  }

  return (
    " " +
    modelText +
    blue(` [${thinking ?? "off"}]`) +
    " "
  );
}

class PromptStatusEditor extends CustomEditor {
  constructor(
    tui: TUI,
    editorTheme: EditorTheme,
    keybindings: KeybindingsManager,
    private readonly getTopLeft: () => string,
  ) {
    super(tui, editorTheme, keybindings, { paddingX: 2 });
  }

  render(width: number): string[] {
    const lines = super.render(width);
    if (lines.length === 0) return lines;

    const borderColor = (text: string) => this.borderColor(text);
    lines[0] = fitBorder(this.getTopLeft(), "", width, borderColor);
    return lines;
  }
}

export default function (pi: ExtensionAPI) {
  pi.on("session_start", (_event, ctx) => {
    if (!ctx.hasUI) return;

    ctx.ui.setEditorComponent((tui: TUI, editorTheme: EditorTheme, keybindings: KeybindingsManager) =>
      new PromptStatusEditor(
        tui,
        editorTheme,
        keybindings,
        () => formatModel(ctx.model, pi.getThinkingLevel(), ctx.ui.theme),
      ),
    );
  });
}
