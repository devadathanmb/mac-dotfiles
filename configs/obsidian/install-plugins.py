#!/usr/bin/env python3

import argparse
import hashlib
import json
import re
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "mac-dots-obsidian"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(16 * 1024 * 1024 + 1)
    if len(data) > 16 * 1024 * 1024:
        raise ValueError(f"Release asset exceeds 16 MiB: {url}")
    return data


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_plugins(manifest):
    plugins = json.loads(manifest.read_text())["plugins"]
    seen = set()
    for plugin in plugins:
        pid = plugin["id"]
        if not re.fullmatch(r"[a-z0-9-]+", pid) or pid in seen:
            raise ValueError(f"Invalid or duplicate plugin ID: {pid}")
        seen.add(pid)
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", plugin["repo"]):
            raise ValueError(f"Invalid GitHub repository: {plugin['repo']}")
        if not re.fullmatch(r"[\w.-]+", plugin["version"]):
            raise ValueError(f"Invalid release tag: {plugin['version']}")
        files = plugin["files"]
        if not {"main.js", "manifest.json"}.issubset(files):
            raise ValueError(f"Missing required assets for {pid}")
        for name, digest in files.items():
            if name not in {"main.js", "manifest.json", "styles.css"}:
                raise ValueError(f"Unexpected asset: {name}")
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError(f"Invalid SHA-256 for {pid}/{name}")
    return plugins


def install_plugins(manifest, vault):
    plugins = read_plugins(manifest)
    root = vault / ".obsidian" / "plugins"
    changed = 0
    for plugin in plugins:
        pid = plugin["id"]
        destination = root / pid
        if destination.is_symlink():
            raise ValueError(f"Refusing to write release assets into a symlink: {destination}")
        files = plugin["files"]
        if any((destination / name).is_symlink() for name in files):
            raise ValueError(f"Refusing to replace symlinked assets in {destination}")
        if all(
            (destination / name).is_file()
            and sha256((destination / name).read_bytes()) == digest
            for name, digest in files.items()
        ):
            print(f"Unchanged: {pid} {plugin['version']}")
            continue
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f".{pid}-", dir=root) as temporary:
            staging = Path(temporary)
            for name, digest in files.items():
                tag = urllib.parse.quote(plugin["version"], safe="")
                url = f"https://github.com/{plugin['repo']}/releases/download/{tag}/{name}"
                data = download(url)
                if sha256(data) != digest:
                    raise ValueError(f"SHA-256 mismatch for {pid}/{name}; installation aborted")
                (staging / name).write_bytes(data)
            metadata = json.loads((staging / "manifest.json").read_text())
            if metadata.get("id") != pid or metadata.get("version") != plugin["version"]:
                raise ValueError(f"Release manifest does not match pinned {pid} {plugin['version']}")
            destination.mkdir(parents=True, exist_ok=True)
            for name in files:
                (staging / name).replace(destination / name)
        changed += 1
        print(f"Installed: {pid} {plugin['version']}")
    return changed


def main():
    parser = argparse.ArgumentParser(description="Install checksum-pinned Obsidian plugins.")
    parser.add_argument("--vault", type=Path, default=Path.home() / "repos" / "notes")
    args = parser.parse_args()
    manifest = Path(__file__).resolve().with_name("plugins.json")
    try:
        install_plugins(manifest, args.vault.expanduser())
    except (OSError, ValueError, KeyError) as error:
        print(f"Obsidian plugin installation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
