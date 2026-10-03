## Efficient Execution

- Keep tool output small: use flags (`--stat`, `--name-only`, `-n`, `rg -l`, `-A/-B`), Read offset/limit, and filters. If output shape is unknown (e.g., container logs), read a short tail first, then query the relevant range or pattern.
- Chain predictable shell follow-ups into one command (`git status --short && git diff --stat`).
- Check local code and docs before searching the web.
- Run one verification proportional to the change; widen it only after a specific failure, diagnosing from the exact error.
- For one-off data inspection/transforms or HTTP checks that don't need the app runtime, run `python` directly (already mise-managed on PATH; don't wrap in `mise exec`) (stdlib `csv`/`json`; `pandas`, `numpy`, `ruamel.yaml`, `httpx`, `beautifulsoup4`, `duckdb`, `pymupdf` installed) instead of Docker. Use project tooling for app-specific behavior.
- Use background only when expected runtime exceeds ~30s, not based on timeout limits; otherwise use foreground. Wait for background completion notifications; never sleep or poll.
- Close stdin (`< /dev/null`) when scripts launch non-interactive CLIs.
