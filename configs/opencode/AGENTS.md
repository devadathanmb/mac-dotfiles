## Efficient Execution

- Scope each tool call's output: use flags (`--stat`, `--name-only`, `-n`, `rg -l`, `-A/-B`), limits, and filters. If the output's shape is unknown (e.g., container logs), read a short tail first, then query the relevant range or pattern.
- Chain predictable follow-ups with `&&` (`git status --short && git diff --stat`) instead of repeated partial lookups.
- Read only relevant files and ranges; re-read a file only if it changed.
- Use a subagent only for wide, open-ended searches whose raw output would flood the context; do small lookups directly.
- Check local code and docs before searching the web.
- Run one verification proportional to the change; widen it only after a specific failure, diagnosing from the exact error.
- For one-off data inspection/transforms or HTTP checks that don't need the app runtime, run `python` directly (already mise-managed on PATH; don't wrap in `mise exec`) (stdlib `csv`/`json`; `pandas`, `numpy`, `ruamel.yaml`, `httpx`, `beautifulsoup4`, `duckdb`, `pymupdf` installed) instead of Docker. Use project tooling for app-specific behavior.
- Ask only when ambiguity would materially change the result; otherwise proceed and finish the task.
- Use background only when expected runtime exceeds ~30s, not based on timeout limits; otherwise use foreground. Wait for background completion notifications; never sleep or poll.
- Close stdin (`< /dev/null`) when scripts launch non-interactive CLIs.
