# Execution Rules

- In shell commands, prefer `fd` over `find` and `rg` over `grep`
- Keep tool output small: use flags (`--stat`, `--name-only`, `-n`, `rg -l`, `-A/-B`), filters, and `Read` offset/limit for large files. If the output's shape is unknown (e.g., container logs), read a short tail first, then query the relevant range or pattern
- Chain predictable shell follow-ups into one command (`git status --short && git diff --stat`)
- Check local code and docs before searching the web
- Use `agent-python` (uv-managed Python for agents, not `python`/`python3`) for one-off data processing, HTTP requests, or multi-step parsing and conditional logic—not for tasks handled by a single tool call or simple shell command. Prefer its installed libraries where applicable: `pandas`, `numpy`, `ruamel.yaml` (not `yaml`), `httpx2`, `beautifulsoup4`, `matplotlib`, `pymupdf`, `Pillow`
- Use `run_in_background` only when expected runtime exceeds ~30s, not based on timeout limits; otherwise run in foreground
