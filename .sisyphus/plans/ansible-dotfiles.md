# Ansible Dotfiles Management Plan

> **Status**: ANALYSIS COMPLETE | **Created**: 2026-02-01 | **Branch**: `feature/ansible-dotfiles-management`

---

## Executive Summary

This plan outlines the migration from the current Dotbot-based dotfiles management to Ansible, enabling:
- **Cross-platform support** (macOS + future Linux)
- **System-level automation** (Homebrew, macOS defaults, packages)
- **Idempotent configuration** (safe to run multiple times)
- **Modular architecture** (roles for reusability)
- **Better testing** (dry-run mode, check mode)

---

## Current State Analysis

### Existing Setup Overview

| Component | Technology | Location |
|-----------|-----------|----------|
| **Dotfiles Manager** | Dotbot | `install.conf.yaml` |
| **Bootstrap Script** | Bash | `bootstrap-mac.sh` |
| **Package Manager** | Homebrew | `homebrew/brew-*.txt` |
| **System Config** | Bash/macOS defaults | `mac/mac-setup.sh` |
| **Shell Configs** | Zsh + Fish | `configs/{zsh,fish}/` |
| **Editor Configs** | VSCode + Cursor | `configs/{vscode,cursor}/` |

### Files to Manage (from `install.conf.yaml`)

```
Root Dotfiles:
- ~/.tmux.conf → .tmux.conf
- ~/.vimrc → .vimrc
- ~/.ideavimrc → .ideavimrc
- ~/.curlrc → .curlrc
- ~/.psqlrc → .psqlrc
- ~/.wgetrc → .wgetrc
- ~/.p10k.zsh → .p10k.zsh
- ~/.gitconfig → .gitconfig
- ~/.zshrc → .zshrc
- ~/.zprofile → .zprofile

XDG Config Dirs:
- ~/.config/fish → configs/fish
- ~/.config/gh → configs/gh
- ~/.config/zsh → configs/zsh
- ~/.config/cvim → configs/cvim
- ~/.config/ghostty → configs/ghostty
- ~/.config/atuin → configs/atuin
- ~/.config/pgcli → configs/pgcli
- ~/.config/htop → configs/htop
- ~/.config/btop → configs/btop
- ~/.config/mpv → configs/mpv
- ~/.config/zed → configs/zed

macOS App Data:
- ~/Library/Application Support/Code/User/settings.json → configs/vscode/settings.json
- ~/Library/Application Support/Code/User/keybindings.json → configs/vscode/keybindings.json
- ~/Library/Application Support/Cursor/User/settings.json → configs/cursor/settings.json
- ~/Library/Application Support/Cursor/User/keybindings.json → configs/cursor/keybindings.json

Scripts:
- ~/.local/bin → scripts/*
```

### Package Inventory

| Category | Count | Examples |
|----------|-------|----------|
| **Formulae** | ~245 | fish, tmux, neovim, zoxide, atuin, fzf, eza, bat, ripgrep, etc. |
| **Casks** | ~40 | cursor, visual-studio-code, ghostty, iterm2, raycast, etc. |

---

## Ansible Best Practices Research Summary

### Key Patterns from Industry Research

1. **Role-Based Architecture**
   - Separate concerns into roles (dotfiles, packages, system, apps)
   - Enable reusability and sharing

2. **Platform Detection & Conditional Logic**
   - Use `ansible_system`, `ansible_os_family` for cross-platform
   - Jinja2 templating for conditional config

3. **Idempotent Operations**
   - All tasks should be safe to run multiple times
   - Use `check_mode: yes` for dry-run validation

4. **Symlink Management**
   - Use `ansible.posix.synchronize` with rsync
   - Alternative: `ansible.builtin.template` for static files

5. **Secret Management**
   - Use Ansible Vault for sensitive data
   - Keep secrets out of version control

6. **Git-Based Workflow**
   - Store dotfiles in Git for version history
   - Git submodules for plugin managers (TPM, vim-plugins)

---

## Proposed Ansible Architecture

```
ansible/
├── ansible.cfg                 # Ansible configuration
├── requirements.yml            # Galaxy roles/collections
├── inventories/
│   └── localhost/
│       └── inventory.yml       # Host definitions
├── group_vars/
│   └── all/
│       └── main.yml            # Global variables
├── host_vars/
│   └── localhost.yml           # Host-specific variables
├── playbooks/
│   ├── site.yml                # Main entry point (all plays)
│   ├── dotfiles.yml            # Dotfiles deployment
│   ├── packages.yml            # Package installation
│   ├── system.yml              # System configuration
│   └── apps.yml                # Application setup
└── roles/
    ├── common/                 # Common prerequisites
    │   └── tasks/
    │       └── main.yml
    ├── dotfiles/               # Dotfiles symlink management
    │   ├── tasks/
    │   │   └── main.yml
    │   ├── files/
    │   │   └── dotfiles_root/
    │   │       ├── .tmux.conf
    │   │       ├── .vimrc
    │   │       └── ...
    │   └── templates/
    │       └── .gitconfig.j2
    ├── packages/               # Package installation
    │   ├── tasks/
    │   │   └── main.yml
    │   └── handlers/
    │       └── main.yml
    ├── homebrew/               # Homebrew management (macOS)
    │   ├── tasks/
    │   │   └── main.yml
    │   └── vars/
    │       └── main.yml
    ├── system/                 # System configuration
    │   ├── tasks/
    │   │   └── main.yml
    │   └── vars/
    │       ├── macos.yml
    │       └── linux.yml
    ├── shell/                  # Shell configuration
    │   ├── tasks/
    │   │   └── main.yml
    │   └── vars/
    │       └── main.yml
    └── apps/                   # Application-specific setup
        ├── tasks/
        │   └── main.yml
        └── files/
            ├── vscode/
            ├── cursor/
            └── ghostty/
```

---

## Migration Tasks

### Phase 1: Foundation Setup

- [ ] Create Ansible project structure
- [ ] Set up `ansible.cfg` configuration
- [ ] Create `requirements.yml` for collections
- [ ] Define inventory for localhost
- [ ] Create global variables file

### Phase 2: Dotfiles Role Development

- [ ] Create dotfiles role with symlink tasks
- [ ] Migrate all root dotfiles from Dotbot
- [ ] Migrate XDG config directories
- [ ] Migrate macOS app configs (VSCode, Cursor)
- [ ] Handle script directory symlinks
- [ ] Add Jinja2 templates where needed (e.g., .gitconfig)

### Phase 3: Package Management

- [ ] Create homebrew role for macOS
- [ ] Migrate formulae from `brew_packages.txt`
- [ ] Migrate casks from `brew_casks.txt`
- [ ] Add idempotent installation checks
- [ ] Add Homebrew caskroom verification

### Phase 4: System Configuration

- [ ] Create system role for macOS defaults
- [ ] Migrate all `mac-setup.sh` tasks to Ansible
- [ ] Add macOS version detection
- [ ] Add Linux system support (future-proofing)

### Phase 5: Shell & Application Configuration

- [ ] Create shell role (Zsh + Fish)
- [ ] Handle plugin managers (Zap, Fisher)
- [ ] Create apps role for editor configs
- [ ] Migrate VSCode and Cursor extensions

### Phase 6: Testing & Documentation

- [ ] Add `--check` mode validation
- [ ] Create README with usage instructions
- [ ] Document all variables
- [ ] Create bootstrap script for fresh installs
- [ ] Add CI/CD validation (GitHub Actions)

---

## Implementation Details

### Key Ansible Modules to Use

| Module | Purpose |
|--------|---------|
| `ansible.builtin.file` | Create directories, set permissions |
| `ansible.builtin.copy` | Copy static files |
| `ansible.builtin.template` | Jinja2 templating for dynamic content |
| `ansible.builtin.lineinfile` | Edit specific lines in files |
| `ansible.posix.synchronize` | Rsync-based file sync (dotfiles) |
| `ansible.builtin.git` | Clone repositories |
| `homebrew.homebrew.homebrew` | Homebrew package management |
| `community.general.macos_defaults` | macOS defaults commands |
| `ansible.builtin.command` | Execute shell commands |

### Platform Detection Strategy

```yaml
- name: Load platform-specific variables
  ansible.builtin.include_vars:
    file: "vars/{{ ansible_system | lower }}.yml"
  when: ansible_system in ['Linux', 'Darwin']
```

### Idempotent Symlink Pattern

```yaml
- name: Ensure dotfile symlink exists
  ansible.builtin.file:
    src: "{{ dotfiles_dir }}/{{ item }}"
    dest: "{{ ansible_env.HOME }}/{{ item }}"
    state: link
    force: yes
  loop: "{{ dotfiles_list }}"
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **Breaking existing setup** | Test in parallel, keep Dotbot as backup |
| **Homebrew differences** | Use `check_mode: yes` for dry-run |
| **macOS version compatibility** | Add version detection, conditional tasks |
| **Performance** | Use async for independent tasks |
| **Secret exposure** | Never commit secrets, use Ansible Vault |

---

## Success Criteria

1. All dotfiles symlinked correctly
2. All packages install idempotently
3. All macOS defaults applied
4. `--check` mode passes validation
5. Fresh install completes in < 30 minutes
6. No manual intervention required

---

## References

- [How I Manage my System and Dotfiles (with Ansible)](https://dev.to/shricodev/how-i-manage-my-system-and-dotfiles-with-ansible-8m1)
- [Using Ansible to Manage Dotfiles](https://www.bhoffpauir.com/blog/article/using-ansible-to-manage-dotfiles-sWPGKq)
- [Ansible Best Practices](https://docs.ansible.com/ansible/latest/tips_tricks/ansible_tips_tricks.html)
- [Ansible Sample Setup](https://docs.ansible.com/ansible/latest/tips_tricks/sample_setup.html)
- [Arch Linux Wiki - Dotfiles](https://wiki.archlinux.org/title/Dotfiles)

---

## Notes

- Keep Dotbot as backup during transition
- Use Git tags for version milestones
- Consider GitHub Actions for CI/CD validation
- Plan for Linux support (future)
