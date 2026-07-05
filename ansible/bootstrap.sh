#!/usr/bin/env bash
set -euo pipefail

# Keep the Mac awake for the whole provision. Homebrew/mise installs can take a
# long time, and idle sleep partway through leaves the machine half-configured.
# Re-exec ourselves once under caffeinate so every step below (brew, ansible,
# the playbook) runs inside a single sleep assertion that is released
# automatically when this script exits.
#   -i prevent idle sleep (works on battery)  -m keep disk spun up
#   -s prevent full system sleep (honored on AC power only)
if [ -z "${BOOTSTRAP_CAFFEINATED:-}" ] && command -v caffeinate &>/dev/null; then
    export BOOTSTRAP_CAFFEINATED=1
    exec caffeinate -ims "$0" "$@"
fi

echo "🚀 Ansible Dotfiles Bootstrap"
echo "=============================="

# Check for Homebrew
if ! command -v brew &>/dev/null; then
    echo "📦 Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Initialize Homebrew environment for this shell session
    if [ -x /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -x /usr/local/bin/brew ]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
fi

# Check for Ansible
if ! command -v ansible-playbook &>/dev/null; then
    echo "📦 Installing Ansible via Homebrew..."
    brew install ansible
fi

# Install Ansible collections
echo "📦 Installing Ansible collections..."
cd "$(dirname "$0")"
ansible-galaxy collection install -r requirements.yml

# Run the main playbook
echo "🚀 Running Ansible playbook..."
ansible-playbook playbooks/main.yml "$@"

echo "✅ Bootstrap complete!"
