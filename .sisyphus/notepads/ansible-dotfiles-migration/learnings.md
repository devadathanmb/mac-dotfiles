# Ansible Dotfiles Migration - Learnings

## Task 1: Foundation Complete

### What worked
- Simple file creation approach for ansible.cfg, requirements.yml, inventory/, group_vars/
- community.general collection installed successfully via ansible-galaxy
- All files minimal but functional

### File contents
- ansible.cfg: `[defaults]` section with `inventory = inventory/localhost.yml` and `host_key_checking = False`
- requirements.yml: Single collection `community.general`
- inventory/localhost.yml: localhost with `ansible_connection: local`
- group_vars/all.yml: `dotfiles_repo: /Users/devadathanmb/.mac-dots`

### Issues encountered
- Subagent accidentally modified `configs/fish/fish_variables` (Fish shell state)
- Resolved by running `git restore configs/fish/fish_variables`

### Next tasks
- Task 2: Dotbot role (orchestrates ./install)
- Task 3: Homebrew role (packages)
- Task 4: macOS role (defaults)
- Task 5: Shell role (Zap ZSH)
- Task 5b: Editors role (extensions)

## Task 2: Dotbot Role Complete

### What worked
- Created `ansible/roles/dotbot/tasks/main.yml` with two tasks:
  1. Git submodule initialization (idempotent via changed_when)
  2. Dotbot execution (idempotent via "Link exists" detection)
- Used `ansible.builtin.command` module as required
- Set `chdir: "{{ dotfiles_repo }}"` for working directory
- Registered output for both tasks
- Idempotency detection:
  - Submodules: Check for "Submodule" in stdout/stderr
  - Dotbot: Check for "Link exists" in stdout (no changes = all links exist)

### File structure
- `ansible/roles/dotbot/tasks/main.yml` - Main task orchestration

### Key insights
- The `./install` script already handles submodule sync internally (line 12 of install script)
- But we still need explicit submodule task for idempotency detection
- Dotbot outputs "Link exists" when symlinks are already created (idempotent)
- Using `command` module prevents shell interpretation (safer)

### Next tasks
- Task 3: Homebrew role (packages)
- Task 4: macOS role (defaults)
- Task 5: Shell role (Zap ZSH)
- Task 5b: Editors role (extensions)

## Task 5: Shell Role (Zap ZSH) Complete

### What worked
- Created `ansible/roles/shell/tasks/main.yml` with two tasks:
  1. Check if Zap ZSH is installed using `ansible.builtin.stat`
  2. Install Zap ZSH if missing using `ansible.builtin.command`
- Used `ansible_user_dir` variable for home directory expansion
- Idempotency via `stat` check: Only installs if `~/.local/share/zap` doesn't exist
- Installation command matches original shell script exactly

### File structure
- `ansible/roles/shell/tasks/main.yml` - Zap ZSH installation tasks

### Key insights
- `ansible.builtin.stat` is the idempotent way to check directory existence
- `when: not zap_installed.stat.exists` prevents re-running installation
- Using `zsh -c` with piped curl matches the original setup-zap-zsh.sh approach
- `changed_when: true` ensures Ansible reports the change when installation occurs

### Next tasks
- Task 3: Homebrew role (packages)
- Task 4: macOS role (defaults)
- Task 5b: Editors role (extensions)

## Task 4: macOS Role Complete

### What worked
- Created `ansible/roles/macos/tasks/main.yml` with 66 osx_defaults tasks
- Converted all 397 lines of bash defaults commands to Ansible tasks
- Organized into 13 categories: trackpad, finder, keyboard, save dialogs, dock, hot corners, terminal, system ui, screenshots, security, performance, safari/webkit, textedit, activity monitor, app store
- Used `community.general.osx_defaults` module for all settings
- Proper type conversion: bool, int, float, string, array
- Added handlers for Finder, Dock, SystemUIServer restarts
- Used `notify` directives on Dock and SystemUIServer tasks

### File structure
- `ansible/roles/macos/tasks/main.yml` - 565 lines, 66 tasks
- `ansible/roles/macos/handlers/main.yml` - 17 lines, 3 handlers

### Key conversions
- `defaults write com.apple.AppleMultitouchTrackpad Clicking -bool true` → osx_defaults with domain, key, type, value
- `-currentHost` flag → `host: currentHost` parameter
- `-g` (global) → `domain: NSGlobalDomain`
- Array values (Terminal StringEncodings) → `type: array` with list value
- Float values (Dock animations) → `type: float`
- File operations (~/Library, Screenshots dir) → `ansible.builtin.file` module
- chflags command → `ansible.builtin.command` with `changed_when: false`

### Excluded items (as required)
- osascript commands (System Preferences quit)
- Commented-out settings (Dock tilesize, autohide-delay, persistent-apps)
- Commented-out hot corners (top left Mission Control)

### Handlers strategy
- Dock tasks notify "Restart Dock" handler
- SystemUIServer tasks notify "Restart SystemUIServer" handler
- Finder tasks would notify "Restart Finder" (no Finder tasks in this role)
- All handlers use `killall` command with `changed_when: false`

### Next tasks
- Task 5: Shell role (Zap ZSH)
- Task 5b: Editors role (extensions)

## Task 3: Homebrew Role Complete

### What worked
- Created `ansible/roles/homebrew/tasks/main.yml` with 4 main tasks
- Created `ansible/roles/homebrew/vars/main.yml` with 286 formulae and 41 casks
- Used `community.general.homebrew` and `community.general.homebrew_cask` modules
- Homebrew installation check (creates if not exists)
- Update Homebrew task
- Install formulae (with `ignore_errors: true` for graceful failure handling)
- Install casks (with `ignore_errors: true`)

### File structure
- `ansible/roles/homebrew/tasks/main.yml` - 5 tasks
- `ansible/roles/homebrew/vars/main.yml` - 286 formulae + 41 casks

### Key decisions
- Used `ignore_errors: true` because some packages may not exist or fail to install
- Not using `state: latest` to avoid automatic upgrades (could break things)
- Package lists imported as-is from existing txt files

## Task 5b: Editors Role Complete

### What worked
- Created `ansible/roles/editors/tasks/main.yml` with extension installation tasks
- Created `ansible/roles/editors/vars/main.yml` with 55 VSCode + 39 Cursor extensions
- Used `ansible.builtin.command` with `--install-extension` for each editor
- Check for editor availability before installing extensions
- Loop over extension lists for both VSCode and Cursor

### File structure
- `ansible/roles/editors/tasks/main.yml` - 5 tasks
- `ansible/roles/editors/vars/main.yml` - 55 VSCode + 39 Cursor extensions

### Key decisions
- Check if `code`/`cursor` commands exist before installing extensions
- Used `ignore_errors: true` for deprecated or unavailable extensions
- Changed detection based on output containing "Extension"

## Task 6: Playbooks Complete

### What worked
- Created `ansible/playbooks/main.yml` - Main orchestrating playbook with all roles
- Created individual playbooks: dotbot.yml, packages.yml, macos.yml, shell.yml, editors.yml
- Added proper tags: [dotbot, symlinks], [homebrew, packages], [macos, defaults], [shell, zsh], [editors, vscode, cursor]
- Created `ansible/bootstrap.sh` - Fresh install entry point script

### File structure
- `ansible/playbooks/main.yml` - Main playbook with all roles in order
- `ansible/playbooks/dotbot.yml` - Dotbot only
- `ansible/playbooks/packages.yml` - Homebrew only
- `ansible/playbooks/macos.yml` - macOS defaults only
- `ansible/playbooks/shell.yml` - Shell setup only
- `ansible/playbooks/editors.yml` - Editors only
- `ansible/bootstrap.sh` - Bootstrap script for fresh installs

### Playbook order
1. dotbot (symlinks first - configs needed by other tools)
2. homebrew (packages)
3. macos (system defaults)
4. shell (Zap ZSH)
5. editors (extensions)

### Bootstrap script
- Checks for Homebrew, installs if missing
- Checks for Ansible, installs via brew if missing
- Installs Ansible collections
- Runs main playbook with any passed arguments
- Supports tags: `--tags dotbot`, `--tags homebrew`, etc.

## Task 7: Verification Complete

### Verification performed
- Ran `ansible-playbook playbooks/main.yml --check` - SUCCESS
- All 5 roles load correctly:
  - dotbot: submodule init + ./install
  - homebrew: 286 formulae + 41 casks
  - macos: 66 osx_defaults tasks
  - shell: Zap ZSH installation
  - editors: 55 VSCode + 39 Cursor extensions
- Tagged execution works: `--tags dotbot`, `--tags homebrew`, etc.
- README updated with Ansible documentation

### Issues fixed
1. `configs/fish/fish_variables` accidentally modified - restored
2. `ansible.cfg` missing `roles_path` - added
3. `dotfiles_repo` variable not available in roles - added `roles/dotbot/defaults/main.yml`
4. Homebrew `length` filter on boolean `failed` - removed debug tasks
5. Fixed typo: `ipedezas` → `ipedezas` in extensions

### Final commit
- README updated with Ansible usage documentation
- Both Ansible and Dotbot documented as options

## Summary

All 7 tasks complete:
- [x] Task 1: Ansible project foundation
- [x] Task 2: Dotbot role (orchestrates ./install)
- [x] Task 3: Homebrew role (packages)
- [x] Task 4: macOS role (defaults)
- [x] Task 5: Shell role (Zap ZSH)
- [x] Task 5b: Editors role (extensions)
- [x] Task 6: Main playbook and bootstrap script
- [x] Task 7: Final verification and documentation
