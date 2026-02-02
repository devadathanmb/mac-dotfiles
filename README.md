# Dotfiles

> Hello, welcome $HOME

Personal dotfiles repository for macOS, managed with [Ansible](https://docs.ansible.com/) orchestrating [Dotbot](https://github.com/deadc0de6/dotbot) for symlinks.

## Quick Start

### Full setup
```bash
git clone https://github.com/devadathanmb/mac-dotfiles.git ~/.mac-dots
cd ~/.mac-dots
./ansible/bootstrap.sh
```

### Selective execution
```bash
cd ~/.mac-dots/ansible

# Run all roles
ansible-playbook playbooks/main.yml

# Run specific roles
ansible-playbook playbooks/main.yml --tags dotbot     # Symlinks
ansible-playbook playbooks/main.yml --tags homebrew   # Homebrew packages
ansible-playbook playbooks/main.yml --tags macos      # macOS defaults
ansible-playbook playbooks/main.yml --tags zsh      # ZSH (Zap ZSH)
ansible-playbook playbooks/main.yml --tags editors    # Editor extensions
ansible-playbook playbooks/asdf.yml                   # ASDF (Python + Node.js)

# Dry-run (preview changes)
ansible-playbook playbooks/main.yml --check --diff
```

### Backup
```bash
cd ~/.mac-dots/ansible
ansible-playbook playbooks/backup.yml
```

## Structure

```
ansible/
├── ansible.cfg              # Ansible configuration
├── requirements.yml         # Ansible collections
├── bootstrap.sh             # Fresh install entry point
├── inventory/
│   └── localhost.yml        # Localhost inventory
├── group_vars/
│   └── all.yml              # Shared variables
├── playbooks/
│   ├── main.yml             # Orchestrates all roles
│   ├── dotbot.yml           # Dotbot symlinks
│   ├── packages.yml         # Homebrew packages
│   ├── macos.yml            # macOS defaults
│   ├── zsh.yml              # Zap ZSH shell
│   ├── editors.yml          # VSCode + Cursor extensions
│   ├── asdf.yml             # ASDF version manager
│   └── backup.yml           # Backup packages/extensions
└── roles/
    ├── dotbot/              # Orchestrates ./install
    ├── homebrew/            # Homebrew packages
    ├── macos/               # System defaults
    ├── zsh/                 # Zap ZSH
    ├── editors/             # Editor extensions
    └── asdf/                # ASDF
```

## License

[MIT](LICENSE)
