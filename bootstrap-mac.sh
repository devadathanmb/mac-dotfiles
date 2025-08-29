#!/usr/bin/env bash
set -e

echo "🚀 Starting macOS bootstrap process"

# 1. Install homebrew and stuff
source "./homebrew/brew-setup.sh"

# 2. Setup sane macOS settings
source "./mac/mac-setup.sh"

# 3. Setup zsh using zap zsh
source "./configs/zsh/setup-zap-zsh.sh"

# 4. Install vscode and cursor extensions
source "./configs/cursor/install-extensions.sh"
source "./configs/vscode/install-extensions.sh"

echo "Bootstrapping complete! Please restart your system to apply all changes."