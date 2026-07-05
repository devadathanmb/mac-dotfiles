#!/usr/bin/env bash
set -euo pipefail

printf '%s\n\n' 'Ansible files detected - running validation...'

cd ansible
./scripts/validate.sh
