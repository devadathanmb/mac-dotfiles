# Dotfiles

> Hello, welcome $HOME


Personal dotfiles repository for macOS, managed with [Dotbot](https://github.com/anishathalye/dotbot) and Ansible.

## Quick Start

### Option 1: Ansible (Recommended)

**Full setup:**
```bash
git clone https://github.com/devadathanmb/mac-dotfiles.git ~/.dotfiles
cd ~/.dotfiles
./ansible/bootstrap.sh
```

**Selective execution with tags:**
```bash
cd ~/.dotfiles/ansible

# Run only dotfiles symlinks
ansible-playbook playbooks/main.yml --tags dotbot

# Run only Homebrew packages
ansible-playbook playbooks/main.yml --tags homebrew

# Run only macOS defaults
ansible-playbook playbooks/main.yml --tags macos

# Run only shell setup (Zap ZSH)
ansible-playbook playbooks/main.yml --tags shell

# Run only editor extensions
ansible-playbook playbooks/main.yml --tags editors

# Check what would change (dry-run)
ansible-playbook playbooks/main.yml --check --diff
```

### Option 2: Dotbot (Original)

1. **Fresh machine setup**: Clone and bootstrap for complete setup
   ```bash
   git clone https://github.com/devadathanmb/mac-dotfiles.git ~/.dotfiles
   cd ~/.dotfiles
   ./bootstrap-mac.sh
   ```

2. **Symlink dotfiles**: After setup, symlink your configs
   ```bash
   # Dry run first
   ./install --dry-run

   # Once confirmed, run
   ./install
   ```

## Backup

After installing packages or extensions, back them up to your dotfiles:

```bash
cd ~/.dotfiles/ansible
ansible-playbook playbooks/backup.yml
```

This will update:
- `homebrew/brew_packages.txt` - Installed formulae
- `homebrew/brew_casks.txt` - Installed casks
- `configs/vscode/extensions.txt` - VSCode extensions
- `configs/cursor/extensions.txt` - Cursor extensions

Then commit the changes:
```bash
git diff
git add .
git commit -m "chore: backup packages and extensions"
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
│   ├── dotbot.yml          # Dotbot symlinks only
│   ├── packages.yml        # Homebrew packages only
│   ├── macos.yml           # macOS defaults only
│   ├── shell.yml           # Shell setup only
│   ├── editors.yml         # Editor extensions only
│   └── backup.yml          # Backup packages/extensions to txt files
└── roles/
    ├── dotbot/             # Orchestrates ./install
    ├── homebrew/           # Homebrew packages (286 formulae, 41 casks)
    ├── macos/              # System defaults (66 settings)
    ├── shell/              # Zap ZSH setup
    └── editors/            # VSCode + Cursor extensions (94 total)
```

## License

See [LICENSE](LICENSE) for details.
