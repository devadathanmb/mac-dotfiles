# Execution Rules

- Prefer `fd` over `find` and `rg` over `grep`
- Scope each command's output: use flags (`--stat`, `--name-only`, `-n`, `rg -l`, `-A/-B`), limits, and filters. If the output's shape is unknown (e.g., container logs), read a short tail first, then query the relevant range or pattern
- Chain predictable follow-ups with `&&` (`git status --short && git diff --stat`) instead of repeated partial lookups
- Read only relevant files (and specific line ranges in large files); re-read a file only if it changed
- Check local code and docs before searching the web
- Use `agent-python` (uv-managed Python for agents, not `python`/`python3`) for one-off data processing, HTTP requests, or multi-step parsing and conditional logic—not for tasks handled by a single tool call or simple shell command. Prefer its installed libraries where applicable: `pandas`, `numpy`, `ruamel.yaml` (not `yaml`), `httpx2`, `beautifulsoup4`, `matplotlib`, `plotly`, `pymupdf`, `Pillow`
- Ask only when ambiguity would materially change the result; otherwise proceed and finish the task
- Run commands in the foreground with a sufficient `yield_time_ms` rather than backgrounding with `&`; use background processes only for long-running servers or daemons
