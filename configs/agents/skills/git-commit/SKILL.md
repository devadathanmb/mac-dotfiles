---
name: git-commit
description: 'Creates git commits with well-formed conventional commit messages. Use whenever the user wants to commit changes, asks for a commit message, or mentions "/commit". Reads the actual diff, proposes a message, confirms with the user, then commits.'
license: MIT
allowed-tools: Bash
---

# Git Commit with Conventional Commits

## Overview

Create standardized, semantic git commits using the Conventional Commits specification. Analyze the actual diff to determine the appropriate type and message.

## Conventional Commit Format

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

The scope is required and should be derived from the diff — use the component, module, directory, or area being changed (e.g., `auth`, `ui`, `api`, `config`, `deps`).

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
feat(config): allow config to extend other configs

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
- **Scope**: What area, module, or component does this change affect? Derive from the diff — look at the files changed and identify the logical grouping (e.g., `auth`, `ui`, `api`, `config`, `deps`). Keep it short and lowercase.
- **Subject line**: A single descriptive line that clearly explains *what* is being changed. Be specific and verbose enough that someone reading the git log immediately understands the change without needing to look at the diff. Don't be vague — "fix bug" is bad, "fix null pointer crash when user profile image is missing" is good. No length limit, but it must remain a single line.
- **Body**: Explain *what exactly* was changed — which files, functions, logic, or behavior was modified and how. This is where you elaborate on the subject. Every commit should have a body unless the change is completely trivial.

### 4. Confirm with User

Before committing, show the proposed message to the user and ask for confirmation:

```
Proposed commit message:

  <type>(<scope>): <descriptive subject line>

  <body explaining what exactly was changed>

Proceed with this commit? (yes to confirm, or provide edits)
```

Wait for the user to confirm or request changes. Apply any edits they provide before committing.

### 5. Execute Commit

```bash
git commit -m "$(cat <<'EOF'
<type>(<scope>): <descriptive subject line>

<body explaining what exactly was changed>
EOF
)"
```

## Best Practices

- One logical change per commit
- Present tense: "add" not "added"
- Imperative mood: "fix bug" not "fixes bug"
- Subject line should be specific enough to understand the change from git log alone — verbose is fine
- Body should describe exactly what was changed: which functions, files, or behaviors, and how
- Reference issues in the body: `Closes #123`, `Refs #456`

## Git Safety Protocol

- NEVER update git config
- NEVER run destructive commands (--force, hard reset) without explicit request
- NEVER skip hooks (--no-verify) unless user asks
- NEVER force push to main/master
- If commit fails due to hooks, fix and create NEW commit (don't amend)
