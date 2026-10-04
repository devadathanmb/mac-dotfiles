# Keybindings

Press **Space** in Vim normal mode to open the command menu. Space still types normally in insert mode. **Ctrl+M** opens the same menu elsewhere, including the sidebar. **Cmd+E** toggles the left sidebar directly.

These bindings mirror your VS Code which-key layout wherever Obsidian has an equivalent command. Edit the YAML below; Spacekeys reloads it automatically. Use **Space → ?** to find and copy command IDs.

## Editor and sidebar

- **H/L**: previous/next tab in normal mode.
- **Ctrl+H/L**: focus pane left/right, including navigation out of the sidebar where an adjacent pane exists.
- **Ctrl+J/K**: down/up throughout editors, command palettes, quick switchers, suggestions, and sidebars. A local Global Vim Navigation plugin forwards these keys to each view's arrow-key handler.
- **Ctrl+N**: clear Vim search highlights in normal mode.
- **Ctrl+X**: close tab in normal mode.
- **Ctrl+E**: show/focus explorer.
- **Space y**: copy a context reference for the selected lines, or current line
  when nothing is selected: `@Folder/note.md:L15` or `@Folder/note.md:L15-L20`.
  Paths are relative to this vault, not necessarily your agent's working directory.
- Clipboard yanks use the system clipboard; visual **p** preserves the yank register; **>/<** retain the visual selection.
- Explorer **j/k**, **h/l**, **r**: navigate, collapse/open, rename. **n** creates a note; **f** creates a folder. **g/G** go to first/last entry. **Esc** returns to the editor.
- Search sidebar: **Tab** leaves the search input, then **j/k** navigate results and **l/Enter** open a result.

## Reviewing specifications

Use **V** to select the current line, or **v** plus motions to select a passage,
then **Space c c** to add a Document Comments margin comment. Type your feedback
and press **Enter** to save; **Shift+Enter** inserts a newline.

- **Space c o**: toggle the comments sidebar.
- **Space c t**: show/hide comments.
- **Space c r**: show/hide resolved comments.
- **Space c a**: add a comment to selected text in Reading view.

Comments and their anchors are stored as HTML comments inside the `.md` file.
Give that file to your agent and ask it to address the `<!--co:...-->` threads
while preserving the `<!--c:ID-->` / `<!--/c:ID-->` anchor pairs. Comments only
work on files opened in this vault; files in other repositories must be made
available to the vault or opened in a separately configured vault.

The default author is **me**. Set your preferred author in the plugin settings.
Author colors stay disabled so collaborator names are not indexed into the
public dotfiles configuration. Review comments themselves remain in your notes,
not the dotfiles repo.

## Intentional differences

- Sidebar navigation uses **n**, not VS Code's **a**, for new notes; **g**, not **gg**, jumps to the top. The plugin does not support arbitrary remapping.
- Space may be intercepted by sidebars. Use **Ctrl+M** for the leader menu there.
- Line numbers are absolute, not relative. Sneak, EasyMotion, and VS Code surround behavior are not recreated by this setup.
- Git, LSP, debugger, terminal, Copilot, pane-moving, and unsupported buffer actions are omitted rather than assigned unrelated behavior.
- Obsidian bookmarks refer to notes/headings, not VS Code's arbitrary line marks.
- Vimrc Support is a community plugin with limited maintainer availability; its command bridge is not a formal Obsidian API.

```yaml
items:
  e:
    command: app:toggle-left-sidebar
    description: Toggle explorer sidebar
  ';':
    command: command-palette:open
    description: Command palette
  '?':
    command: spacekeys:find-command
    description: Find command ID
  y:
    command: global-vim-navigation:copy-context-link
    description: Copy context link
  c:
    description: Comments / review
    items:
      c:
        command: document-comments:add-comment
        description: Add comment to selection
      o:
        command: global-vim-navigation:toggle-comments-sidebar
        description: Toggle comments sidebar
      t:
        command: document-comments:toggle-comments
        description: Toggle comments
      r:
        command: document-comments:toggle-resolved
        description: Toggle resolved comments
      a:
        command: document-comments:add-comment-reading
        description: Add comment in Reading view
  f:
    command: switcher:open
    description: Find files
  F:
    description: Files
    items:
      n:
        command: file-explorer:new-file
        description: New note
      f:
        command: file-explorer:new-file
        description: New note
      N:
        command: file-explorer:new-folder
        description: New folder
      F:
        command: file-explorer:new-folder
        description: New folder
      r:
        command: workspace:edit-file-title
        description: Rename current note
      y:
        command: file-explorer:duplicate-file
        description: Duplicate current note
      m:
        command: file-explorer:move-file
        description: Move current note
      d:
        command: app:delete-file
        description: Delete current note
      l:
        command: workspace:copy-path
        description: Copy vault-relative path
      L:
        command: workspace:copy-full-path
        description: Copy absolute path
  B:
    description: Buffers / tabs
    items:
      c:
        command: workspace:close-others
        description: Close other tabs
      b:
        command: app:show-tab-switcher
        description: Show tabs
      d:
        command: workspace:close
        description: Close current tab
      n:
        command: workspace:next-tab
        description: Next tab
      p:
        command: workspace:previous-tab
        description: Previous tab
      N:
        command: workspace:new-tab
        description: New tab
      u:
        command: workspace:undo-close-pane
        description: Reopen closed tab
  b:
    description: Bookmarks
    items:
      t:
        command: bookmarks:bookmark-current-view
        description: Bookmark current note
      m:
        command: bookmarks:bookmark-current-view
        description: Bookmark current note
      u:
        command: bookmarks:open
        description: Show bookmarks
      l:
        command: bookmarks:open
        description: Show bookmarks
  s:
    description: Search
    items:
      b:
        command: app:show-tab-switcher
        description: Search open tabs
      m:
        command: bookmarks:open
        description: Show bookmarks
      s:
        command: outline:open
        description: Show note headings
      z:
        command: global-search:open
        description: Search note text
      f:
        command: switcher:open
        description: Find files
      l:
        command: global-search:open
        description: Live grep
  r:
    description: Find and replace
    items:
      f:
        command: editor:open-search-replace
        description: Find and replace in note
  h:
    command: workspace:split-horizontal
    description: Split horizontal
  v:
    command: workspace:split-vertical
    description: Split vertical
  S:
    description: Show
    items:
      e:
        command: file-explorer:open
        description: Show explorer
      s:
        command: outline:open
        description: Show headings
  u:
    description: UI toggles
    items:
      b:
        command: app:toggle-left-sidebar
        description: Toggle left sidebar
      j:
        command: app:toggle-right-sidebar
        description: Toggle right sidebar
      t:
        command: app:toggle-ribbon
        description: Toggle ribbon
      r:
        command: markdown:toggle-preview
        description: Toggle reading view (Obsidian addition)
      s:
        command: app:open-settings
        description: Open settings (Obsidian addition)
      k:
        file: Settings/Keybindings
        description: Edit keybindings (Obsidian addition)
      R:
        command: spacekeys:load-keymap
        description: Reload keybindings (Obsidian addition)
```
