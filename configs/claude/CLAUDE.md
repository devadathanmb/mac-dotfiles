## Efficient Execution

- Keep tool output small: use flags (`--stat`, `--name-only`, `-n`, `rg -l`, `-A/-B`), Read offset/limit, and filters. If output shape is unknown (e.g., container logs), read a short tail first, then query the relevant range or pattern.
- Chain predictable shell follow-ups into one command (`git status --short && git diff --stat`).
- Check local code and docs before searching the web.
- Run one verification proportional to the change; widen it only after a specific failure, diagnosing from the exact error.
- Use `python` directly (no `mise exec`) for one-off data processing, HTTP requests, or multi-step parsing and conditional logic—not for tasks handled by a single tool call or simple shell command. Prefer installed libraries where applicable: `pandas`, `numpy`, `ruamel.yaml`, `httpx`, `beautifulsoup4`, `duckdb`, `pymupdf`.
- Use background only when expected runtime exceeds ~30s, not based on timeout limits; otherwise use foreground. Wait for background completion notifications; never sleep or poll.
- Redirect stdin (`< /dev/null`) only for commands that may prompt.
