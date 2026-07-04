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
./ansible/bootstrap.sh
```

`bootstrap.sh` installs Homebrew and Ansible if missing, then runs the full playbook.

Dotbot is a git submodule. If you clone without `--recursive`, pull it in with:

```bash
git submodule update --init --recursive
```

## Running things selectively

```bash
cd ~/.mac-dots/ansible

ansible-playbook playbooks/main.yml                   # everything

ansible-playbook playbooks/main.yml --tags dotbot     # symlinks
ansible-playbook playbooks/main.yml --tags homebrew   # packages
ansible-playbook playbooks/main.yml --tags macos      # system defaults
ansible-playbook playbooks/main.yml --tags zsh        # zap zsh
ansible-playbook playbooks/main.yml --tags editors    # editor extensions
ansible-playbook playbooks/asdf.yml                   # asdf (Python + Node.js)

ansible-playbook playbooks/main.yml --check --diff    # dry run
```

## Pulling live state back into the repo

```bash
cd ~/.mac-dots/ansible
ansible-playbook playbooks/backup.yml
```

This reads installed Homebrew formulae, casks, and VSCode/Cursor/Zed extensions off the current machine and writes them into the repo. Check `git diff` before committing.

## Layout

```
ansible/            # Playbooks and roles
configs/             # App configs, symlinked by Dotbot
homebrew/            # Tracked formulae and casks
scripts/             # Standalone scripts, symlinked to ~/.local/bin
install.conf.yaml    # Dotbot's symlink map
```

## License

[GPL 3.0](./LICENSE)
