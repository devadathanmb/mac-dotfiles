# Obsidian

Reusable configuration for the vault at `~/repos/notes`, linked by
`install.conf.yaml`. Vault contents, attachments, `workspace.json`, and Obsidian's
global application state are intentionally not managed here.

## Contents

- Editor, appearance, core-plugin, community-plugin, and hotkey settings.
- `vimrc`: linked as the vault's `.obsidian.vimrc`.
- `Keybindings.md`: linked as `Settings/Keybindings.md`; editable from Obsidian
  with `Space u k`.
- `snippets/vscode-style.css`: Maple Mono / GitHub Dark-style customization.
- `plugins/`: plugin settings, plus the local Global Vim
  Navigation plugin implementing app-wide Ctrl+J/K as Down/Up, comments-sidebar
  toggling, `Space y` context references for selected/current lines,
  Ctrl+H/L focus movement between splits and the file explorer, and VS Code-style
  file explorer keys (`a` new file, `f`/`A` new folder, `r` rename, `d` delete, `x`/`p` cut/paste,
  `y`/`Y` copy relative/full path, `o` toggle folder, `Ctrl+D`/`Ctrl+U` page).

## Third-party plugins

`plugins.json` pins each plugin's GitHub repository, release tag, and SHA-256
checksums. Dotbot runs `install-plugins.py` after linking settings to download
release assets directly into the vault. Downloaded code is not stored in this
repository. Only each third-party plugin's `data.json` is symlinked here.

The installer needs network access on the first install or when changing pins.
If all installed assets match their checksums, it makes no changes and no network
requests. It verifies every asset and release manifest before replacing a
plugin's code, and leaves settings and unrelated plugin files untouched.

| Plugin | Version | Source |
| --- | --- | --- |
| Spacekeys | 0.5.0 | https://github.com/jlumpe/obsidian-spacekeys |
| Vimrc Support | 0.10.2 | https://github.com/esm7/obsidian-vimrc-support |
| Sidebar Keyboard Navigation | 1.1.2 | https://github.com/denvolok/obsidian-sidebar-keyboard-navigation |
| Document Comments | 0.1.15 | https://github.com/kylemcd/obsidian-document-comments |

Document Comments stores review threads in the Markdown files themselves as
HTML comments, readable by coding agents. Select a line with `V`, then use
`Space c c` to add feedback. `Space c o` toggles the comments sidebar.

## Restore and maintain

1. Install Obsidian and Maple Mono using the machine's normal provisioning.
2. Apply the Dotbot links through the repository's normal dotfiles workflow.
   The links create the vault's configuration directories if necessary; the
   installer downloads the pinned third-party plugins automatically.
3. Open `~/repos/notes` as a vault in Obsidian and enable community plugins if
   prompted.

To install/restore only third-party plugin code without applying other dotfiles:

```sh
python configs/obsidian/install-plugins.py
```

These are individual settings-file links plus one directory link for our custom
plugin, not a link of the entire `.obsidian` directory. Workspace layout and
unrelated plugins remain local. Additional plugins installed in Obsidian are not
automatically included here.

Settings changes can modify this repository immediately. Review the diff before
committing, especially plugin `data.json` files: never publish credentials or
private application state. Author-color indexing in Document Comments remains
disabled to avoid copying collaborator names into these settings.

To update a third-party plugin, update its release tag and checksums in
`plugins.json`, update this table, and run the installer. Obsidian's own updater
can change vault-local code, but provisioning will restore the pinned versions.

The local navigation plugin is source code, not a downloaded dependency; edit
`plugins/global-vim-navigation/main.js` and reload Obsidian to apply changes.
