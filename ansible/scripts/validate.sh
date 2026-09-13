#!/usr/bin/env bash
# Ansible Validation Script
# Run this before committing to catch issues early

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANSIBLE_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ANSIBLE_DIR"

echo "🔍 Running Ansible validation checks..."
echo

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Track overall status
FAILED=0

# 1. Syntax Check
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  Syntax Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
for playbook in playbooks/*.yml; do
    if ansible-playbook "$playbook" --syntax-check > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $(basename "$playbook")"
    else
        echo -e "${RED}✗${NC} $(basename "$playbook")"
        FAILED=1
    fi
done
echo

# 2. Ansible Lint
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣  Ansible Lint"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if ansible-lint playbooks/*.yml 2>&1 | tee /tmp/ansible-lint.out; then
    echo -e "${GREEN}✓${NC} No critical issues found"
else
    # Check if it's just warnings
    if grep -q "Passed:" /tmp/ansible-lint.out; then
        echo -e "${YELLOW}⚠${NC}  Warnings found (non-blocking)"
    else
        echo -e "${RED}✗${NC} Linting failed"
        FAILED=1
    fi
fi
echo

# 3. Deprecation Check (sample - runs backup playbook as it's fast)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣  Deprecation Warnings Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
DEPRECATION_OUTPUT=$(ANSIBLE_DEPRECATION_WARNINGS=True ansible-playbook playbooks/backup.yml --check --tags formulae 2>&1)
if echo "$DEPRECATION_OUTPUT" | grep -qi "deprecation"; then
    echo -e "${YELLOW}⚠${NC}  Deprecation warnings found:"
    echo "$DEPRECATION_OUTPUT" | grep -i "deprecation"
    echo
    echo "Note: Deprecation warnings are non-blocking but should be addressed"
else
    echo -e "${GREEN}✓${NC} No deprecation warnings"
fi
echo

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All validation checks passed!${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    exit 0
else
    echo -e "${RED}❌ Some validation checks failed${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    exit 1
fi
