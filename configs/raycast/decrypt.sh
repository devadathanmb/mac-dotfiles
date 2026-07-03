#!/usr/bin/env bash
set -euo pipefail
trap 'stty sane 2>/dev/null || true' EXIT

cd "$(dirname "$0")"

input="${1:-raycast-x-backup.rayconfig.gpg}"
output="${2:-${input%.gpg}}"

if [[ ! -f "$input" ]]; then
  echo "Missing encrypted Raycast config: $input" >&2
  exit 1
fi

if [[ -e "$output" ]]; then
  echo "Refusing to overwrite existing file: $output" >&2
  exit 1
fi

read -rsp "GPG passphrase: " passphrase
echo

gpg --batch --yes --pinentry-mode loopback \
  --passphrase-fd 3 \
  --decrypt --output "$output" "$input" \
  3< <(printf '%s' "$passphrase")
unset passphrase

chmod 600 "$output"

echo "Decrypted $input -> $output"
