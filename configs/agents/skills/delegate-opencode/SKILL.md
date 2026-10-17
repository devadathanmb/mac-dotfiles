---
name: delegate-opencode
description:
  Delegate a task, code review, or second opinion to an OpenCode agent through its background
  service API, watch it, and retrieve or continue the result. Use when explicitly invoked to hand
  work to OpenCode from Claude Code or another harness, including orchestrating several OpenCode
  agents in parallel.
disable-model-invocation: true
compatibility:
  Requires OpenCode V2 with its background service running (`opencode service status`), python3, and
  an authenticated model provider.
---

# Delegate to OpenCode

Drive every session through `scripts/delegate.py` (relative to this skill's directory). Do not use
`opencode run`: it hangs when stdin is an open pipe, which is what background tasks provide.

## Choose the model

Default to OpenCode's configured model and agent. Add `--model`/`--agent` only when the user names a
model or lets you pick among models they listed. When prompting a model listed below, read its guide
first.

| Model                 | Guide                                                          |
| --------------------- | -------------------------------------------------------------- |
| `muse-spark`          | [references/models/muse.md](references/models/muse.md)         |
| `deepseek-v4.1-flash` | [references/models/deepseek.md](references/models/deepseek.md) |
| `gpt-6.1-sol`         | [references/models/gpt-sol.md](references/models/gpt-sol.md)   |

Resolve a model's full ID (provider/model) with `opencode models | rg <name>`. Switch a running task
to another model only when the user allows it.

Running several agents at once (worktrees, merging their branches): read
[references/parallel.md](references/parallel.md) first.

## Write the brief

OpenCode does not inherit this conversation. Write a self-contained prompt to a file outside the
repository with the objective, working directory, exact scope (for reviews: uncommitted, staged, a
commit, or a branch comparison with an explicit base; never assume `main`), owned files, decisions
that must not change, verification commands, and the expected report. Include only task-relevant
context and no secrets.

- Reviews and second opinions are non-mutating: say not to edit files or run mutating commands, and
  add `--rule edit=deny`. Ask for findings with severity, `path:line`, evidence, and a fix; "no
  findings" stated explicitly; anything not checked disclosed. The prompt and rule are not a
  sandbox.
- Allow implementation only when the user requested it. Define permitted paths, expected changes,
  and verification; forbid commits, pushes, and destructive operations unless separately authorized.
  When commits are authorized, say they are pre-authorized and need no confirmation; otherwise some
  models stop with a blocking question before the first commit.
- Agents cannot run `rm`, or write outside their working directory, without an approval that blocks
  them. Tell them: never run `rm` (use `git rm` for tracked files; list untracked files to delete in
  the report); never create scratch or log files (read output trimmed with `| tail`/`| rg`);
  anything needed outside the working directory is prepared by you beforehand. Spell out the
  common violations: no `> /tmp/x.log` redirects (read exit codes with `; echo EXIT:$?`), and no
  ad-hoc scripts that create temp dirs or repos to probe behavior (write a test with the project's
  fixtures instead). A general "no scratch files" rule doesn't stop either.
- When the goal is a metric (complexity, coverage, lint counts), agents lower the number rather than
  fix the cause: one-line wrappers, boolean-returning dispatch chains, tests that only import or render
  to satisfy a static coverage estimate. Say readability beats the score, name an acceptable residual
  (e.g. "moderate is fine"), and explain how the metric is computed so the fix targets the cause.
- Examples in the brief get implemented literally, even when trivial. Write suggested extractions as
  "only if it names a real rule", or leave them out.
- Require verification to finish before the final report, and a report with: changes per file group,
  deviations and why, commands run with pass/fail lines, and anything unsure or undone.
- Name invariants the change must keep and checks that guard them; agents satisfy a stated
  acceptance command, so make it exact (e.g. word-bounded `rg` patterns).

## Run and watch

Run every `run`/`watch`/`reject` with the harness's background-task feature and wait for its
completion notification; do not poll or add shell background jobs. Use a unique `--out` per task,
preferably in the harness's approved temp directory (re-watching the same task reuses it). Tell the
user the `progress.log` path right after starting; they can also open the session in the OpenCode
TUI or web UI.

```sh
D=/abs/path/to/skill/scripts/delegate.py
python3 $D run --prompt-file /abs/task.md --out /abs/out --dir /abs/workdir \
  [--model 'provider/model#variant'] [--agent NAME] [--title T] [--rule edit=deny]
python3 $D run --session ses_... --prompt-file /abs/followup.md --out /abs/out2  # follow-up turn
python3 $D watch --session ses_... --out /abs/out           # re-attach, no prompt
python3 $D reject --session ses_... --out /abs/out --message '...'  # refuse pending requests, keep going
python3 $D status --session ses_... [--out /abs/out]        # running?, pending, last progress
python3 $D interrupt --session ses_...
```

- Follow up only with the session ID the script printed for this task; never continue the "last"
  session. `--rule` applies only to new sessions and accepts `deny` or `ask`; never grant `allow`.
- Watching exits as soon as the session needs attention. Unless the status says it was interrupted,
  the session is still running.

| Status (exit)              | Meaning                                                            | Response                                                                                                                                                                                                                                                                                                                                                         |
| -------------------------- | ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `succeeded` (0)            | Turn ended normally                                                | Consume the result.                                                                                                                                                                                                                                                                                                                                              |
| `idle` (5)                 | No events for `--idle` (120s); still running                       | Read the printed progress tail. A long command in flight (tests, e2e): `watch` again. No progress (usage limit reached, hung model): `interrupt`, then continue the task in a new session, with the user's model choice, briefed with what is already done.                                                                                                      |
| `blocked` (4)              | A permission request or question pending for `--block-grace` (20s) | Never approve it. Harmless and inside the task (deleting the agent's own scratch file, creating a directory it needs): do it yourself, then `reject --message` saying it is done. Out of scope: `reject --message` with what to do instead. Risky or unclear: ask the user. A pending question can't be rejected: `interrupt`, then answer with `run --session`. |
| `no-start` (3)             | No execution within `--startup-timeout` (90s); interrupted         | Rerun once with a new session; if it repeats, report the blocker.                                                                                                                                                                                                                                                                                                |
| `timeout` (7)              | Watched longer than `--max-runtime` (3600s); interrupted           | Report partial progress, or continue with a narrower follow-up.                                                                                                                                                                                                                                                                                                  |
| `failed`/`interrupted` (6) | OpenCode ended the turn unsuccessfully                             | Read the tail of `progress.log`; fix the specific cause or report.                                                                                                                                                                                                                                                                                               |

A script error (exit 2) prints one line on stderr; fix the cause (service not running, bad flag) or
report it.

## Consume and report

stdout holds the status, session ID, paths, and the final answer (capped; the full answer is in
`result.md`). Never read `events.jsonl` wholesale; `rg` it for a specific detail only. An agent's
report is a claim: before accepting it, inspect the diff, rerun the verification proportional to the
change, and validate review findings against the code. A passing test is a claim too: check that it
can fail (a UI wait can pass by matching the input the text was typed into). Preserve unrelated user work.

- "Failed once, passed on rerun; timing" is a finding, not noise. Reproduce it (force the timing with a
  short delay) before accepting the branch; a dismissed local flake is often the next CI failure.
- Fix small problems yourself (inline a trivial helper, deduplicate a copied test stub, drop a
  metric-only commit) instead of another agent round; send back work that needs the agent's context. Report
confirmed findings or changes, unverified claims and blockers, verification, and the OpenCode
session ID. For large responses, summarize and give the `result.md` path.
