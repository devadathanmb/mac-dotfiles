# Orchestrating parallel OpenCode agents

## Setup

- One git worktree and branch per task. Prepare anything an agent needs outside its worktree (e.g. a
  per-task copy of a fixture repo) before starting it.
- When the user asked for branch-based delegation, authorize commits on the task branch; agents
  never merge, rebase, or push.
- Keep one shared preamble (ground rules, permissions, verification, report format) plus one file
  per task, concatenated into the prompt. When an agent hits a new failure, add the fix to the
  preamble so later tasks avoid it.

## Splitting

- Split by file ownership; tasks that edit the same file run in sequence. Phases in a plan are
  for dependencies, not topics: tasks with disjoint files can start together even when the plan
  lists them in different phases.
- Land shared foundations in a serial task first, then branch the parallel tasks from it and give
  them the exact signatures that landed.
- Plan the merge order for tasks that touch shared registries (schema, type, and large test files).
- Run at most about three browser/e2e suites at once; more causes timing flakes that agents chase.

## Merging

- Review every diff before merging: owned-file boundaries, invariants, agent-facing output, module
  placement, stray files. Fix small issues yourself; send larger ones back with `run --session`.
- Cherry-picking task branches onto the base keeps history linear. When an agent reworked its own
  commit after review, squash the two so the rejected version doesn't stay in history.
- Each branch passing on its own doesn't cover the combination: rerun the full gate (including
  browser/e2e) on the merged result before reporting it done.
- Resolve each conflict region separately, then compare the test list before and after; a bulk
  resolution silently drops one side's tests or code.
- Never run two builds or test suites in one worktree at once, including an agent's leftover run; a
  build that cleans its output directory fails the other with false errors.
