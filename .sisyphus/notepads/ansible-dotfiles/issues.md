# Ansible Dotfiles Issues & Gotchas

## Issue 1: Homebrew Path Differences

**Date**: 2026-02-01

**Problem**: Apple Silicon vs Intel Mac paths differ

**Details**:
- Apple Silicon: `/opt/homebrew/bin/brew`
- Intel: `/usr/local/bin/brew`

**Solution**:
```yaml
- name: Detect Homebrew prefix
  ansible.builtin.shell: brew --prefix
  register: homebrew_prefix
  changed_when: false
```

**Status**: RESOLVED - Use `brew shellenv` dynamically

---

## Issue 2: macOS Library Paths

**Date**: 2026-02-01

**Problem**: Tilde expansion in Ansible paths

**Details**: `~` doesn't expand in Ansible paths automatically

**Solution**:
```yaml
- name: Use explicit paths
  ansible.builtin.file:
    path: "{{ ansible_env.HOME }}/Library/Application Support/Code/User/settings.json"
```

**Status**: RESOLVED - Always use `ansible_env.HOME`

---

## Issue 3: Dotbot vs Ansible Conflict

**Date**: 2026-02-01

**Problem**: Both Dotbot and Ansible creating symlinks

**Details**:
- May create conflicting symlinks
- Different symlink targets

**Solution**:
- Run Dotbot first to establish baseline
- Ansible uses `force: yes` to overwrite
- Phase out Dotbot after migration

**Status**: MITIGATED - Clear migration sequence

---

## Issue 4: File Mode Permissions

**Date**: 2026-02-01

**Problem**: SSH directory permissions too open

**Details**:
- `.ssh` needs 700 permissions
- Private keys need 600 permissions
- Ansible may not preserve modes

**Solution**:
```yaml
- name: Set SSH directory permissions
  ansible.builtin.file:
    path: "{{ ansible_env.HOME }}/.ssh"
    mode: '0700'

- name: Set SSH key permissions
  ansible.builtin.file:
    path: "{{ item }}"
    mode: '0600'
  loop: "{{ ssh_key_files }}"
```

**Status**: RESOLVED - Explicit permission tasks

---

## Issue 5: Git Submodules in Dotbot

**Date**: 2026-02-01

**Problem**: Dotbot runs git submodule update

**Details**:
- Current setup uses: `git submodule update --init --recursive`
- Ansible needs equivalent

**Solution**:
```yaml
- name: Initialize git submodules
  ansible.builtin.git:
    repo: "{{ item.repo }}"
    dest: "{{ item.path }}"
    recursive: yes
    track_submodules: yes
  loop: "{{ submodule_repos }}"
```

**Status**: RESOLVED - Use ansible.builtin.git

---

## Issue 6: XDG Directory Structure

**Date**: 2026-02-01

**Problem**: XDG config directories need creation

**Details**:
- `~/.config/fish`, `~/.config/zsh`, etc.
- Need to create parent directories

**Solution**:
```yaml
- name: Ensure XDG config directory
  ansible.builtin.file:
    path: "{{ ansible_env.HOME }}/.config/{{ item }}"
    state: directory
    mode: '0755'
  loop: "{{ xdg_configs }}"
```

**Status**: RESOLVED - Create dirs before symlink

---

## Issue 7: macOS Defaults Require Reload

**Date**: 2026-02-01

**Problem**: macOS defaults need app restart

**Details**:
- `killall Finder` needed for Finder changes
- Some defaults require logout/restart

**Solution**:
```yaml
- name: Restart Finder
  ansible.builtin.command: killall Finder
  ignore_errors: yes
```

**Status**: DOCUMENTED - User notification needed

---

## Issue 8: Homebrew Cask Installation

**Date**: 2026-02-01

**Problem**: Cask installation may require user interaction

**Details**:
- Some casks need license agreement
- GUI apps may have additional prompts

**Solution**:
```yaml
- name: Install cask
  community.general.homebrew_cask:
    name: "{{ item }}"
    state: present
  loop: "{{ cask_list }}"
  ignore_errors: yes  # For licenses that need manual accept
```

**Status**: MITIGATED - Use ignore_errors for edge cases
