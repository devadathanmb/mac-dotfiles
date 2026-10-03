#!/usr/bin/env bash
# Scaffold a Vite + React + Tailwind v4 + shadcn/ui project that builds to one self-contained HTML file.
# Usage: init-react.sh <project-name> [parent-dir]
set -euo pipefail

name="${1:?usage: init-react.sh <project-name> [parent-dir]}"
parent="${2:-.}"
log="$(mktemp "${TMPDIR:-/tmp}/init-react.XXXXXX")"

cd "$parent"
if [ -e "$name" ]; then
  echo "error: $parent/$name already exists" >&2
  exit 1
fi

echo "Scaffolding $name (log: $log)"
npx -y shadcn@latest init -t vite -n "$name" -b radix -p nova --no-monorepo --no-rtl -y </dev/null >"$log" 2>&1 \
  || { echo "error: shadcn init failed; see $log" >&2; exit 1; }

cd "$name"
npm install -D vite-plugin-singlefile >>"$log" 2>&1 \
  || { echo "error: installing vite-plugin-singlefile failed; see $log" >&2; exit 1; }

python3 - <<'PY'
import re
p = "vite.config.ts"
t = open(p).read()
t = t.replace('import { defineConfig } from "vite"\n',
              'import { defineConfig } from "vite"\nimport { viteSingleFile } from "vite-plugin-singlefile"\n', 1)
t = re.sub(r"plugins: \[(.*?)\]", lambda m: f"plugins: [{m.group(1)}, viteSingleFile()]", t, count=1)
assert "viteSingleFile()" in t, "could not patch vite.config.ts"
open(p, "w").write(t)

p = "index.html"
t = open(p).read()
t = re.sub(r'\s*<link rel="icon"[^>]*>', "", t)
open(p, "w").write(t)
PY
rm -f public/vite.svg

echo "Ready: $(pwd)"
echo "Add components with: npx shadcn@latest add <component...>"
echo "Build with: npm run build  ->  dist/index.html"
