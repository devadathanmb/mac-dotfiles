# Ansible Dotfiles Decisions

## Decision 1: Architecture Choice

**Date**: 2026-02-01

**Decision**: Role-based architecture with separate playbooks

**Rationale**:
- Modular and reusable
- Industry standard pattern
- Easy to test individual components
- Enables cross-platform support

**Implementation**:
- Main `site.yml` includes all plays
- Individual playbooks for specific tasks
- Roles: common, dotfiles, packages, homebrew, system, shell, apps

---

## Decision 2: Inventory Strategy

**Date**: 2026-02-01

**Decision**: Single localhost inventory initially

**Rationale**:
- Simplifies initial implementation
- Can expand to multi-host later
- No remote SSH needed for local setup

**Implementation**:
```
inventories/
  localhost/
    inventory.yml
```

---

## Decision 3: Dotfiles Sync Method

**Date**: 2026-02-01

**Decision**: Use `ansible.posix.synchronize` (rsync-based) for directories

**Rationale**:
- More efficient for large config directories
- Preserves permissions and attributes
- `delete: no` prevents accidental data loss

**Alternative Considered**: Template module
- Better for single files needing Jinja2 templating
- Use for `.gitconfig` where templating is needed

**Implementation**:
- Directories: `ansible.posix.synchronize`
- Single files with templating: `ansible.builtin.template`

---

## Decision 4: Platform Detection

**Date**: 2026-02-01

**Decision**: Use `ansible_system` variable for OS detection

**Rationale**:
- Built-in Ansible fact
- Reliable for Linux/Darwin detection
- Simple implementation

**Implementation**:
```yaml
- name: Load OS-specific vars
  ansible.builtin.include_vars:
    file: "vars/{{ ansible_system | lower }}.yml"
```

---

## Decision 5: Keep Dotbot as Backup

**Date**: 2026-02-01

**Decision**: Maintain existing Dotbot setup during transition

**Rationale**:
- Reduces risk of breaking existing setup
- Allows parallel testing
- Easy rollback if needed

**Implementation**:
- Keep `install.conf.yaml` and Dotbot files
- Document migration progress
- Remove Dotbot after Ansible is proven

---

## Decision 6: Package Installation Order

**Date**: 2026-02-01

**Decision**: Install Homebrew packages after dotfiles

**Rationale**:
- Some packages may depend on config files
- Prevents circular dependencies
- Allows dotfiles to be ready for package hooks

**Implementation**:
```yaml
# site.yml play order:
- import_playbook: playbooks/dotfiles.yml
- import_playbook: playbooks/system.yml
- import_playbook: playbooks/packages.yml
- import_playbook: playbooks/shell.yml
- import_playbook: playbooks/apps.yml
```

---

## Decision 7: Secret Management Strategy

**Date**: 2026-02-01

**Decision**: Defer Ansible Vault implementation

**Rationale**:
- Current dotfiles don't have secrets in repo
- Can add Vault later without breaking changes
- Simplifies initial implementation

**Implementation**:
- Document vault requirements for future
- Keep secrets out of version control now
- Add vault when sensitive configs are needed
