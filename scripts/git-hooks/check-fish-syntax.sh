#!/usr/bin/env bash
set -euo pipefail

for file in "$@"; do
    fish -n "$file"
done
