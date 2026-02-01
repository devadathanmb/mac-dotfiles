# Ansible Dotfiles Learnings

## Research Date: 2026-02-01

---

## Key Patterns Discovered

### 1. Role-Based Architecture (Most Common Pattern)

**From**: Brian Hoffpauir's article and Shrijal Acharya's setup

**Pattern**: 
- Separate roles for: dotfiles, packages, system, apps
- Each role has: tasks/, files/, templates/, vars/, defaults/
- Enables reusability and sharing

**Example Structure**:
```
roles/
  dotfiles/
    tasks/main.yml
    files/dotfiles_root/
    templates/
    vars/
      linux.yml
      darwin.yml
```

### 2. Cross-Platform Detection

**From**: Ansible documentation and Brian Hoffpauir's implementation

**Key Variables**:
- `ansible_system` → 'Linux' or 'Darwin'
- `ansible_os_family` → 'Darwin', 'RedHat', 'Debian'
- `ansible_distribution` → 'macOS', 'Ubuntu', 'Fedora'

**Implementation**:
```yaml
- name: Load OS-specific vars
  ansible.builtin.include_vars:
    file: "vars/{{ ansible_system | lower }}.yml"
```

### 3. Idempotent Symlink Management

**From**: Multiple sources

**Best Practice**: Use `ansible.posix.synchronize` with rsync
```yaml
- name: Sync dotfiles
  ansible.posix.synchronize:
    src: files/dotfiles_root/
    dest: "{{ ansible_env.HOME }}"
    recursive: yes
    delete: no
```

**Alternative**: Template module for static files
```yaml
- name: Deploy dotfile
  ansible.builtin.template:
    src: "{{ item }}.j2"
    dest: "{{ ansible_env.HOME }}/{{ item }}"
    mode: '0644'
```

### 4. Homebrew Management (macOS)

**From**: Your existing `brew-setup.sh` and Ansible modules

**Key Considerations**:
- Use `homebrew.homebrew.homebrew` collection
- Handle Apple Silicon vs Intel differences
- Use `--check` for dry-run validation

### 5. Jinja2 Templating for Conditional Config

**From**: Brian Hoffpauir's `.bashrc.j2` example

**Example**:
```jinja2
{% if ansible_system == 'Linux' %}
alias ls='ls --color=auto'
{% elif ansible_system == 'Darwin' %}
alias ls='ls -G'
{% endif %}
```

---

## Tools & Collections Identified

| Tool | Purpose | Ansible Module |
|------|---------|----------------|
| Homebrew | Package management | `homebrew.homebrew.homebrew` |
| macOS Defaults | System preferences | `community.general.macos_defaults` |
| Git | Version control | `ansible.builtin.git` |
| Rsync | File sync | `ansible.posix.synchronize` |
| File operations | Symlinks, permissions | `ansible.builtin.file` |

---

## Installation Patterns

### Python Virtual Environment (Recommended)
```bash
python3 -m venv ./venv
source ./venv/bin/activate
pip install ansible
pip freeze > requirements.txt
```

### Alternative: Homebrew
```bash
brew install ansible
```

---

## Best Practices Summary

1. **Use roles** for modularity and reusability
2. **Detect platform** early and load OS-specific vars
3. **Make tasks idempotent** (safe to run multiple times)
4. **Use `--check` mode** for dry-run validation
5. **Separate static files** (files/) from dynamic (templates/)
6. **Version control** your Ansible project
7. **Test in VMs** before production use
8. **Use Ansible Vault** for secrets

---

## Sources

- https://dev.to/shricodev/how-i-manage-my-system-and-dotfiles-with-ansible-8m1
- https://www.bhoffpauir.com/blog/article/using-ansible-to-manage-dotfiles-sWPGKq
- https://docs.ansible.com/ansible/latest/tips_tricks/ansible_tips_tricks.html
- https://docs.ansible.com/ansible/latest/tips_tricks/sample_setup.html
- https://wiki.archlinux.org/title/Dotfiles

---

## Task 1: Ansible Foundation Setup (2026-02-01)

### What Was Created

**Directory Structure**:
```
ansible/
├── ansible.cfg              # Local execution config
├── requirements.yml         # Collection dependencies
├── inventory/
│   └── localhost.yml        # Local inventory
├── group_vars/
│   └── all.yml              # Shared variables
├── playbooks/               # (empty, for future playbooks)
└── roles/                   # (empty, for future roles)
```

### Configuration Details

**ansible.cfg**:
- `inventory = inventory/localhost.yml` - Points to local inventory
- `host_key_checking = False` - Disables SSH key checking for local execution

**requirements.yml**:
- Specifies `community.general` collection (needed for homebrew, osx_defaults)
- Installed successfully via `ansible-galaxy collection install -r requirements.yml`

**inventory/localhost.yml**:
- Single host: `localhost`
- `ansible_connection: local` - Executes locally without SSH
- `ansible_python_interpreter: "{{ ansible_playbook_python }}"` - Uses playbook's Python

**group_vars/all.yml**:
- `dotfiles_repo: /Users/devadathanmb/.mac-dots` - Root path for all roles to reference

### Verification

✅ All 4 files created with correct content
✅ Directory structure matches specification
✅ `ansible-galaxy collection install` completed (community.general already installed)
✅ Test command successful: `ansible all -i inventory/localhost.yml -m debug` returned SUCCESS

### Key Insights for Next Tasks

1. **Inventory is ready** - Roles can reference `localhost` group
2. **Variables are centralized** - All roles can access `dotfiles_repo` via group_vars
3. **Local execution configured** - No SSH needed, runs directly on macOS
4. **Collections installed** - `community.general` available for homebrew/osx_defaults modules

### Next Steps (Tasks 2-5b)

- Task 2: Create `dotfiles` role with symlink management
- Task 3: Create `homebrew` role for package installation
- Task 4: Create `macos` role for system preferences
- Task 5a: Create main playbook
- Task 5b: Create bootstrap playbook

