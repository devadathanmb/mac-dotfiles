# Execution Rules

- In shell commands, prefer `fd` over `find` and `rg` over `grep`.
- Scope tool output with appropriate flags, limits, and filters. If its shape is unknown (for example, container logs), read a short tail first, then query the relevant range or pattern.
- Chain predictable dependent shell commands with `&&` instead of making repeated partial lookups. Run independent tool calls in parallel when useful.
- Read only relevant files and appropriate ranges in large files; re-read when needed, especially after changes.
- Check local code and documentation before searching the web.
- Use `agent-python` (uv-managed Python for agents), rather than `python` or `python3`, for one-off data processing, HTTP requests, or multi-step parsing and conditional logic—not for work handled by a single tool call or simple shell command. Prefer its installed libraries where applicable: `pandas`, `numpy`, `ruamel.yaml` (not `yaml`), `httpx2` (not `httpx`), `beautifulsoup4`, `plotly`, `pymupdf`, `Pillow`.
- Ask questions only when ambiguity would materially change the result; resolve routine implementation choices yourself and finish the task.
