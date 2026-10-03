## Efficient Execution

- Keep tool output small: use flags (`--stat`, `--name-only`, `-n`, `rg -l`, `-A/-B`), Read offset/limit, and filters. If output shape is unknown (e.g., container logs), read a short tail first, then query the relevant range or pattern.
- Chain predictable shell follow-ups into one command (`git status --short && git diff --stat`).
- Check local code and docs before searching the web.
- Run one verification proportional to the change; widen it only after a specific failure, diagnosing from the exact error.
- For one-off data inspection/transforms or HTTP checks that don't need the app runtime, run `python` directly (already mise-managed on PATH; don't wrap in `mise exec`) (stdlib `csv`/`json`; `pandas`, `numpy`, `ruamel.yaml`, `httpx`, `beautifulsoup4`, `duckdb`, `pymupdf` installed) instead of Docker. Use project tooling for app-specific behavior.
- Run anything that may take over ~30s (eval batches, builds, full test suites, slow network jobs) as a background task using the harness's background option, and let its completion notification wake you; never foreground it with `sleep`/poll loops or hand-guessed timeouts. Launch non-interactive CLIs from scripts with stdin closed (`< /dev/null`) so they cannot block waiting for input.
