---
name: git-commit
description: 'Creates git commits with well-formed conventional commit messages. Use whenever the user wants to commit changes, asks for a commit message, or mentions "/commit". Reads the actual diff, proposes a message, confirms with the user, then commits.'
allowed-tools: Bash
---

# Git Commit with Conventional Commits

## Overview

Create standardized, semantic git commits using the Conventional Commits specification. Analyze the actual diff to determine the appropriate type and message.

## Conventional Commit Format

```
<type>: <description>

[optional body]

[optional footer(s)]
```

## Commit Types

| Type        | Purpose                          |
| ----------- | -------------------------------- |
| `feat`      | New feature                      |
| `fix`       | Bug fix                          |
| `refactor`  | Code refactor (no feature/fix)   |
| `chore`     | Maintenance, deps, config, misc  |

## Breaking Changes

```
# BREAKING CHANGE footer
feat: allow config to extend other configs

BREAKING CHANGE: `extends` key behavior changed
```

## Workflow

### 1. Analyze Diff

```bash
# If files are staged, use staged diff
git diff --staged

# If nothing staged, use working tree diff
git diff

# Also check status
git status --porcelain
```

**The diff is the sole source of truth for the commit body.** Read it in full before writing a single bullet. Session conversation, discussed-but-not-staged changes, and anything not visible as an added or removed line in the diff must not appear in the message.

### 2. Stage Files (if needed)

If nothing is staged or you want to group changes differently:

```bash
# Stage specific files
git add path/to/file1 path/to/file2

# Stage by pattern
git add *.test.*
git add src/components/*

# Interactive staging
git add -p
```

**Never commit secrets** (.env, credentials.json, private keys).

### 3. Generate Commit Message

Analyze the diff to determine:

- **Type**: What kind of change is this?
- **Subject line**: A single descriptive line that clearly explains *what* is being changed. Be specific and verbose enough that someone reading the git log immediately understands the change without needing to look at the diff. Don't be vague — "fix bug" is bad, "fix null pointer crash when user profile image is missing" is good. No length limit, but it must remain a single line.
- **Body**: Explain *what exactly* was changed — which files, functions, logic, or behavior was modified and how. This is where you elaborate on the subject. Every commit should have a body unless the change is completely trivial.
- **Diff-only rule**: Every bullet must trace to a specific hunk in the diff — a line added or removed. If you cannot point to the exact lines, omit the bullet. Do not use session context to fill in bullets that the diff does not support.

**Body style** (when the body is more than a sentence or two):

- Use **bullet points** (one distinct change, file, or behavior per bullet).
- Keep **Markdown minimal** in the commit text: no headings, tables, or decorative formatting unless the user explicitly asked for that format.
- Use **backticks** only for short literals worth highlighting: paths, flags, commands, function or type names, config keys — not full sentences.

### 4. Confirm with User

Before committing, show the proposed message to the user and ask for confirmation:

```
Proposed commit message:

  <type>: <descriptive subject line>

  - <bullet: what changed; use `paths` / `symbols` in backticks where helpful>
  - <bullet: …>

Proceed with this commit? (yes to confirm, or provide edits)
```

Wait for the user to confirm or request changes. Apply any edits they provide before committing.

### 5. Execute Commit

```bash
git commit -m "$(cat <<'EOF'
<type>: <descriptive subject line>

- <bullet body lines; backticks for literals>
EOF
)"
```

## Best Practices

- One logical change per commit
- Present tense: "add" not "added"
- Imperative mood: "fix bug" not "fixes bug"
- Subject line should be specific enough to understand the change from git log alone — verbose is fine
- Body should describe exactly what was changed: which functions, files, or behaviors, and how — prefer bullets, minimal Markdown, backticks for literals (see **Body style** above)

## Git Safety Protocol

- NEVER run destructive commands (--force, hard reset) without explicit request

## Anti-Patterns

| Anti-Pattern | Fix |
|---|---|
| Adding bullets from session chat that are absent from the diff | Only describe what the diff shows |
| Describing a change as "merged X into Y" when the diff shows Y as purely new | Trust the diff: if the base had no Y, Y is new — say "added", not "merged" |
| Describing removal of a symbol not visible in the diff | Map every bullet to specific diff hunks before writing |
| Describing an intra-session refactor on a new file as a "drop" or "remove" | If the file is new, there are no removals — the diff only shows additions. Something cleaned up before the first commit never existed in the diff; omit it entirely |
| Using session discussion to infer what "must have changed" | If it is not in the diff, it is not in the message |
