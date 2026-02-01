#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Starting Ansible dotfiles setup..."

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "📦 Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add Homebrew to PATH for this session
    if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
fi

# Check if Ansible is installed
if ! command -v ansible &> /dev/null; then
    echo "📦 Installing Ansible..."
    brew install ansible
fi

# Install required Ansible collections
echo "📦 Installing Ansible Galaxy collections..."
ansible-galaxy collection install community.general --force

# Run the playbook
echo "🔧 Running Ansible playbook..."
ansible-playbook site.yml "$@"

echo "✅ Setup complete!"
echo ""
echo "You may need to:"
echo "  1. Restart your terminal"
echo "  2. Log out and back in for macOS changes to take effect"
