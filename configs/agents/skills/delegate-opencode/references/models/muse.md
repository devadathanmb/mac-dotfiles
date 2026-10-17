# muse-spark

Handles judgment-heavy, multi-file work when given the invariants: refactors, API redesigns, and
component splits that must keep behavior identical. Writes tests for what it extracts and runs long
verification suites to the end.

## Prompting

- State design decisions (names, signatures, route tables) as decided; anything left open gets its
  own reasonable but different shape.
- On large refactors, ask for one commit per passing step.
- To continue another session's work, list its commits and have it review them against the
  invariants before finishing.
- Say where pure (non-UI) modules belong; otherwise it puts them next to their only caller.
- Say "no speculative defensive code" when you want none.

## Check on review

- It may end its turn while its own verification is still running, with no final report. Require
  verification to finish first; if it happens anyway, rerun verification yourself once its leftover
  process exits.
- Stray files it leaves are listed under "unsure / undone".
- Edits outside its owned files appear as reported deviations.
- Given a numeric target (complexity, coverage), it reaches it by fragmenting code: one-line
  accessors, boolean-returning `applyX` chains, "model" functions that only move ternaries. Reject
  these; it rewrites cleanly when told which helpers to inline and which rule to name instead.
- Captures command output in `/tmp/*.log` despite a no-scratch-files rule, then blocks asking to `rm`
  them. It also probes behavior with ad-hoc scripts that create temp dirs (another block). Forbid both
  by name in the brief.
- Render tests that need browser globals get a stub copied into each test file; consolidate them.
