# Ansible Dotfiles Migration Plan (Revised)

## TL;DR

> **Quick Summary**: Create Ansible orchestration layer that runs Dotbot for symlinks while adding package management (Homebrew), system configuration (macOS defaults), shell setup, and editor extensions. Dotbot remains the source of truth for symlink definitions.
> 
> **Deliverables**:
> - Complete Ansible project structure in `ansible/` directory
> - 5 roles: dotbot (orchestrates ./install), homebrew, macos, shell, editors
> - Main playbook with tagged execution
> - Bootstrap script for fresh installs
> - Verification procedures for each role
> 
> **Estimated Effort**: Medium (7 tasks, ~3-4 hours implementation)
> **Parallel Execution**: YES - 2 waves
> **Critical Path**: Task 1 (Foundation) → Task 6 (Integration) → Task 7 (Verification)

---

## Context

### Original Request
Create Ansible orchestration for the macOS dotfiles repository at `/Users/devadathanmb/.mac-dots`. Ansible should coordinate all setup tasks while Dotbot continues to manage symlinks via `install.conf.yaml`.

### Key Clarification
**Ansible orchestrates Dotbot, NOT replaces it.**
- `install.conf.yaml` remains the source of truth for symlinks
- Ansible runs `./install` script to invoke Dotbot
- No direct symlink management in Ansible

### Interview Summary
**Key Discussions**:
- Project Location: Ansible in `ansible/` subdirectory (minimal disruption)
- Migration Strategy: Keep Dotbot as the symlink manager
- Test Strategy: Manual verification after each role (high thoroughness)
- Platform Scope: macOS-only for now (simpler implementation)
- Package Handling: Import existing brew_packages.txt and brew_casks.txt as-is

**Research Findings**:
- Dotbot is a git submodule at `dotbot/`
- `./install` script handles submodule sync and runs Dotbot
- `install.conf.yaml` defines all symlinks
- Collections needed: `community.general` (homebrew, osx_defaults)

### Special Notes
- **Exclude temp files** (already handled by Dotbot's install.conf.yaml)
- **Fish variables**: Managed by Dotbot symlink
- **Scripts directory**: Managed by Dotbot symlink to `~/.local/bin`
- **Dotbot submodule**: `./install` already handles `git submodule update`

---

## Work Objectives

### Core Objective
Create an Ansible orchestration layer that coordinates Dotbot (for symlinks) with Homebrew (packages), macOS defaults, shell setup, and editor extensions into a unified, idempotent setup process.

### Concrete Deliverables
1. `ansible/` directory with complete project structure
2. `ansible/roles/dotbot/` - runs Dotbot for symlink management
3. `ansible/roles/homebrew/` - manages formulae and casks
4. `ansible/roles/macos/` - manages macOS defaults
5. `ansible/roles/shell/` - manages Zap ZSH setup
6. `ansible/roles/editors/` - manages VSCode/Cursor extensions
7. `ansible/playbooks/main.yml` - orchestrates all roles
8. `ansible/bootstrap.sh` - entry point for fresh installs

### Definition of Done
- [x] `ansible-playbook ansible/playbooks/main.yml --check` runs without errors
- [x] Dotbot successfully creates all symlinks when invoked by Ansible
- [x] Homebrew packages install without errors
- [x] macOS defaults apply correctly (verify Finder, Dock settings)
- [x] Zap ZSH installs idempotently
- [x] VSCode/Cursor extensions install
- [x] Dotbot still works independently via `./install`

### Must Have
- Dotbot as the symlink manager (not Ansible)
- Ansible orchestrates the overall setup flow
- Idempotent operations (safe to run multiple times)
- Tagged execution (run only specific roles)
- Manual verification steps documented

### Must NOT Have (Guardrails)
- DO NOT create symlinks directly in Ansible (Dotbot handles this)
- DO NOT modify install.conf.yaml
- DO NOT duplicate Dotbot's symlink logic in Ansible
- DO NOT add Linux/multi-platform support in this migration
- DO NOT reorganize Homebrew packages into categories
- DO NOT use Ansible Vault (no secrets to encrypt)

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: NO (Ansible testing infra not present)
- **User wants tests**: Manual verification after each role
- **Framework**: Manual verification procedures

### Manual Verification Approach

Each TODO includes verification procedures that can be executed manually:

**Verification Pattern:**
1. Run playbook with `--check --diff` first (dry-run)
2. Run playbook for real
3. Execute verification commands
4. Confirm expected output

**Evidence to Capture:**
- Terminal output from verification commands
- Confirmation that Dotbot ran successfully
- Symlinks verified via `ls -la`

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - All Independent):
├── Task 1: Create Ansible project foundation
├── Task 2: Create dotbot role (orchestrates ./install)
├── Task 3: Create homebrew role
├── Task 4: Create macos role
├── Task 5: Create shell role
└── Task 5b: Create editors role

Wave 2 (After Wave 1 - Integration):
├── Task 6: Create main playbook and bootstrap script
└── Task 7: Final verification and documentation

Note: After Task 1 (foundation), Tasks 2-5b can all run in parallel
since they are independent roles with no interdependencies.
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 2,3,4,5,5b | None (foundation) |
| 2 | 1 | 6 | 3,4,5,5b |
| 3 | 1 | 6 | 2,4,5,5b |
| 4 | 1 | 6 | 2,3,5,5b |
| 5 | 1 | 6 | 2,3,4,5b |
| 5b | 1 | 6 | 2,3,4,5 |
| 6 | 2,3,4,5,5b | 7 | None |
| 7 | 6 | None | None (final) |

### Agent Dispatch Summary

| Wave | Tasks | Recommended Approach |
|------|-------|---------------------|
| 1 | 1, then 2-5b in parallel | Task 1 first, then all roles in parallel |
| 2 | 6, 7 | Sequential - Integration then verification |

---

## TODOs

### Task 1: Create Ansible Project Foundation

**What to do**:
- Create `ansible/` directory structure
- Create `ansible/ansible.cfg` with local configuration
- Create `ansible/requirements.yml` with community.general collection
- Create `ansible/inventory/localhost.yml` for local execution
- Create `ansible/group_vars/all.yml` with shared variables (dotfiles_repo path)
- Install required collections: `ansible-galaxy collection install -r requirements.yml`

**Must NOT do**:
- Do not create roles yet (separate tasks)
- Do not modify any existing files outside ansible/

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: Simple file creation, no complex logic
- **Skills**: None required
  - Standard Ansible knowledge sufficient

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Wave 1 (foundation first)
- **Blocks**: Tasks 2, 3, 4, 5, 5b
- **Blocked By**: None (can start immediately)

**References**:

**Pattern References**:
- `.gitmodules:1-5` - Dotbot submodule configuration
- `install:1-16` - Current Dotbot install script

**Documentation References**:
- Ansible Best Practices: https://docs.ansible.com/ansible/latest/tips_tricks/ansible_tips_tricks.html
- Role Directory Structure: https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html

**File Structure to Create**:
```
ansible/
├── ansible.cfg
├── requirements.yml
├── inventory/
│   └── localhost.yml
├── group_vars/
│   └── all.yml
├── playbooks/
│   └── (empty - created in Task 6)
└── roles/
    └── (empty - created in Tasks 2-5b)
```

**Acceptance Criteria**:

**Automated Verification**:
```bash
# Verify directory structure
ls -la ansible/
# Expected: ansible.cfg, requirements.yml, inventory/, group_vars/, playbooks/, roles/

# Verify ansible.cfg
cat ansible/ansible.cfg
# Expected: Contains [defaults] section with inventory path

# Verify requirements.yml
cat ansible/requirements.yml
# Expected: Contains community.general collection

# Verify inventory
cat ansible/inventory/localhost.yml
# Expected: Contains localhost with ansible_connection=local

# Verify group_vars
cat ansible/group_vars/all.yml
# Expected: Contains dotfiles_repo variable pointing to repo root

# Install collections and verify
cd ansible && ansible-galaxy collection install -r requirements.yml
ansible-galaxy collection list | grep community.general
# Expected: community.general listed
```

**Commit**: YES
- Message: `feat(ansible): add project foundation structure`
- Files: `ansible/ansible.cfg`, `ansible/requirements.yml`, `ansible/inventory/localhost.yml`, `ansible/group_vars/all.yml`
- Pre-commit: `ansible --version` (verify ansible works)

---

### Task 2: Create Dotbot Role (Orchestrates Symlinks)

**What to do**:
- Create `ansible/roles/dotbot/` directory structure
- Create `tasks/main.yml` with:
  1. Ensure git submodules are initialized (git submodule update --init --recursive)
  2. Run Dotbot install script (./install)
- Use `ansible.builtin.command` module
- Set working directory to repo root
- Make idempotent by checking if symlinks already exist

**Must NOT do**:
- Do NOT create symlinks directly - Dotbot handles this
- Do NOT modify install.conf.yaml
- Do NOT parse or duplicate Dotbot's logic

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: Very simple role - just runs existing script
- **Skills**: None required

**Parallelization**:
- **Can Run In Parallel**: YES (after Task 1)
- **Parallel Group**: Wave 1 (with Tasks 3,4,5,5b)
- **Blocks**: Task 6
- **Blocked By**: Task 1

**References**:

**Pattern References**:
- `install:1-16` - The script this role will execute
- `.gitmodules:1-5` - Submodule configuration
- `install.conf.yaml:1-44` - Dotbot config (source of truth for symlinks)

**Key Implementation Details**:
```yaml
# tasks/main.yml structure
- name: Ensure git submodules are initialized
  ansible.builtin.command:
    cmd: git submodule update --init --recursive
    chdir: "{{ dotfiles_repo }}"
  register: submodule_result
  changed_when: submodule_result.stdout != ''

- name: Run Dotbot to create symlinks
  ansible.builtin.command:
    cmd: ./install
    chdir: "{{ dotfiles_repo }}"
  register: dotbot_result
  changed_when: "'Link exists' not in dotbot_result.stdout"
```

**Acceptance Criteria**:

**Automated Verification**:
```bash
# Dry run (note: command module doesn't support check mode well)
cd ansible && ansible-playbook playbooks/dotbot.yml --check --diff
# Expected: Shows command tasks

# Run for real
cd ansible && ansible-playbook playbooks/dotbot.yml

# Verify symlinks were created by Dotbot
ls -la ~/.tmux.conf ~/.vimrc ~/.zshrc ~/.gitconfig
# Expected: All show -> pointing to repo files

# Verify config directories
ls -la ~/.config/fish ~/.config/ghostty ~/.config/zsh
# Expected: All show -> pointing to configs/ directories

# Verify Application Support
ls -la ~/Library/Application\ Support/Code/User/settings.json
# Expected: Symlink to repo configs/

# Verify Dotbot still works independently
./install --dry-run
# Expected: No errors, "Link exists" for all symlinks
```

**Commit**: YES
- Message: `feat(ansible): add dotbot role to orchestrate symlinks`
- Files: `ansible/roles/dotbot/tasks/main.yml`
- Pre-commit: `./install --dry-run` (verify Dotbot works)

---

### Task 3: Create Homebrew Role

**What to do**:
- Create `ansible/roles/homebrew/` directory structure
- Create `tasks/main.yml` with:
  1. Ensure Homebrew is installed (check, install if missing)
  2. Update Homebrew
  3. Install formulae from list
  4. Install casks from list
- Create `vars/main.yml` with package lists (read from existing files)
- Use `community.general.homebrew` and `community.general.homebrew_cask`
- Handle installation failures gracefully (some packages may not exist)

**Must NOT do**:
- Do not reorganize or categorize packages
- Do not remove any packages from existing lists
- Do not run `brew upgrade` automatically (could break things)

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: Uses standard Homebrew modules, clear pattern
- **Skills**: None required

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Tasks 2,4,5,5b)
- **Blocks**: Task 6
- **Blocked By**: Task 1

**References**:

**Pattern References**:
- `homebrew/brew-setup.sh:1-65` - Current Homebrew setup script
- `homebrew/brew_packages.txt` - 286 formulae
- `homebrew/brew_casks.txt` - 41 casks

**Documentation References**:
- community.general.homebrew: https://docs.ansible.com/ansible/latest/collections/community/general/homebrew_module.html
- community.general.homebrew_cask: https://docs.ansible.com/ansible/latest/collections/community/general/homebrew_cask_module.html

**Acceptance Criteria**:

**Automated Verification**:
```bash
# Dry run
cd ansible && ansible-playbook playbooks/packages.yml --check --diff

# Verify Homebrew is detected
which brew
# Expected: /opt/homebrew/bin/brew or /usr/local/bin/brew

# Run playbook (will take time for 286 packages)
cd ansible && ansible-playbook playbooks/packages.yml

# Verify some key packages
brew list | grep -E "^(fzf|bat|eza|git|tmux)$"
# Expected: All listed

# Verify casks
brew list --cask | grep -E "^(ghostty|cursor|visual-studio-code)$"
# Expected: All listed
```

**Commit**: YES
- Message: `feat(ansible): add homebrew role for package management`
- Files: `ansible/roles/homebrew/tasks/main.yml`, `ansible/roles/homebrew/vars/main.yml`
- Pre-commit: `ansible-playbook ansible/playbooks/packages.yml --check`

---

### Task 4: Create macOS Role

**What to do**:
- Create `ansible/roles/macos/` directory structure
- Create `tasks/main.yml` with osx_defaults tasks
- Convert all `defaults write` commands from `mac/mac-setup.sh` to `community.general.osx_defaults`
- Organize by category (trackpad, finder, keyboard, dock, etc.)
- Create handlers for app restarts (Finder, Dock, SystemUIServer)
- Create Screenshots directory if needed

**Must NOT do**:
- Do not include osascript commands (System Preferences quit)
- Do not include commented-out settings
- Do not add new settings not in mac-setup.sh

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: Repetitive conversion, clear pattern
- **Skills**: None required

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Tasks 2,3,5,5b)
- **Blocks**: Task 6
- **Blocked By**: Task 1

**References**:

**Pattern References**:
- `mac/mac-setup.sh:1-397` - All defaults commands to convert

**Key Settings Categories** (from mac-setup.sh):
- Trackpad (lines 30-43): tap to click, right-click, three-finger drag
- Finder (lines 48-82): show extensions, path bar, list view
- Keyboard (lines 88-117): fast repeat, disable autocorrect
- Save Dialogs (lines 122-133): expand by default
- Dock (lines 138-182): auto-hide, static-only
- Hot Corners (lines 188-213): disabled top-right
- Terminal (lines 218-225): UTF-8
- System UI (lines 230-250): battery %, 24-hour time
- Screenshots (lines 254-271): PNG, location, no shadow
- Security (lines 276-284): immediate password
- Safari (lines 300-328): dev menu, privacy
- TextEdit (lines 334-346): plain text
- Activity Monitor (lines 350-361): show all, CPU sort
- App Store (lines 366-373): disable auto-download

**Documentation References**:
- community.general.osx_defaults: https://docs.ansible.com/ansible/latest/collections/community/general/osx_defaults_module.html

**Acceptance Criteria**:

**Automated Verification**:
```bash
# Dry run
cd ansible && ansible-playbook playbooks/macos.yml --check --diff

# Run playbook
cd ansible && ansible-playbook playbooks/macos.yml

# Verify key settings
defaults read com.apple.finder ShowPathbar
# Expected: 1

defaults read com.apple.dock autohide
# Expected: 1

defaults read NSGlobalDomain KeyRepeat
# Expected: 1

defaults read com.apple.screencapture location
# Expected: /Users/devadathanmb/Pictures/Screenshots

# Verify Screenshot directory exists
ls -la ~/Pictures/Screenshots
# Expected: Directory exists
```

**Commit**: YES
- Message: `feat(ansible): add macos role for system defaults`
- Files: `ansible/roles/macos/tasks/main.yml`, `ansible/roles/macos/handlers/main.yml`
- Pre-commit: `ansible-playbook ansible/playbooks/macos.yml --check`

---

### Task 5: Create Shell Role

**What to do**:
- Create `ansible/roles/shell/` directory structure
- Create `tasks/main.yml` with:
  1. Check if Zap ZSH is installed (`~/.local/share/zap`)
  2. Install Zap ZSH if missing (curl command)
- Use `ansible.builtin.command` with `creates:` for idempotency

**Must NOT do**:
- Do not modify .zshrc (handled by Dotbot symlink)
- Do not install additional shell plugins (Zap handles that via .zshrc)

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: Simple shell command, single task
- **Skills**: None required

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Tasks 2,3,4,5b)
- **Blocks**: Task 6
- **Blocked By**: Task 1

**References**:

**Pattern References**:
- `configs/zsh/setup-zap-zsh.sh:1-9` - Current Zap installation script

**Acceptance Criteria**:

**Automated Verification**:
```bash
# Dry run
cd ansible && ansible-playbook playbooks/shell.yml --check --diff

# Run playbook
cd ansible && ansible-playbook playbooks/shell.yml

# Verify Zap is installed
ls -la ~/.local/share/zap
# Expected: Directory exists with zap files

# Verify idempotency (run again)
cd ansible && ansible-playbook playbooks/shell.yml
# Expected: "ok" status, not "changed"
```

**Commit**: YES
- Message: `feat(ansible): add shell role for zap zsh setup`
- Files: `ansible/roles/shell/tasks/main.yml`
- Pre-commit: `ansible-playbook ansible/playbooks/shell.yml --check`

---

### Task 5b: Create Editors Role

**What to do**:
- Create `ansible/roles/editors/` directory structure
- Create `tasks/main.yml` with:
  1. Check if `code` command exists
  2. Install VSCode extensions from `configs/vscode/extensions.txt` (55 extensions)
  3. Check if `cursor` command exists
  4. Install Cursor extensions from `configs/cursor/extensions.txt` (39 extensions)
- Use `ansible.builtin.command` with loop over extension lists
- Handle failures gracefully (some extensions may be deprecated)

**Must NOT do**:
- Do not modify extension lists
- Do not sync settings (handled by Dotbot symlinks)

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: Shell commands with loops, straightforward
- **Skills**: None required

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Tasks 2,3,4,5)
- **Blocks**: Task 6
- **Blocked By**: Task 1

**References**:

**Pattern References**:
- `configs/vscode/install-extensions.sh:1-70` - VSCode extension installer
- `configs/cursor/install-extensions.sh:1-70` - Cursor extension installer
- `configs/vscode/extensions.txt` - 55 VSCode extensions
- `configs/cursor/extensions.txt` - 39 Cursor extensions

**Acceptance Criteria**:

**Automated Verification**:
```bash
# Dry run
cd ansible && ansible-playbook playbooks/editors.yml --check --diff

# Run playbook (takes time for 94 total extensions)
cd ansible && ansible-playbook playbooks/editors.yml

# Verify VSCode extensions
code --list-extensions | wc -l
# Expected: 55 or more

# Verify Cursor extensions
cursor --list-extensions | wc -l
# Expected: 39 or more

# Verify specific extensions
code --list-extensions | grep vscodevim.vim
cursor --list-extensions | grep vscodevim.vim
# Expected: Both show vscodevim.vim
```

**Commit**: YES
- Message: `feat(ansible): add editors role for vscode/cursor extensions`
- Files: `ansible/roles/editors/tasks/main.yml`
- Pre-commit: `ansible-playbook ansible/playbooks/editors.yml --check`

---

### Task 6: Create Main Playbook and Bootstrap Script

**What to do**:
- Create `ansible/playbooks/main.yml` - orchestrates all roles with tags
- Create `ansible/playbooks/dotbot.yml` - just dotbot role
- Create `ansible/playbooks/packages.yml` - just homebrew role
- Create `ansible/playbooks/macos.yml` - just macos role
- Create `ansible/playbooks/shell.yml` - just shell role
- Create `ansible/playbooks/editors.yml` - just editors role
- Create `ansible/bootstrap.sh` - entry point for fresh installs:
  1. Check/install Homebrew
  2. Install Ansible via brew
  3. Install Ansible collections
  4. Run main playbook
- Add proper tags for selective execution
- Ensure correct role order in main.yml: dotbot first (symlinks needed for configs)

**Must NOT do**:
- Do not remove or modify existing bootstrap-mac.sh
- Do not run playbooks automatically (just create them)

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: File creation, standard playbook structure
- **Skills**: None required

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Wave 2 (sequential)
- **Blocks**: Task 7
- **Blocked By**: Tasks 2,3,4,5,5b

**References**:

**Pattern References**:
- `bootstrap-mac.sh:1-19` - Current bootstrap process order
- All role tasks created in Tasks 2-5b

**Playbook Execution Order** (main.yml):
1. `dotbot` - Create symlinks first (configs needed by other tools)
2. `homebrew` - Install packages
3. `macos` - Configure system defaults
4. `shell` - Setup Zap ZSH
5. `editors` - Install extensions

**Acceptance Criteria**:

**Automated Verification**:
```bash
# Verify all playbooks exist
ls -la ansible/playbooks/
# Expected: main.yml, dotbot.yml, packages.yml, macos.yml, shell.yml, editors.yml

# Verify bootstrap.sh exists and is executable
ls -la ansible/bootstrap.sh
# Expected: -rwxr-xr-x

# Dry run main playbook
cd ansible && ansible-playbook playbooks/main.yml --check --diff

# Test tag execution
cd ansible && ansible-playbook playbooks/main.yml --tags dotbot --check
# Expected: Only dotbot tasks shown

# Test selective playbook
cd ansible && ansible-playbook playbooks/packages.yml --check
# Expected: Only homebrew tasks shown
```

**Commit**: YES
- Message: `feat(ansible): add main playbook and bootstrap script`
- Files: `ansible/playbooks/*.yml`, `ansible/bootstrap.sh`
- Pre-commit: `ansible-playbook ansible/playbooks/main.yml --check`

---

### Task 7: Final Verification and Documentation

**What to do**:
- Run complete Ansible playbook on current system
- Verify Dotbot ran successfully (symlinks created)
- Verify Dotbot still works independently via `./install`
- Update repo README.md with Ansible usage section
- Document both usage methods (Ansible and direct Dotbot)

**Must NOT do**:
- Do not delete Dotbot or install.conf.yaml
- Do not commit unrelated changes

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: Verification and documentation
- **Skills**: None required

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Wave 2 (final)
- **Blocks**: None
- **Blocked By**: Task 6

**References**:

**Pattern References**:
- `README.md:1-25` - Current README to update
- `install.conf.yaml:1-44` - Dotbot config (source of truth)

**Acceptance Criteria**:

**Automated Verification**:
```bash
# Full Ansible run
cd ansible && ansible-playbook playbooks/main.yml

# Verify Dotbot created symlinks (via Ansible)
for f in .tmux.conf .vimrc .gitconfig .zshrc .zprofile .p10k.zsh .ideavimrc .curlrc .psqlrc .wgetrc; do
  readlink ~/$f
done
# Expected: All point to repo files

# Verify config directories
for d in fish gh zsh cvim ghostty atuin pgcli htop btop mpv zed; do
  readlink ~/.config/$d
done
# Expected: All point to configs/ directories

# Verify Dotbot still works independently
./install --dry-run
# Expected: No errors, "Link exists" for all symlinks

# Verify README has Ansible section
grep -q "Ansible" README.md
# Expected: Match found

# Verify README still documents Dotbot
grep -q "Dotbot" README.md
# Expected: Match found
```

**Commit**: YES
- Message: `docs: add Ansible usage documentation to README`
- Files: `README.md`
- Pre-commit: None

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `feat(ansible): add project foundation structure` | ansible.cfg, requirements.yml, inventory/, group_vars/ | Collection install works |
| 2 | `feat(ansible): add dotbot role to orchestrate symlinks` | roles/dotbot/ | Dotbot runs successfully |
| 3 | `feat(ansible): add homebrew role for package management` | roles/homebrew/ | Packages install |
| 4 | `feat(ansible): add macos role for system defaults` | roles/macos/ | Defaults applied |
| 5 | `feat(ansible): add shell role for zap zsh setup` | roles/shell/ | Zap installed |
| 5b | `feat(ansible): add editors role for vscode/cursor extensions` | roles/editors/ | Extensions installed |
| 6 | `feat(ansible): add main playbook and bootstrap script` | playbooks/, bootstrap.sh | Full playbook runs |
| 7 | `docs: add Ansible usage documentation to README` | README.md | README updated |

---

## Success Criteria

### Verification Commands
```bash
# Full system verification
cd ansible && ansible-playbook playbooks/main.yml --check --diff

# Individual role verification
ansible-playbook playbooks/dotbot.yml --check
ansible-playbook playbooks/packages.yml --check
ansible-playbook playbooks/macos.yml --check
ansible-playbook playbooks/shell.yml --check
ansible-playbook playbooks/editors.yml --check

# Dotbot still works independently
./install --dry-run
```

### Final Checklist
- [x] Dotbot runs successfully via Ansible and creates all symlinks
- [x] Dotbot still works independently via `./install`
- [x] Homebrew packages install without errors
- [x] macOS defaults apply correctly
- [x] Zap ZSH installs idempotently
- [x] VSCode/Cursor extensions install
- [x] README documents both Ansible and Dotbot usage
- [x] All playbooks pass `--check` mode

---

## Rollback Plan

If Ansible setup has issues:

1. **Dotbot is always available**: Run `./install` directly to manage symlinks
2. **Remove Ansible directory**: `rm -rf ansible/` if needed
3. **Existing scripts unchanged**: `bootstrap-mac.sh` still works
4. **macOS defaults reversible**: Run with opposite values or use Time Machine

Ansible is purely additive - it doesn't modify or replace any existing functionality.

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    Ansible Orchestration                    │
│                  (ansible/playbooks/main.yml)               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐ │
│  │  dotbot  │  │ homebrew │  │  macos   │  │shell/editors│ │
│  │   role   │  │   role   │  │   role   │  │    roles    │ │
│  └────┬─────┘  └──────────┘  └──────────┘  └─────────────┘ │
│       │                                                     │
│       ▼                                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                    ./install                          │  │
│  │              (existing Dotbot script)                 │  │
│  └────┬─────────────────────────────────────────────────┘  │
│       │                                                     │
│       ▼                                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              install.conf.yaml                        │  │
│  │        (Dotbot config - source of truth)              │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Key: Ansible orchestrates Dotbot. Dotbot manages symlinks.
     install.conf.yaml remains the single source of truth.
```
