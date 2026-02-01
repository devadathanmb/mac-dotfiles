# Dotfiles

> Hello, welcome $HOME

Personal dotfiles repository for macOS, managed with Ansible (orchestrating Dotbot for symlinks).

## Quick Start

**Full setup:**
```bash
git clone https://github.com/devadathanmb/mac-dotfiles.git ~/.mac-dots
cd ~/.mac-dots
./ansible/bootstrap.sh
```

**Selective execution with tags:**
```bash
cd ~/.mac-dots/ansible

# Run all roles
ansible-playbook playbooks/main.yml

# Run specific roles
ansible-playbook playbooks/main.yml --tags dotbot        # Symlinks
ansible-playbook playbooks/main.yml --tags homebrew      # Packages
ansible-playbook playbooks/main.yml --tags macos         # Defaults
ansible-playbook playbooks/main.yml --tags shell         # Shell
ansible-playbook playbooks/main.yml --tags editors       # Extensions
ansible-playbook playbooks/asdf.yml                      # ASDF (Python + Node.js)

# Check what would change (dry-run)
ansible-playbook playbooks/main.yml --check --diff
```

**Backup installed packages/extensions:**
```bash
cd ~/.mac-dots/ansible
ansible-playbook playbooks/backup.yml
```

## Structure

```
ansible/
├── ansible.cfg              # Ansible configuration
├── requirements.yml         # Ansible collections
├── bootstrap.sh            # Fresh install entry point
├── inventory/
│   └── localhost.yml       # Localhost inventory
├── group_vars/
│   └── all.yml             # Shared variables
├── playbooks/
│   ├── main.yml            # Orchestrates all roles
│   ├── dotbot.yml          # Dotbot symlinks
│   ├── packages.yml        # Homebrew packages
│   ├── macos.yml           # macOS defaults
│   ├── shell.yml           # Shell setup
│   ├── editors.yml         # Editor extensions
│   ├── asdf.yml            # ASDF (Python + Node.js)
│   └── backup.yml          # Backup packages/extensions
└── roles/
    ├── dotbot/             # Orchestrates ./install
    ├── homebrew/           # Homebrew packages
    ├── macos/              # System defaults
    ├── shell/              # Zap ZSH
    ├── editors/            # VSCode + Cursor extensions
    └── asdf/               # ASDF version manager
```

## License

See [LICENSE](LICENSE) for details.
