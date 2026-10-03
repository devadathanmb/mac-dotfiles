---
name: gh-cli-agent
description: >
  Investigate GitHub PR feedback and CI: review comments (human, bot, Copilot), unresolved review threads, failing checks, and failing GitHub Actions logs. Use when the user asks what reviewers said, what feedback remains, or why a PR's CI failed. Do not use for creating/editing/viewing/listing PRs; use `gh` directly for those.
---

# gh-cli-agent

`~/.agents/skills/gh-cli-agent/scripts/gh-pr-context <cmd> [PR]` (written `gh-pr-context` below). `PR` is a number, PR URL, or `OWNER/REPO#N`; omit it for the current branch's PR. Needs `gh` authenticated. Data is fetched fresh on every call.

| Question | Command |
|---|---|
| What did reviewers / Copilot / a bot say? | `gh-pr-context comments [--user L]... [--copilot \| --bots \| --human]` |
| What feedback is still unresolved? | `gh-pr-context threads` (`--all` includes resolved) |
| Which checks failed? | `gh-pr-context checks --failed` |
| Why did CI fail? | `gh-pr-context logs` |

- `comments` merges general comments, inline review comments, and review summaries (`gh pr view --comments` misses inline feedback). Comment state is not resolution state; use `threads` for what remains open.
- `threads` shows thread ids and `[outdated]` (the code changed since the comment) so you can tell what still applies.
- `logs` finds failing Actions runs from the checks, then prints, per failing step, the 25 lines leading up to each `##[error]` (`--tail N` to change). Start from that; open the full cleaned log only if the cause isn't visible. External CI (non-Actions) is listed with its link only.

## Output

Small results print inline. Large ones end with `[preview N/M chars | full output, L lines: <path> | ...]`; the preview is usually enough, otherwise `rg -n` or Read with offset/limit on `<path>`. Individual comments are cut at 1500 chars (`--max-body N`, 0 = all). Quote only the relevant lines in your answer; don't paste logs.

Errors print `error: ... | hint: ...` and exit 1. If `gh` is unauthenticated, ask the user to run `gh auth login`.
