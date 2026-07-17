## Token-Efficient Execution

- **Batch tool calls.** Combine independent inspections, searches, and verification commands into as few tool calls as possible. Prefer a single call with multiple sequential commands over multiple separate calls.
- **Inspect once, implement in one pass.** Read the relevant files once, make all changes in a single pass where possible, and run one proportional verification pass.
- **Keep output narrow.** Prefer targeted `rg`, bounded file ranges, path-specific diffs, and concise status output. Don't dump complete files or full diffs when a path, symbol, or diff stat is enough.
- **Don't over-search.** Avoid broad repository searches when specific paths, symbols, or line ranges will do. Don't use web search when the answer is in the repo, installed source, or project docs.
- **Verify proportionally.** One focused test or build is normally sufficient for a low-risk change. Don't escalate into multiple test, editor, runtime, and debugger passes unless a failure requires it.
- **Diagnose failures narrowly.** After a failed verification, investigate the specific error — don't retry blindly, poll, or swap verification mechanisms without reason.
- **No ad-hoc scripts for small changes.** Don't create throwaway verification scripts unless ordinary project checks can't validate the behavior.
- **Ask when uncertain.** If in doubt about how to proceed, ask rather than guess.
