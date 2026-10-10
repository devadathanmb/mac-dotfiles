---
name: create-pull-request
description: >
  Create, draft, or update GitHub pull requests.
---

# GitHub Pull Requests

## Output

Use `<type>: <concise one-line summary>` with one of these four types:

| Type | Use for |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Restructure without a feature or bug fix |
| `chore` | Maintenance, dependencies, or configuration |

Keep the title specific and clear without being terse or verbose.

Use this body:

```markdown
## Summary
- <brief description of the bug or behavior changed>
- <regression coverage, only when the diff adds meaningful coverage>

## Related
<issue or ticket link>
```

Include `## Related` only when the user supplies an issue or ticket link, or the
repository PR template requires it; otherwise omit it. Keep the Summary focused
on final product or code behavior, not test execution.

## Workflow

### 1. Gather context

Determine the base before inspecting changes. For an update, read it from
`gh pr view --json baseRefName`; for creation, use the user-specified base. Use
that branch wherever `<base>` appears below.

```bash
git fetch origin
git diff origin/<base>...HEAD
```

Use paths to narrow the diff only when needed. Treat the merge-base diff as the
source of truth; commit messages and branch history are only hints. Use user,
issue, and PR context to infer intent, but describe only items present in the
final diff.

### 2. Draft the PR

Write for a reviewer of the final squashed change. Explain the bug or behavior
changed, meaningful regression coverage in the diff, and why the change is
needed only when it is not obvious from the title and behavior.

For a small PR, use one or two Summary bullets; do not add bullets merely to
look complete. For a genuinely large PR, add subsections only when they help
reviewers navigate distinct areas. Use Markdown to improve readability: bold
key concepts, use backticks for identifiers, and use nested bullets for
grouping.

A strong PR uses a specific title, explains the changed behavior, and describes
regression coverage without reporting test execution:

**Title:** `fix: prevent duplicate charges on retried payment webhooks`

**Body:**

```markdown
## Summary
- Prevents **duplicate charges** when a payment webhook is retried by reusing the existing `idempotency_key`.
- Adds regression coverage for retry behavior:
  - repeated deliveries of the same event
  - retries after the original charge succeeds

## Related
#123
```

Apply these content rules:

- Trace every Summary bullet to a specific hunk in
  `git diff origin/<base>...HEAD`; delete it if it cannot be mapped. Exclude
  local-only context and gitignored or scratch artifacts unless requested.
- Do not include test commands, test group IDs, pass counts, coverage
  percentages, lint/build status, or generic claims such as "tests pass" or
  "verified." These are execution metadata, not a summary of the change.
- A regression-test bullet may describe behavior protected by a test in the
  diff, but not how it ran or how many tests passed. Add a testing section only
  when requested or required by the repository PR template.
- Do not mention files, resources, decisions, skipped changes, or exclusions
  unless they appear as changed lines in the final diff. Do not add "left
  unchanged," "did not change," "already exists," or "because X was already
  configured" unless the diff changes documentation or comments saying so.
- Describe the final shape instead of branch history. Rewrite commit messages
  into a cohesive summary rather than copying them.
- Do not invent rationale; ask once if a material reason is unclear.

### 3. Confirm

Show the complete title and body before `gh pr create`, `gh pr edit`, or another
mutating command. Read-only commands such as `gh pr view` may run while
gathering context. Wait for explicit confirmation; apply requested edits and
re-show the preview if they significantly change it.

### 4. Execute

If the branch is not pushed, run `git push -u origin HEAD`. Write the approved
body to a temporary file, store its path in `pr_body_file`, then run the matching command chained with `rm` so
the temp file is removed in the same call:

```bash
gh pr create --base "<base>" --title "<type>: <title>" --body-file "$pr_body_file" && rm "$pr_body_file"
gh pr edit --title "<type>: <title>" --body-file "$pr_body_file" && rm "$pr_body_file"
```

Use `--body-file` so the user can copy and run the same command manually. After
creation or update, output the PR URL. If `gh` is not authenticated, ask the
user to run `gh auth login`.
