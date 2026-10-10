#!/usr/bin/env python3
"""Link the shared Obsidian configuration into one or more vaults.

Usage: link-vault.py [--all] [--exclude PATH ...] [VAULT ...]

With --all (or no arguments) every vault registered in Obsidian's global
obsidian.json is used. Existing files that would be replaced are moved to
~/.local/state/obsidian-link-backups/. Safe to re-run.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OBSIDIAN_JSON = Path.home() / "Library/Application Support/obsidian/obsidian.json"
BACKUP_ROOT = Path.home() / ".local/state/obsidian-link-backups"

# vault-relative target -> source relative to this directory
LINKS = {
    ".obsidian/app.json": "app.json",
    ".obsidian/appearance.json": "appearance.json",
    ".obsidian/community-plugins.json": "community-plugins.json",
    ".obsidian/core-plugins.json": "core-plugins.json",
    ".obsidian/hotkeys.json": "hotkeys.json",
    ".obsidian.vimrc": "vimrc",
    "Settings/Keybindings.md": "Keybindings.md",
    ".obsidian/snippets/vscode-style.css": "snippets/vscode-style.css",
    ".obsidian/plugins/spacekeys/data.json": "plugins/spacekeys/data.json",
    ".obsidian/plugins/obsidian-vimrc-support/data.json": "plugins/obsidian-vimrc-support/data.json",
    ".obsidian/plugins/sidebar-keyboard-navigation/data.json": "plugins/sidebar-keyboard-navigation/data.json",
    ".obsidian/plugins/global-vim-navigation": "plugins/global-vim-navigation",
    ".obsidian/plugins/document-comments/data.json": "plugins/document-comments/data.json",
}


def registered_vaults():
    if not OBSIDIAN_JSON.exists():
        return []
    data = json.loads(OBSIDIAN_JSON.read_text())
    return [Path(v["path"]) for v in data.get("vaults", {}).values()]


def link_vault(vault, stamp):
    for rel, src in LINKS.items():
        target, source = vault / rel, HERE / src
        if target.is_symlink() and target.resolve() == source.resolve():
            continue
        if target.exists() or target.is_symlink():
            backup = BACKUP_ROOT / stamp / vault.name / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            target.rename(backup)
            print(f"  backed up {rel} -> {backup}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(source)
        print(f"  linked {rel}")
    subprocess.run(
        [sys.executable, str(HERE / "install-plugins.py"), "--vault", str(vault)],
        check=True,
        stdin=subprocess.DEVNULL,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("vaults", nargs="*", type=Path)
    parser.add_argument("--all", action="store_true", help="include every vault Obsidian knows about")
    parser.add_argument("--exclude", action="append", default=[], type=Path)
    args = parser.parse_args()

    vaults = [v.expanduser() for v in args.vaults]
    if args.all or not vaults:
        vaults += registered_vaults()
    excluded = {p.expanduser().resolve() for p in args.exclude}
    stamp = time.strftime("%Y%m%d-%H%M%S")

    seen = set()
    for vault in vaults:
        vault = vault.resolve()
        if vault in seen or vault in excluded:
            continue
        seen.add(vault)
        if not vault.is_dir():
            print(f"skipping missing vault {vault}")
            continue
        print(f"{vault}")
        link_vault(vault, stamp)


if __name__ == "__main__":
    main()
