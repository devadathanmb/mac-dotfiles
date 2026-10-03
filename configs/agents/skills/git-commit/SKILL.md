---
name: git-commit
description: >
  Create a git commit or draft a conventional commit message when the user
  explicitly asks to commit, requests a commit message, or invokes /commit.
---

# Git Commits

## Message format

```text
<type>: <specific one-line description>

[optional body]

[optional footer]
```

Use one of these four types:

| Type | Use for |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Restructuring without a feature or bug fix |
| `chore` | Maintenance, dependencies, or configuration |

Write the subject in present-tense imperative mood (`add`, not `added` or
`adds`). Make it specific enough to understand from the log without reading the
diff. It may be verbose but must remain one line; do not impose an arbitrary
length limit.

Include a body unless the change is completely trivial. Explain what changed
and how, including relevant files, functions, logic, or behavior. Use bullets
for distinct changes. Keep Markdown minimal: no headings, tables, or decoration
unless requested. Use backticks only for short literals such as paths, flags,
commands, symbols, types, and config keys.

For a breaking change, append a `BREAKING CHANGE:` footer:

```text
feat: allow configs to extend other configs

BREAKING CHANGE: `extends` now replaces inherited arrays
```

A strong message is specific and explains the changed behavior without relying
on conversation context:

```text
fix: avoid profile crashes when image metadata is missing

- Fall back to the default avatar when `profile_image` is null.
- Add coverage for profiles without image metadata.
```

## Workflow

### 1. Select the commit scope

```bash
git status --porcelain
git diff --staged
```

Use only the staged diff when present; otherwise inspect `git diff` and stage
the intended files with explicit paths. The selected changes must form one
logical commit. If already-staged changes contain unrelated work, ask the user
how to group them. Never commit secrets such as `.env`, credentials, or private
keys.

Before drafting, read the complete selected diff. Re-run `git diff --staged`
after any staging changes. For a message-only request, inspect the staged diff
when present or the working-tree diff otherwise, and directly read relevant
untracked files because `git diff` omits them; do not stage or commit anything.

### 2. Draft from the diff

The selected diff is the sole source of truth for a commit. For a message-only
request, directly inspected untracked files may also support the draft. Every
factual claim and body bullet must map to a specific diff line or inspected
untracked content. Omit session discussion and changes outside that scope.

Describe the final state exactly. Do not describe a new file as merged from
another file or claim that a symbol was removed unless the diff shows it.

### 3. Confirm

For a commit request, show the exact proposed message and wait for explicit
confirmation. Apply requested edits before committing. If the user requested
only a message, return it and stop.

### 4. Commit

Write the approved message to a temporary file, store its path in
`commit_message_file`, and pass it with `-F`. Never place a multiline message
in command substitution or an inline shell argument because quoting is
unreliable.

```bash
git commit -F "$commit_message_file" && rm "$commit_message_file"
```

Never run destructive commands such as force operations or hard resets unless
the user explicitly requests them.
