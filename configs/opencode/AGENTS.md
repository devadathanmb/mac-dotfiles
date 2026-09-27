## Efficient Execution

- Scope each tool call's output: use flags (`--stat`, `--name-only`, `-n`, `rg -l`, `-A/-B`), limits, and filters. If the output's shape is unknown (e.g., container logs), read a short tail first, then query the relevant range or pattern.
- Combine predictable follow-ups into one command (`git status --short && git diff --stat`) rather than making repeated partial lookups.
- Inspect only relevant files and ranges; avoid repeated or repository-wide reads. Re-read a file only if it changed.
- Delegate wide, open-ended searches to a subagent so the raw output never enters the main context.
- Use local code and documentation before searching the web.
- Run one verification proportional to the change; expand only after a specific failure.
- Diagnose failures from the exact error instead of retrying broadly.
- For one-off data inspection/transforms or HTTP checks that do not need the app runtime, use globally available mise-managed `python` (stdlib `csv`/`json`; installed `pandas`, `numpy`, `ruamel.yaml`, `httpx`) instead of starting Docker. Use project tooling for app-specific behavior; check installed versions only when compatibility matters.
- Ask only when ambiguity would materially change behavior; otherwise proceed.
