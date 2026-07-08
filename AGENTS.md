# Agent Notes

## Shape

- Personal macOS dotfiles/provisioning repo; use `Makefile` as the main interface.
- Dotbot links `configs/` and top-level dotfiles into `$HOME` from `install.conf.yaml`.
- Ansible is rooted at `ansible/`; run direct `ansible-playbook` commands there so `ansible.cfg` loads `inventory/localhost.yml` and `roles_path = roles`.
- `dotbot/` is a vendored submodule (`ignore = dirty`); do not edit it for repo behavior changes.
- No root npm workspace. Package manifests are under `configs/pi/npm` and `configs/pi/extensions/*`; run npm commands inside the relevant package directory.

## Commands

- `make`: list supported targets.
- `make bootstrap`: first-time/full setup; may install Homebrew/Ansible and changes the live Mac.
- `make all`: run the full main playbook after prerequisites exist.
- Focused targets: `make packages`, `make macos`, `make dotfiles`, `make zsh`, `make editors`, `make mise`.
- Dry-run focused Ansible through Make with `ARGS`, e.g. `make macos ARGS="--check --diff"`.
- Direct tagged run from `ansible/`: `ansible-playbook playbooks/main.yml --tags dotbot`.
- Restore a macOS defaults snapshot from `ansible/`: `ansible-playbook playbooks/macos.yml -e macos_defaults_file=configs/macos/backups/macos-defaults-YYYYMMDD-HHMMSS.yml`.

## Validation

- Install hooks once: `make hooks`; run all hooks: `make hooks-run`.
- Validate Ansible only from `ansible/`: `./scripts/validate.sh`.
- Hooks require `prettier`, `yamllint`, `shfmt`, `shellcheck`, `fish`, `zsh`, and `ansible-lint`; `homebrew/brew_packages.txt` tracks all except system `zsh`.
- Pre-commit excludes `dotbot/` and runs the local staged-change scanner before formatting/lint hooks.
- No `.github/workflows` are present currently; do not assume CI will catch issues.

## Gotchas

- `install.conf.yaml` uses Dotbot `force: true`, `relink: true`, and `clean: ["~"]`; `make dotfiles`/`./install` can replace existing files in `$HOME` with symlinks.
- `make backup` writes current machine state into tracked files: Homebrew lists, VSCode/Cursor/Zed extension lists, and timestamped `configs/macos/backups/`; inspect `git diff` after it.
- The Homebrew and editor roles use `ignore_errors: true` for package/extension installs, so a playbook can finish while individual installs failed; read the debug output.
- `DOTFILES_REPO` overrides the repo path for most playbooks, but some role defaults hard-code `/Users/devadathanmb/.mac-dots`; prefer this checkout unless testing path overrides.
- `make bootstrap` and Make playbook targets wrap long runs with `caffeinate -ims`; direct `ansible-playbook` commands do not.
- The macOS role restarts Finder, Dock, and SystemUIServer through handlers after relevant defaults changes.
