## Efficient Execution

- Scope each tool call's output: use flags (`--stat`, `--name-only`, `-n`, `rg -l`, `-A/-B`), limits, and filters. If the output's shape is unknown (e.g., container logs), read a short tail first, then query the relevant range or pattern.
- Chain predictable follow-ups with `&&` (`git status --short && git diff --stat`) instead of repeated partial lookups.
- Read only relevant files and ranges; re-read a file only if it changed.
- Check local code and docs before searching the web.
- Widen verification only after a specific failure, diagnosing from the exact error.
- Use `python` directly (no `mise exec`) for one-off data processing, HTTP requests, or multi-step parsing and conditional logic—not for tasks handled by a single tool call or simple shell command. Prefer installed libraries where applicable: `pandas`, `numpy`, `ruamel.yaml`, `httpx`, `beautifulsoup4`, `duckdb`, `pymupdf`.
