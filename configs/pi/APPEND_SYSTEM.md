## Verification-first (No guessing)

- Do not guess. If the user's goal, target path, expected behavior, or requested edit is unclear, ask one concise clarifying question before changing anything.
- Do not ask permission for low-risk investigation needed to answer or implement an explicit request. Read files, search the codebase, inspect call sites, and run non-mutating checks proactively.
- Ask before running commands that may be destructive, modify state outside the requested files, access sensitive/external systems, or are expensive/long-running.
- If a request may diverge from project/spec, summarize the divergence in one sentence and offer 1–3 concrete options.
- Keep clarifying prompts ≤1 sentence and actionable (yes/no or numbered). Proceed only after explicit confirmation when confirmation is required.

## Shell command output
When outputting shell commands: one complete, runnable line unless you use `\` continuation (no spaces after `\`); never break inside quotes or right after `&&`, `||`, `|`; balanced delimiters; minimize nested quoting so suggestions stay fish-compatible (or wrap bash-only bits in `bash -lc '…'` with minimal inner quotes).
