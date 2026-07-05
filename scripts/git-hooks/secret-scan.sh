#!/usr/bin/env bash
set -euo pipefail

SENSITIVE_PATTERN='(\.env(\.[a-zA-Z0-9_-]+)?[^a-zA-Z0-9_-]|["\x27]\.env["\x27]|\.env$|\bfyle\b|\btoken\b|\bsecret\b|\bapi[_-]?key\b|\bpassw(or)?d\b|\bcredential\b|\bprivate[_-]?key\b|\bauth[_-]?token\b|\baccess[_-]?key\b)'

staged_diff=$(
    git diff --cached -U0 -- . \
        ':(exclude)scripts/git-hooks/secret-scan.sh' \
        ':(exclude).pre-commit-config.yaml' |
        grep '^+[^+]' |
        cut -c2- || true
)

if [ -z "$staged_diff" ]; then
    exit 0
fi

matches=$(printf '%s\n' "$staged_diff" | rg -i -n --color=always "$SENSITIVE_PATTERN" 2> /dev/null || true)

if [ -z "$matches" ]; then
    exit 0
fi

printf '\n%s\n' 'SECRET SCAN FAILED - commit blocked'
printf '%s\n\n' 'Sensitive keyword(s) detected in staged changes:'
printf '%s\n\n' "$matches"
printf '%s\n' 'Remove or redact the references above before committing.'
printf '%s\n' 'To bypass, use: git commit --no-verify'
exit 1
