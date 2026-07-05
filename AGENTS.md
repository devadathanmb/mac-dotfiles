# Repository Guidelines

## Project Structure & Module Organization

This repository manages a macOS environment with Ansible and Dotbot. Use `Makefile` from the repository root as the main entry point. Ansible playbooks live in `ansible/playbooks/`, shared variables in `ansible/group_vars/`, inventory in `ansible/inventory/`, and roles in `ansible/roles/`. Application and shell configuration files live under `configs/` and are linked by Dotbot through `install.conf.yaml`. Homebrew package manifests are in `homebrew/`. Standalone helper scripts belong in `scripts/`; Ansible-specific scripts belong in `ansible/scripts/`. `dotbot/` is a submodule and should not be edited unless intentionally updating Dotbot itself.

## Build, Test, and Development Commands

- `make`: show available targets.
- `make bootstrap`: first-time setup; installs prerequisites and runs the full setup.
- `make all`: run the main Ansible playbook.
- `make packages`, `make macos`, `make dotfiles`, `make zsh`, `make editors`, `make mise`: run focused playbooks.
- `make backup`: pull current package, editor, and macOS defaults state back into the repo.
- `make macos ARGS="--check --diff"`: dry-run a target with extra Ansible flags.
- `make hooks`: install repo-managed pre-commit hooks into `.git/hooks/`.
- `make hooks-run`: run all hooks against the repository.
- `cd ansible && ./scripts/validate.sh`: run syntax, lint, and deprecation checks.

## Coding Style & Naming Conventions

Write YAML with two-space indentation, explicit task names, and clear role or tag names such as `homebrew`, `macos`, or `editors`. Keep playbooks small and delegate reusable behavior to roles or scripts. Shell scripts should be Bash-compatible, use `set -e` when appropriate, and prefer readable variable names. Let pre-commit run Prettier, `yamllint`, `shfmt`, `shellcheck`, `fish_indent`, and syntax checks before committing.

## Testing Guidelines

There is no general unit test suite. Validate Ansible changes with `ansible-playbook playbooks/<name>.yml --syntax-check` and `ansible-lint playbooks/*.yml` from `ansible/`, or run `ansible/scripts/validate.sh`. For machine-affecting changes, prefer `--check --diff` first. Confirm symlink changes with `make dotfiles ARGS="--check --diff"` before applying.

## Commit & Pull Request Guidelines

Recent history uses concise Conventional Commit-style messages, for example `feat: add ...`, `fix: align ...`, `chore: migrate ...`, plus occasional `backup` snapshots. Prefer a scoped, imperative summary. Pull requests should explain the affected area, include validation output or dry-run notes, and call out any macOS defaults, package installs, or destructive changes. Include screenshots only for visible editor or terminal UI changes.
