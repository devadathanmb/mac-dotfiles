# Execution Rules

- In shell commands, prefer `fd` over `find` and `rg` over `grep`.
- Scope each tool call's output: use flags (`--stat`, `--name-only`, `-n`, `rg -l`, `-A/-B`), limits, and filters. If the output's shape is unknown (e.g., container logs), read a short tail first, then query the relevant range or pattern.
- Chain predictable follow-ups with `&&` (`git status --short && git diff --stat`) instead of repeated partial lookups.
- Read only relevant files (and specific ranges in large files); re-read a file only if it changed.
- Use `subagent` (`explore`) only for wide, open-ended searches whose raw output would flood the context; use `glob`, `grep`, and `read` directly for targeted lookups.
- Check local code and docs before searching the web.
- Use `python` directly for one-off data processing, HTTP requests, or multi-step parsing and conditional logic—not for tasks handled by a single tool call or simple shell command. Prefer installed libraries where applicable: `pandas`, `numpy`, `ruamel.yaml` (not `yaml`), `httpx`, `beautifulsoup4`, `duckdb`, `pymupdf`, `Pillow`.
- Ask (or call `question`) only when ambiguity would materially change the result; resolve routine implementation choices yourself and finish the task.
- Use `background: true` only when expected runtime exceeds ~30s, not to bypass timeout limits; otherwise run in the foreground. Wait for completion notifications; never sleep or poll.
