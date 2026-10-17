# gpt-6.1-sol

Suited to delicate, stateful changes with many interacting invariants (layout effects, DOM
measurement, pointer and selection handling); produces sound stepwise commits. Slow, and runs can
stop mid-task at the provider's usage limit.

## Prompting

- Ask for one commit per step, each after the project's gate passes, so an interrupted run leaves
  usable work.
- Say commits are pre-authorized and it must not ask. Otherwise it stops with a blocking question
  ("may I commit?") after finishing the work. A pending question can't be rejected: interrupt, then
  answer with `run --session`.

## Check on review

- A run stopped by a usage limit shows as `idle` with no command in flight. Interrupt it, review its
  commits, and continue in a new session with a brief listing what is done.
- It may still land all steps as one commit; review it as one large change.
- It reports e2e failures that pass on rerun as "timing-sensitive" and moves on. Reproduce those
  yourself before merging.
- To satisfy hook-count or density metrics it groups unrelated hooks into large "session" or
  "navigation" hooks. Accept that only if the grouping reads as one concern.
