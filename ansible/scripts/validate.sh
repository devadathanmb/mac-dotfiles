#!/usr/bin/env bash
# Run syntax, lint, and a check-mode deprecation probe for the Ansible files.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANSIBLE_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ANSIBLE_DIR" || exit

TEMP_DIR="$(mktemp -d)" || exit
trap 'rm -rf "$TEMP_DIR"' EXIT

GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
RED=$'\033[0;31m'
NC=$'\033[0m'
FAILED=0

echo "Running Ansible validation checks..."

printf '\n%s\n' '1. Syntax check'
shopt -s nullglob
PLAYBOOKS=(playbooks/*.yml)
if ((${#PLAYBOOKS[@]} == 0)); then
    printf '%sNo playbooks found in ansible/playbooks%s\n' "$RED" "$NC"
    FAILED=1
fi
for playbook in "${PLAYBOOKS[@]}"; do
    if ansible-playbook "$playbook" --syntax-check > "$TEMP_DIR/syntax.out" 2>&1; then
        printf '%s✓%s %s\n' "$GREEN" "$NC" "$(basename "$playbook")"
    else
        status=$?
        printf '%s✗%s %s (exit %s)\n' "$RED" "$NC" "$(basename "$playbook")" "$status"
        cat "$TEMP_DIR/syntax.out"
        FAILED=1
    fi
done

printf '\n%s\n' '2. Ansible lint'
if ansible-lint playbooks/*.yml > "$TEMP_DIR/ansible-lint.out" 2>&1; then
    cat "$TEMP_DIR/ansible-lint.out"
    printf '%s✓%s Ansible lint passed\n' "$GREEN" "$NC"
else
    status=$?
    cat "$TEMP_DIR/ansible-lint.out"
    printf '%s✗%s Ansible lint failed (exit %s)\n' "$RED" "$NC" "$status"
    FAILED=1
fi

printf '\n%s\n' '3. Deprecation warning probe (check mode)'
# The selected formulae tasks invoke `brew` to read the installed package list.
# Provide an empty read-only stub so this probe also works on Linux runners
# without Homebrew. The copy module only predicts changes in check mode.
mkdir "$TEMP_DIR/bin" || exit
cat > "$TEMP_DIR/bin/brew" << 'BREW_STUB'
#!/usr/bin/env sh
exit 0
BREW_STUB
chmod +x "$TEMP_DIR/bin/brew" || exit
if PATH="$TEMP_DIR/bin:$PATH" ANSIBLE_DEPRECATION_WARNINGS=True \
    ansible-playbook playbooks/backup.yml --check --tags formulae \
    > "$TEMP_DIR/deprecation.out" 2>&1; then
    if grep -qi 'deprecation' "$TEMP_DIR/deprecation.out"; then
        printf '%s⚠%s Deprecation warnings found (non-blocking):\n' "$YELLOW" "$NC"
        grep -i 'deprecation' "$TEMP_DIR/deprecation.out"
    else
        printf '%s✓%s No deprecation warnings\n' "$GREEN" "$NC"
    fi
else
    status=$?
    cat "$TEMP_DIR/deprecation.out"
    printf '%s✗%s Check-mode deprecation probe failed (exit %s)\n' "$RED" "$NC" "$status"
    FAILED=1
fi

printf '\n'
if ((FAILED == 0)); then
    printf '%sAll validation checks passed.%s\n' "$GREEN" "$NC"
    exit 0
fi

printf '%sOne or more validation checks failed.%s\n' "$RED" "$NC"
exit 1
