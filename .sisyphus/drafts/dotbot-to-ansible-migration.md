# Draft: Dotbot to Ansible Migration

## Requirements (confirmed)

### Current Dotbot Configuration (from install.conf.yaml)
**Root Dotfiles (direct symlinks to ~)**:
- `.tmux.conf` → .tmux.conf
- `.vimrc` → .vimrc
- `.ideavimrc` → .ideavimrc
- `.curlrc` → .curlrc
- `.psqlrc` → .psqlrc
- `.wgetrc` → .wgetrc
- `.p10k.zsh` → .p10k.zsh
- `.gitconfig` → .gitconfig
- `.zshrc` → .zshrc
- `.zprofile` → .zprofile

**Config Directories (~/.config/)**:
- `~/.config/fish` → .configs/fish (note: typo in config, should be configs/)
- `~/.config/gh` → configs/gh
- `~/.config/zsh` → configs/zsh
- `~/.config/cvim` → configs/cvim
- `~/.config/ghostty` → configs/ghostty
- `~/.config/atuin` → configs/atuin
- `~/.config/pgcli` → configs/pgcli
- `~/.config/htop` → configs/htop
- `~/.config/btop` → configs/btop
- `~/.config/mpv` → configs/mpv
- `~/.config/zed` → configs/zed

**Scripts Directory**:
- `~/.local/bin` → scripts/* (glob pattern)

**macOS Application Support**:
- VSCode settings.json → configs/vscode/settings.json
- VSCode keybindings.json → configs/vscode/keybindings.json
- Cursor settings.json → configs/cursor/settings.json
- Cursor keybindings.json → configs/cursor/keybindings.json

**Disabled (commented out)**:
- iTerm2 plist

### Bootstrap Process (bootstrap-mac.sh)
1. Source homebrew/brew-setup.sh (install Homebrew + packages)
2. Source mac/mac-setup.sh (configure macOS defaults)
3. Source configs/zsh/setup-zap-zsh.sh (install Zap for Zsh)
4. Source configs/cursor/install-extensions.sh
5. Source configs/vscode/install-extensions.sh

### Homebrew Packages
- **Formulae**: 286 packages
- **Casks**: 41 GUI applications

### macOS Defaults (mac/mac-setup.sh - 397 lines)
Categories:
- Trackpad: tap to click, right-click, three-finger drag
- Finder: show extensions, path in title, hide desktop icons, list view
- Keyboard: fast repeat, disable autocorrect/smart quotes
- Save Dialogs: expand by default
- Dock: auto-hide, static-only, scale effect
- Hot Corners: top-right disabled
- Terminal: UTF-8 encoding
- System UI: battery %, 24-hour time
- Screenshots: PNG, ~/Pictures/Screenshots, no shadow
- Security: immediate password on sleep
- Safari: disable search suggestions, enable dev menu
- TextEdit: plain text mode
- Activity Monitor: show all, sort by CPU
- App Store: disable auto-download

### Sensitive Files
- `.gitconfig`: Contains user.name and user.email - NOT tokens (verified)
- No API keys or secrets detected in root dotfiles

## Technical Decisions

### Ansible Project Structure (Recommended)
```
ansible/
├── ansible.cfg
├── requirements.yml
├── inventory/
│   └── localhost.yml
├── group_vars/
│   └── all.yml
├── playbooks/
│   ├── main.yml          # Entry point
│   ├── dotfiles.yml      # Just dotfiles
│   ├── packages.yml      # Just packages
│   └── macos.yml         # Just macOS settings
└── roles/
    ├── dotfiles/
    │   ├── tasks/main.yml
    │   ├── vars/main.yml
    │   └── files/        # (reference to repo root dotfiles)
    ├── homebrew/
    │   ├── tasks/main.yml
    │   └── vars/main.yml
    ├── macos/
    │   ├── tasks/main.yml
    │   └── vars/main.yml
    ├── shell/
    │   └── tasks/main.yml
    └── editors/
        └── tasks/main.yml
```

### Key Module Choices
1. **Symlinks**: `ansible.builtin.file` with `state: link`
2. **Homebrew**: `community.general.homebrew` and `community.general.homebrew_cask`
3. **macOS defaults**: `community.general.osx_defaults` module
4. **Shell commands**: `ansible.builtin.command` for zap-zsh and extensions

### Idempotency Strategy
- Use `creates:` parameter for shell/command modules
- Use `state: present` for package installation
- Symlinks naturally idempotent with `force: yes`

## Research Findings

### From Previous Analysis (ANSIBLE_MIGRATION_ANALYSIS.md)
- Role-based architecture recommended
- Platform detection via `ansible_system`, `ansible_os_family`
- Collections needed: `community.general`, `ansible.posix`

## Confirmed Decisions (from user)

1. **Project Location**: Option A - Inside repo as `ansible/` subdirectory
   - Minimal disruption, single git history, can roll back
2. **Migration Strategy**: Keep Dotbot as fallback during transition
   - Both systems work in parallel until Ansible is validated
3. **Test Strategy**: Manual verification after each role
   - Medium effort, high thoroughness
4. **Platform Scope**: macOS-only for now
   - Simpler implementation, can add Linux later
5. **Homebrew Packages**: Import existing lists as-is
   - Use brew_packages.txt and brew_casks.txt directly

## CRITICAL CLARIFICATION (from user)

**Ansible should ORCHESTRATE Dotbot, NOT replace it.**

- Dotbot remains the source of truth for symlink definitions (install.conf.yaml)
- Ansible runs Dotbot as part of the playbook
- NO direct symlink management in Ansible
- The "dotfiles" role becomes "dotbot" role - just runs ./install

## Special Notes (from user)

- `configs/fish/fish_variables` has modified state - handle carefully
- EXCLUDE temporary/backup files:
  - `configs/fish/fish_variablesUkIPWXUWtA`
  - `configs/ghostty/config.aa707223.bak`
- Focus on clean, idempotent Ansible setup
- Preserve exact symlink structure from install.conf.yaml

## Scope Boundaries

### INCLUDE
- All current Dotbot symlinks
- Homebrew formulae and casks
- macOS defaults configuration
- Shell setup (Zap ZSH)
- VSCode/Cursor extension installation
- Proper Ansible project structure

### EXCLUDE
- Multi-platform support (macOS only for now)
- Ansible Vault setup (no secrets to encrypt currently)
- Cloud/remote execution (localhost only)
- iTerm2 plist (commented out in Dotbot)
