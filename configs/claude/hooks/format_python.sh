#!/bin/bash
#
# Claude Code PostToolUse hook: Format only changed lines with black
#
# This hook runs after the agent edits a file. It:
# 1. Reads the hook input JSON from stdin
# 2. Checks if the file is a Python file
# 3. Uses git diff to find which lines changed
# 4. Runs black --line-ranges only on those lines
#

set -e

# Read JSON input from stdin
INPUT=$(cat)

# Extract file_path from JSON input using python (available in this project)
# Claude Code uses tool_input.file_path structure
FILE_PATH=$(echo "$INPUT" | python -c "import sys, json; print(json.load(sys.stdin).get('tool_input', {}).get('file_path', ''))")

# Exit early if no file path
if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Only process Python files
if [[ ! "$FILE_PATH" =~ \.py$ ]]; then
    exit 0
fi

# Check if file exists
if [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

# Get changed line ranges from git diff
# -U0 means no context lines, so we only get the changed lines
# Format: @@ -old_start,old_count +new_start,new_count @@
DIFF_OUTPUT=$(git diff --no-color -U0 -- "$FILE_PATH" 2>/dev/null || true)

if [ -z "$DIFF_OUTPUT" ]; then
    # No uncommitted changes, try comparing with HEAD
    DIFF_OUTPUT=$(git diff --no-color -U0 HEAD -- "$FILE_PATH" 2>/dev/null || true)
fi

if [ -z "$DIFF_OUTPUT" ]; then
    # Still no diff output - file might be new/untracked, format the whole file
    black --quiet "$FILE_PATH" 2>/dev/null || true
    exit 0
fi

# Parse diff output to extract line ranges
# Looking for lines like: @@ -X,Y +A,B @@ where A is start line, B is count
LINE_RANGES=""
while IFS= read -r line; do
    if [[ "$line" =~ ^@@.*\+([0-9]+)(,([0-9]+))?.* ]]; then
        START_LINE="${BASH_REMATCH[1]}"
        COUNT="${BASH_REMATCH[3]:-1}"  # Default to 1 if no count specified

        # Skip if count is 0 (deletion only)
        if [ "$COUNT" = "0" ]; then
            continue
        fi

        END_LINE=$((START_LINE + COUNT - 1))

        # Ensure we have valid line numbers
        if [ "$START_LINE" -gt 0 ] && [ "$END_LINE" -ge "$START_LINE" ]; then
            LINE_RANGES="$LINE_RANGES --line-ranges=${START_LINE}-${END_LINE}"
        fi
    fi
done <<< "$DIFF_OUTPUT"

# If we found line ranges, format only those lines
if [ -n "$LINE_RANGES" ]; then
    # shellcheck disable=SC2086
    black --quiet $LINE_RANGES "$FILE_PATH" 2>/dev/null || true
fi

exit 0
