#!/usr/bin/env bash
set -euo pipefail
trap 'stty sane 2>/dev/null || true' EXIT

cd "$(dirname "$0")"

input="${1:-raycast-x-backup.rayconfig}"
output="${2:-${input}.gpg}"

if [[ ! -f "$input" ]]; then
  echo "Missing plaintext Raycast config: $input" >&2
  exit 1
fi

read -rsp "GPG passphrase: " passphrase
echo
read -rsp "Confirm passphrase: " confirm
echo

if [[ "$passphrase" != "$confirm" ]]; then
  echo "Passphrases do not match" >&2
  exit 1
fi
unset confirm

gpg --batch --yes --pinentry-mode loopback \
  --passphrase-fd 3 \
  --symmetric --cipher-algo AES256 \
  --output "$output" "$input" \
  3< <(printf '%s' "$passphrase")
unset passphrase

chmod 600 "$output"

echo "Encrypted $input -> $output"
