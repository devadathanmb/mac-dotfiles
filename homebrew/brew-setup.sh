#!/usr/bin/env bash

# Script to install Homebrew and packages/casks from backup files
# Usage: ./brew-setup.sh

set -e  # Exit on any error

echo "🍺 Homebrew Setup Script"
echo "========================"

# Check if Homebrew is installed, install if not
if ! command -v brew &> /dev/null; then
    echo "📥 Homebrew not found. Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for this session
    if [[ -f "/opt/homebrew/bin/brew" ]]; then
        # Apple Silicon Mac
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [[ -f "/usr/local/bin/brew" ]]; then
        # Intel Mac
        eval "$(/usr/local/bin/brew shellenv)"
    fi
    
    echo "✅ Homebrew installed successfully!"
else
    echo "✅ Homebrew already installed"
fi

echo ""

# Install formulae (regular packages)
if [ -f "brew_packages.txt" ]; then
    echo "📦 Installing formulae..."
    while IFS= read -r package; do
        if [ -n "$package" ]; then
            echo "Installing: $package"
            brew install "$package" || echo "⚠️  Failed to install: $package"
        fi
    done < brew_packages.txt
    echo "✅ Formulae installation complete"
else
    echo "⚠️  brew_packages.txt not found, skipping formulae"
fi

echo ""

# Install casks (GUI applications)
if [ -f "brew_casks.txt" ]; then
    echo "🖥️  Installing casks..."
    while IFS= read -r cask; do
        if [ -n "$cask" ]; then
            echo "Installing: $cask"
            brew install --cask "$cask" || echo "⚠️  Failed to install: $cask"
        fi
    done < brew_casks.txt
    echo "✅ Casks installation complete"
else
    echo "⚠️  brew_casks.txt not found, skipping casks"
fi


# Install other casks (GUI applications)
if [ -f "other_casks.txt" ]; then
    echo "🖥️  Installing casks..."
    while IFS= read -r cask; do
        if [ -n "$cask" ]; then
            echo "Installing: $cask"
            brew install --cask "$cask" || echo "⚠️  Failed to install: $cask"
        fi
    done < other_casks.txt
    echo "✅ Casks installation complete"
else
    echo "⚠️  other_casks.txt not found, skipping casks"
fi

echo ""
echo "🎉 Installation process complete!"
echo "Run 'brew doctor' to check for any issues."
