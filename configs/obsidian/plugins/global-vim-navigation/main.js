const { Plugin, Notice, View } = require("obsidian");

module.exports = class GlobalVimNavigation extends Plugin {
  // Ctrl+H/L move to the neighbouring split, entering or leaving the left sidebar at the edges.
  // Returns false when there is nothing to move to so the keypress is left alone.
  moveBetweenSidebarAndEditor(toLeft) {
    const workspace = this.app.workspace;
    const active = workspace.getActiveViewOfType(View)?.leaf;
    if (!active) return false;
    const inSidebar = active.getRoot() === workspace.leftSplit;
    const focus = (leaf) => {
      // Focus left in the editor would otherwise make its leaf active again.
      document.activeElement?.blur?.();
      workspace.setActiveLeaf(leaf, { focus: true });
    };

    if (inSidebar) {
      if (toLeft) return false;
      const editor = workspace.getMostRecentLeaf(workspace.rootSplit);
      if (!editor) return false;
      focus(editor);
      return true;
    }

    const adjacent = workspace.getAdjacentLeafInDirection(active, toLeft ? "left" : "right");
    if (adjacent && adjacent.getRoot() !== workspace.leftSplit) {
      focus(adjacent);
      return true;
    }
    if (!toLeft || workspace.leftSplit.collapsed) return false;
    const explorer = workspace.getLeavesOfType("file-explorer")[0];
    if (!explorer) return false;
    focus(explorer);
    // Activating the leaf alone leaves no focused row, so arrow keys do nothing.
    const { tree, fileItems } = explorer.view;
    const current = workspace.getActiveFile();
    const item = tree.focusedItem ?? (current && fileItems[current.path]) ?? Object.values(fileItems)[0];
    if (item) tree.setFocusedItem(item);
    return true;
  }

  // VS Code-style single-key file explorer actions; true when the key was handled.
  explorerKey(event) {
    const workspace = this.app.workspace;
    const view = workspace.getActiveViewOfType(View);
    if (view?.getViewType() !== "file-explorer" || document.querySelector(".modal")) return false;
    const field = document.activeElement;
    if (field && (field.tagName === "INPUT" || field.tagName === "TEXTAREA" || field.isContentEditable)) return false;
    if (event.metaKey || event.altKey) return false;

    const { tree } = view;
    const item = tree.focusedItem;
    if (!item) return false;
    const file = item.file;
    const folder = file.children ? file : file.parent;
    const vault = this.app.vault;
    const copy = (text) => navigator.clipboard.writeText(text).then(() => new Notice(`Copied: ${text}`, 2000));

    if (event.ctrlKey) {
      if (event.shiftKey || (event.key !== "d" && event.key !== "u")) return false;
      const arrow = event.key === "d" ? "ArrowDown" : "ArrowUp";
      for (let i = 0; i < 10; i++) {
        document.dispatchEvent(new KeyboardEvent("keydown", { key: arrow, bubbles: true, cancelable: true }));
      }
      return true;
    }

    switch (event.key) {
      case "a":
        view.createAbstractFile("file", folder, false);
        return true;
      case "A":
      case "f":
        view.createAbstractFile("folder", folder, false);
        return true;
      case "r":
        view.startRenameFile(file);
        return true;
      case "d": {
        const siblings = (item.parent ?? tree.root).vChildren.children;
        const index = siblings.indexOf(item);
        const nextPath = (siblings[index + 1] ?? siblings[index - 1] ?? item.parent)?.file?.path;
        // The prompt resolves before the file is removed, so wait for the delete event.
        const ref = vault.on("delete", (deleted) => {
          if (deleted !== file) return;
          vault.offref(ref);
          setTimeout(() => {
            const nextItem = view.fileItems[nextPath];
            if (nextItem) tree.setFocusedItem(nextItem);
          }, 200);
        });
        this.app.fileManager.promptForDeletion(file);
        // Stop listening if the prompt is declined.
        setTimeout(() => vault.offref(ref), 60000);
        return true;
      }
      case "x":
        this.cutFile = file;
        new Notice(`Cut: ${file.path}`, 2000);
        return true;
      case "p": {
        const source = this.cutFile;
        if (!source) return true;
        this.cutFile = null;
        const prefix = folder.path === "/" ? "" : `${folder.path}/`;
        this.app.fileManager.renameFile(source, `${prefix}${source.name}`);
        return true;
      }
      case "y":
        copy(file.path);
        return true;
      case "Y":
        copy(vault.adapter.getFullPath(file.path));
        return true;
      case "o":
        item.setCollapsed?.(!item.collapsed);
        return true;
      // Obsidian's native Enter renames the row, and the sidebar plugin's `l` forwards Enter.
      case "Enter":
      case "l": {
        if (event.key === "l" && event.shiftKey) return false;
        if (file.children) {
          if (event.key === "Enter") item.setCollapsed?.(!item.collapsed);
          else item.setCollapsed?.(false);
          return true;
        }
        let target = null;
        workspace.iterateAllLeaves((leaf) => {
          if (!target && leaf.view.file === file && leaf.getRoot() !== workspace.leftSplit) target = leaf;
        });
        target ??= workspace.getMostRecentLeaf(workspace.rootSplit) ?? workspace.getLeaf(true);
        const open = target.view.file === file ? Promise.resolve() : target.openFile(file);
        open.then(() => {
          document.activeElement?.blur?.();
          workspace.setActiveLeaf(target, { focus: true });
        });
        return true;
      }
      default:
        return false;
    }
  }

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
        if (event.isComposing) return;
        if (this.explorerKey(event)) {
          event.preventDefault();
          event.stopImmediatePropagation();
          return;
        }
        if (!event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
        const key = event.key.toLowerCase();
        if ((key === "h" || key === "l") && this.moveBetweenSidebarAndEditor(key === "h")) {
          event.preventDefault();
          event.stopImmediatePropagation();
          return;
        }
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
