# mac-dots

> Hello, welcome $HOME

My macOS setup, managed with [Ansible](https://docs.ansible.com/). Ansible orchestrates [Dotbot](https://github.com/anishathalye/dotbot), which does the symlinking.

## What's managed

- **Shell**: zsh (zap, powerlevel10k), fish
- **Terminal**: Ghostty, Kitty, iTerm2
- **Editors**: VSCode, Cursor, Zed, Vim. Extension lists are tracked and reinstalled on setup.
- **AI coding tools**: Claude Code (settings, agents, hooks, skills), Codex, OpenCode, Pi, shared MCP config
- **CLI tools**: tmux, git, gh, curl, wget, atuin, pgcli, psql, htop, btop, mpv, and a few more in `configs/` and the top-level dotfiles
- **macOS system defaults**: dock, Finder, keyboard, trackpad, security, spaces, appearance. No sudo needed.
- **Homebrew**: formulae and casks, tracked in `homebrew/`, reinstalled on setup

## Setup

```bash
git clone --recursive https://github.com/devadathanmb/mac-dotfiles.git ~/.mac-dots
cd ~/.mac-dots
make bootstrap        # or: ./ansible/bootstrap.sh
```

`bootstrap.sh` installs Homebrew and Ansible if missing, then runs the full playbook. Re-run it any time; it keeps the Mac awake during long installs.

Dotbot is a git submodule. If you clone without `--recursive`, pull it in with:

```bash
git submodule update --init --recursive
```

## Running things selectively

`make` (run from the repo root) is the friendly frontend. Each target wraps the matching playbook, runs under `caffeinate`, and can be chained (`make backup macos`). `make` on its own lists everything.

```bash
make all              # everything (brew + ansible already present)
make packages         # Homebrew formulae + casks
make macos            # system defaults
make dotfiles         # symlinks
make zsh              # zap zsh
make editors          # editor extensions
make mise             # mise (Python + Node.js)

make packages ARGS="--check --diff"   # pass extra flags through to ansible
```

Or drive Ansible directly for finer control:

```bash
cd ~/.mac-dots/ansible

ansible-playbook playbooks/main.yml                   # everything

ansible-playbook playbooks/main.yml --tags dotbot     # symlinks
ansible-playbook playbooks/main.yml --tags homebrew   # packages
ansible-playbook playbooks/main.yml --tags macos      # system defaults
ansible-playbook playbooks/main.yml --tags zsh        # zap zsh
ansible-playbook playbooks/main.yml --tags editors    # editor extensions
ansible-playbook playbooks/mise.yml                   # mise (Python + Node.js)

ansible-playbook playbooks/main.yml --check --diff    # dry run
```

## Pulling live state back into the repo

```bash
make backup           # from the repo root

# Or directly, for tag-level control:
cd ~/.mac-dots/ansible
ansible-playbook playbooks/backup.yml

# Back up only managed macOS defaults.
ansible-playbook playbooks/backup.yml --tags macos

# Apply one timestamped macOS defaults backup.
ansible-playbook playbooks/macos.yml -e macos_defaults_file=configs/macos/backups/macos-defaults-YYYYMMDD-HHMMSS.yml
```

This reads installed Homebrew formulae, casks, VSCode/Cursor/Zed extensions, and managed macOS defaults off the current machine and writes them into the repo. macOS defaults backups are timestamped under `configs/macos/backups/`; check `git diff` before committing.

## Layout

```
Makefile             # Friendly frontend over the playbooks (make help)
ansible/             # Playbooks and roles
configs/             # App configs, symlinked by Dotbot
homebrew/            # Tracked formulae and casks
scripts/             # Standalone scripts, symlinked to ~/.local/bin
install.conf.yaml    # Dotbot's symlink map
```

## License

[GPL 3.0](./LICENSE)
