#!/usr/bin/env bash
set -euo pipefail

for file in "$@"; do
    zsh -n "$file"
done
