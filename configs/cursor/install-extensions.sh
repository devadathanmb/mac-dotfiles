#!/usr/bin/env bash

# Script to install Cursor extensions from a backup file
# Usage: ./install-cursor-extensions.sh [extensions-file]

set -e # Exit on any error

EXTENSIONS_FILE="${1:-extensions.txt}"
FAILED_EXTENSIONS=()

echo "🔧 Cursor Extensions Installer"
echo "==============================="

# Check if Cursor is installed
if ! command -v cursor &> /dev/null; then
    echo "❌ Cursor command not found. Make sure Cursor is installed and added to PATH."
    exit 1
fi

# Check if extensions file exists
if [ ! -f "$EXTENSIONS_FILE" ]; then
    echo "❌ Extensions file '$EXTENSIONS_FILE' not found."
    echo "Usage: $0 [extensions-file]"
    exit 1
fi

# Count total extensions
total_extensions=$(grep -cv '^$\|^#' "$EXTENSIONS_FILE")
current=0

echo "📦 Found $total_extensions extensions to install"
echo ""

# Install extensions
while IFS= read -r extension; do
    # Skip empty lines and comments
    if [[ -z "$extension" || "$extension" =~ ^#.* ]]; then
        continue
    fi

    current=$((current + 1))
    echo "[$current/$total_extensions] Installing: $extension"

    if cursor --install-extension "$extension" --force > /dev/null 2>&1; then
        echo "✅ Successfully installed: $extension"
    else
        echo "❌ Failed to install: $extension"
        FAILED_EXTENSIONS+=("$extension")
    fi

    echo ""
done < "$EXTENSIONS_FILE"

echo "🎉 Installation process complete!"
echo ""

# Report results
if [ ${#FAILED_EXTENSIONS[@]} -eq 0 ]; then
    echo "✅ All extensions installed successfully!"
else
    echo "⚠️  ${#FAILED_EXTENSIONS[@]} extension(s) failed to install:"
    for failed_ext in "${FAILED_EXTENSIONS[@]}"; do
        echo "  - $failed_ext"
    done
    echo ""
    echo "You can try installing these manually or check if they're still available."
fi

echo "Run 'cursor --list-extensions' to verify installed extensions."
