const { Plugin, Notice } = require("obsidian");

module.exports = class GlobalVimNavigation extends Plugin {
  onload() {
    this.addCommand({
      id: "copy-context-link",
      name: "Copy context link",
      editorCallback: async (editor, view) => {
        if (!view.file) {
          new Notice("Open a Markdown file to copy its context link.");
          return;
        }
        const from = editor.getCursor("from");
        const to = editor.getCursor("to");
        const start = from.line + 1;
        // A selection ending at column zero excludes that final line.
        const end = to.line > from.line && to.ch === 0 ? to.line : to.line + 1;
        const reference = `@${view.file.path}:L${start}${end > start ? `-L${end}` : ""}`;
        try {
          await navigator.clipboard.writeText(reference);
          new Notice(`Copied: ${reference}`, 2000);
        } catch (error) {
          console.error("Could not copy context link", error);
          new Notice("Could not copy context link to the clipboard.");
        }
      },
    });

    this.addCommand({
      id: "toggle-comments-sidebar",
      name: "Toggle comments sidebar",
      callback: () => {
        const workspace = this.app.workspace;
        const leaves = workspace.getLeavesOfType("document-comments-sidebar");
        const visible = leaves.filter((leaf) => {
          const root = leaf.getRoot();
          if ((root === workspace.leftSplit || root === workspace.rightSplit) && root.collapsed) return false;
          return leaf.view.containerEl.offsetParent !== null;
        });
        if (visible.length) {
          // Close only comment views; leave other sidebar tabs and panels intact.
          visible.forEach((leaf) => leaf.detach());
        } else {
          this.app.commands.executeCommandById("document-comments:open-comments-sidebar");
        }
      },
    });

    const documents = new WeakSet();
    const bind = (doc) => {
      if (!doc || documents.has(doc)) return;
      documents.add(doc);
      this.registerDomEvent(doc, "keydown", (event) => {
        if (event.isComposing || !event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
        const key = event.key.toLowerCase();
        if (key !== "j" && key !== "k") return;

        const target = event.target;
        if (!target || typeof target.dispatchEvent !== "function") return;
        event.preventDefault();
        event.stopImmediatePropagation();

        // Reuse each view's own arrow-key behavior instead of overriding selection logic.
        const down = key === "j";
        const arrow = down ? "ArrowDown" : "ArrowUp";
        const forwarded = new doc.defaultView.KeyboardEvent("keydown", {
          key: arrow,
          code: arrow,
          keyCode: down ? 40 : 38,
          which: down ? 40 : 38,
          bubbles: true,
          cancelable: true,
          composed: true,
          repeat: event.repeat,
        });
        target.dispatchEvent(forwarded);

        // Synthetic events have no native caret movement in plain text inputs.
        // Suggestions that consume the arrow event take priority over this fallback.
        if (!forwarded.defaultPrevented &&
            (target.tagName === "INPUT" || target.tagName === "TEXTAREA") &&
            typeof target.selectionStart === "number") {
          const value = target.value;
          const position = target.selectionStart;
          const lineStart = value.lastIndexOf("\n", position - 1) + 1;
          const column = position - lineStart;
          let next;
          if (down) {
            const end = value.indexOf("\n", position);
            if (end === -1) next = value.length;
            else {
              const nextEnd = value.indexOf("\n", end + 1);
              next = Math.min(end + 1 + column, nextEnd === -1 ? value.length : nextEnd);
            }
          } else if (lineStart === 0) next = 0;
          else {
            const previousStart = value.lastIndexOf("\n", lineStart - 2) + 1;
            next = Math.min(previousStart + column, lineStart - 1);
          }
          target.setSelectionRange(next, next);
        }
      }, true);
    };

    bind(document);
    this.app.workspace.iterateAllLeaves((leaf) => bind(leaf.view.containerEl.ownerDocument));
    this.registerEvent(this.app.workspace.on("window-open", (workspaceWindow) => bind(workspaceWindow.doc)));
  }
};
