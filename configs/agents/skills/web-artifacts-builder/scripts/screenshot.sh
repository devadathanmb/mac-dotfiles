#!/usr/bin/env bash
# Capture full-page desktop and mobile screenshots of an HTML file or URL with Playwright.
# Usage: screenshot.sh <html-file-or-url> [out-dir]
set -euo pipefail

target="${1:?usage: screenshot.sh <html-file-or-url> [out-dir]}"
out="${2:-$(mktemp -d "${TMPDIR:-/tmp}/artifact-shots.XXXXXX")}"
mkdir -p "$out"

case "$target" in
  http://*|https://*|file://*) url="$target" ;;
  *) url="file://$(cd "$(dirname "$target")" && pwd)/$(basename "$target")" ;;
esac

pw() { npx -y playwright@latest "$@"; }
pw install chromium >/dev/null 2>&1 || { echo "error: installing Playwright Chromium failed" >&2; exit 1; }

pw screenshot --full-page --wait-for-timeout=800 --viewport-size=1440,900 "$url" "$out/desktop.png" >/dev/null
pw screenshot --full-page --wait-for-timeout=800 --viewport-size=390,844 "$url" "$out/mobile.png" >/dev/null

echo "$out/desktop.png"
echo "$out/mobile.png"
