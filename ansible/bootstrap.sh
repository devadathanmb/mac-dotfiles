#!/usr/bin/env bash
set -e

echo "🚀 Ansible Dotfiles Bootstrap"
echo "=============================="

# Check for Homebrew
if ! command -v brew &>/dev/null; then
    echo "📦 Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
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
