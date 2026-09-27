#!/usr/bin/env bash
set -euo pipefail

# Keep the Mac awake for the whole provision. Homebrew/mise installs can take a
# long time, and idle sleep partway through leaves the machine half-configured.
# Re-exec ourselves once under caffeinate so every step below (brew, ansible,
# the playbook) runs inside a single sleep assertion that is released
# automatically when this script exits.
#   -i prevent idle sleep (works on battery)  -m keep disk spun up
#   -s prevent full system sleep (honored on AC power only)
if [ -z "${BOOTSTRAP_CAFFEINATED:-}" ] && command -v caffeinate &> /dev/null; then
    export BOOTSTRAP_CAFFEINATED=1
    exec caffeinate -ims "$0" "$@"
fi

echo "🚀 Ansible Dotfiles Bootstrap"
echo "=============================="

setup_homebrew_shellenv() {
    if [ -x /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -x /usr/local/bin/brew ]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
}

# A previous bootstrap attempt may have installed Homebrew without updating the
# terminal that launched this script. Find its standard installation before
# deciding whether a new installation is needed.
if ! command -v brew &> /dev/null; then
    setup_homebrew_shellenv
fi

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    # The installer runs NONINTERACTIVE, so it calls sudo with -n and can never
    # prompt for a password itself. Cache credentials first so creating
    # /opt/homebrew succeeds instead of failing with insufficient permissions.
    if ! sudo -n true 2> /dev/null; then
        if [ ! -t 0 ]; then
            echo "❌ sudo credentials are required to install Homebrew, but this shell is not interactive." >&2
            exit 1
        fi
        echo "🔑 Administrator password required to install Homebrew to /opt/homebrew..."
        sudo -v || {
            echo "❌ sudo authentication failed." >&2
            exit 1
        }
    fi

    # Refresh the cached sudo ticket while the installer runs. On a slow
    # network the download outlives the default 5-minute sudo timestamp, and
    # the installer's later `sudo -n` calls would fail halfway through.
    sudo_keepalive() { while sudo -n true 2> /dev/null; do sleep 30; done; }
    sudo_keepalive &
    sudo_keepalive_pid=$!
    trap 'kill "$sudo_keepalive_pid" 2> /dev/null || true' EXIT

    echo "📦 Installing Homebrew..."
    NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    kill "$sudo_keepalive_pid" 2> /dev/null || true
    trap - EXIT

    # Initialize Homebrew environment for this shell session
    setup_homebrew_shellenv
fi

# Check for Ansible
if ! command -v ansible-playbook &> /dev/null; then
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
