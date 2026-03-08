#!/bin/bash
#
# Claude Code PostToolUse hook: Syntax check + lint changed Python files
#
# Runs after Edit/Write on Python files:
# 1. python -m py_compile — catches syntax errors fast
# 2. flake8 — style/lint violations using project config
#

set -e

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | python -c "import sys, json; print(json.load(sys.stdin).get('tool_input', {}).get('file_path', ''))")

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

if [[ ! "$FILE_PATH" =~ \.py$ ]]; then
    exit 0
fi

if [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

FAILED=0

# Step 1: syntax check
COMPILE_OUTPUT=$(python -m py_compile "$FILE_PATH" 2>&1 || true)
if [ -n "$COMPILE_OUTPUT" ]; then
    echo "Syntax error:"
    echo "$COMPILE_OUTPUT"
    FAILED=1
fi

# Step 2: flake8 lint (find repo root for project .flake8 config)
REPO_ROOT=$(git -C "$(dirname "$FILE_PATH")" rev-parse --show-toplevel 2>/dev/null || true)

if [ -n "$REPO_ROOT" ] && [ -f "$REPO_ROOT/.flake8" ]; then
    FLAKE8_OUTPUT=$(flake8 --config="$REPO_ROOT/.flake8" "$FILE_PATH" 2>&1 || true)
else
    FLAKE8_OUTPUT=$(flake8 "$FILE_PATH" 2>&1 || true)
fi

if [ -n "$FLAKE8_OUTPUT" ]; then
    echo "$FLAKE8_OUTPUT"
    FAILED=1
fi

exit $FAILED
