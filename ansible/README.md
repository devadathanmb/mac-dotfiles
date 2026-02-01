# Ansible Dotfiles

Ansible-based configuration management for macOS development environment.

## Prerequisites

1. **Xcode Command Line Tools**
   ```bash
   xcode-select --install
   ```

2. **Homebrew** (will be installed automatically if missing)
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

3. **Ansible**
   ```bash
   brew install ansible
   ```

4. **Ansible Galaxy Collections**
   ```bash
   ansible-galaxy collection install community.general
   ```

## Quick Start

Run the full setup:

```bash
cd ansible
./run.sh
```

Or manually:

```bash
cd ansible
ansible-playbook site.yml
```

## Playbooks

### Full Setup
```bash
ansible-playbook site.yml
```

### Individual Components

**Homebrew packages only:**
```bash
ansible-playbook playbooks/homebrew.yml
```

**Dotfile symlinks only:**
```bash
ansible-playbook playbooks/dotfiles.yml
```

**macOS preferences only:**
```bash
ansible-playbook playbooks/macos.yml
```

**Shell setup only:**
```bash
ansible-playbook playbooks/shell.yml
```

**VS Code/Cursor extensions only:**
```bash
ansible-playbook playbooks/vscode.yml
```

## Using Tags

Run specific parts of the setup:

```bash
# Only homebrew
ansible-playbook site.yml --tags homebrew

# Only dotfiles
ansible-playbook site.yml --tags dotfiles

# Only macOS defaults
ansible-playbook site.yml --tags macos

# Only shell setup
ansible-playbook site.yml --tags shell

# Only editor extensions
ansible-playbook site.yml --tags vscode
```

## Dry Run (Check Mode)

Preview changes without applying them:

```bash
ansible-playbook site.yml --check
```

## Verbose Output

Get detailed output:

```bash
ansible-playbook site.yml -v    # verbose
ansible-playbook site.yml -vv   # more verbose
ansible-playbook site.yml -vvv  # debug level
```

## Configuration

### Feature Flags

Edit `group_vars/all.yml` to enable/disable features:

```yaml
install_homebrew: true
install_dotfiles: true
configure_macos: true
install_vscode_extensions: true
install_cursor_extensions: true
setup_shell: true
```

### Customizing Packages

Edit role vars files to customize:

- `roles/homebrew/vars/main.yml` - Homebrew packages and casks
- `roles/dotfiles/vars/main.yml` - Symlink mappings
- `roles/vscode/vars/main.yml` - VS Code/Cursor extensions

## Directory Structure

```
ansible/
├── ansible.cfg           # Ansible configuration
├── inventory/
│   └── hosts.yml         # Inventory (localhost)
├── group_vars/
│   └── all.yml           # Global variables
├── site.yml              # Main playbook
├── playbooks/            # Individual playbooks
│   ├── homebrew.yml
│   ├── dotfiles.yml
│   ├── macos.yml
│   ├── shell.yml
│   └── vscode.yml
├── roles/
│   ├── homebrew/         # Homebrew package management
│   ├── dotfiles/         # Symlink management
│   ├── macos/            # macOS system preferences
│   ├── shell/            # Zsh/Zap setup
│   └── vscode/           # VS Code/Cursor extensions
└── run.sh                # Quick run script
```

## Roles

### homebrew
Installs Homebrew (if needed), taps, packages, and casks.

### dotfiles
Creates symlinks for dotfiles to their proper locations.

### macos
Configures macOS system preferences (trackpad, finder, dock, etc.).

### shell
Installs Zap Zsh plugin manager and sets Zsh as default shell.

### vscode
Installs VS Code and Cursor editor extensions.

## Troubleshooting

### Permission Errors
Some macOS settings may require running with `--ask-become-pass`:
```bash
ansible-playbook site.yml --ask-become-pass
```

### Failed Tasks
Individual task failures are often due to missing applications. Install the application first, then re-run.

### Idempotency
All tasks are designed to be idempotent - running them multiple times produces the same result.
