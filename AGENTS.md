# mac-dots

Personal macOS provisioning with Ansible and Dotbot. This checkout manages the
current machine: many files under `$HOME` are symlinks into it, so edits can affect
active applications immediately.

## Repository map

| Path | Purpose |
| --- | --- |
| `Makefile` | Provisioning entry points; passes `ARGS` to Ansible. |
| `ansible/playbooks/`, `ansible/roles/` | Orchestration and installation/configuration tasks. |
| `install.conf.yaml`, `install` | Dotbot link manifest and launcher. |
| `configs/`, root dotfiles | Tracked application and shell configuration linked into `$HOME`. |
| `homebrew/brew_packages.txt`, `homebrew/brew_casks.txt` | Desired Homebrew formulae and casks. |
| `configs/mise/config.toml` | Global runtime/tool versions; root `mise.toml` applies to this checkout. |
| `scripts/` | Utilities linked into `~/.local/bin` and Git hook scripts. |
| `exports/` | Application exports for manual import; not applied by provisioning. |

macOS defaults live in `ansible/roles/macos/tasks/mac/`. The macOS role uses those
tasks unless `macos_defaults_file` selects a backup to restore. Backups live in
`configs/macos/backups/`.

## Editing

- Edit repository sources rather than linked copies in `$HOME`. Update
  `install.conf.yaml` when adding or removing managed links; every link source
  must be tracked so it exists in a clean clone.
- `dotbot/` is a third-party submodule with dirty changes ignored by Git. Make
  integration changes in `install`, `install.conf.yaml`, or `ansible/roles/dotbot/`.
- Keep paths portable: use home-directory variables, Homebrew prefixes, or mise
  shims rather than a username or a version-specific tool installation path.
- Keep Ansible tasks idempotent. Prefer modules; commands need accurate change
  detection. Handle expected failures explicitly rather than suppressing errors.
- Package manifests describe desired state. Check formula/cask overlap and
  related configuration before changing entries.
- This repository is public. Keep credentials and authentication state untracked.

## Execution and validation

- Run direct Ansible commands from `ansible/` so `ansible.cfg` loads the inventory
  and roles. `dotfiles_repo` defaults to `~/.mac-dots`; set `DOTFILES_REPO` to the
  checkout path when working elsewhere.
- Do not apply provisioning as a test. For a preview, use a focused target such
  as `make macos ARGS="--check --diff"`. Applying macOS settings can restart Dock,
  Finder, and SystemUIServer. `make dotfiles` / `./install` can replace existing
  files and remove stale home-directory links.
- `make backup` overwrites tracked package lists, editor extension lists, and
  preference snapshots from the current machine. Run it only for a backup task
  and review the complete diff.
- For Ansible changes, run `cd ansible && ./scripts/validate.sh` (syntax, lint,
  and a check-mode deprecation probe). If required collections are missing, run
  `ansible-galaxy collection install -r requirements.yml` from `ansible/` first.
- For other changes, select the relevant hooks from `.pre-commit-config.yaml`:
  `pre-commit run <hook-id> --files <paths>`. Formatting hooks modify files;
  review their diff. CI covers Ansible only. `make hooks-run` checks the full repo.
