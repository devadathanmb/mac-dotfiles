# Ansible Validation Scripts

## validate.sh

Quick validation script to catch issues before committing.

### Usage

```bash
# From ansible directory
./scripts/validate.sh
```

### What it checks

1. **Syntax Check** - Ensures all playbooks parse correctly
2. **Ansible Lint** - Catches best practice violations and potential bugs
3. **Deprecation Warnings** - Identifies future compatibility issues

The deprecation probe runs the `formulae` tasks from `backup.yml` in check mode.
It supplies a temporary, empty `brew` command for Linux environments that do not
have Homebrew installed. The copy module predicts differences without writing
the package list in check mode.
The temporary command and captured output are removed when the script exits.

### Exit Codes

- `0` - All checks passed ✅
- `1` - Critical issues found ❌

### When to run

- Before committing changes
- After modifying playbooks or roles
- When adding new tasks

## CI/CD Integration

The same checks run automatically on GitHub via `.github/workflows/ansible-validate.yml`:

- ✅ Runs on every push to main/develop
- ✅ Runs on all pull requests
- ⚠️ Ansible deprecation warnings are visible but non-blocking
- ❌ Syntax errors, lint failures, and validation command failures fail the build

## Configuration

Ansible lint rules are configured in `ansible/.ansible-lint`.

Current configuration skips overly strict rules for personal dotfiles:

- `var-naming[no-role-prefix]` - No need for role prefixes
- `name[casing]` - Flexible task naming
- `ignore-errors` - Sometimes you need to ignore errors
- `no-handler` - Using `when: changed` is acceptable
