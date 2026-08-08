# Repository Instructions

## Sources Of Truth

- This repository provisions the current Mac. `Makefile` drives Ansible; `install.conf.yaml` defines Dotbot links into `$HOME`.
- Edit tracked sources, usually under `configs/`, rather than their linked copies in `$HOME`. Change `install.conf.yaml` when adding or removing managed paths.
- Run direct Ansible commands from `ansible/` so its inventory and role paths load from `ansible.cfg`.
- Do not edit `dotbot/`; it is an ignored-dirty submodule. Change `install`, `install.conf.yaml`, or `ansible/roles/dotbot/` instead.
- `configs/agents/AGENTS.md` is symlinked globally for OpenCode, Codex, and Claude; reserve it for cross-repository rules.

## Working Standard

- Keep changes scoped to one provisioning concern. Do not mix machine-state backups with unrelated config edits.
- Keep Ansible idempotent: prefer modules to `command`/`shell`, set accurate `changed_when`, and use focused task names and tags.
- Ignore failures only for optional work; register and report them.
- Do not run provisioning targets as validation. Preview applicable changes with `ARGS="--check --diff"`; macOS tasks may restart Finder, Dock, and SystemUIServer.
- Dotbot uses `force: true`, `relink: true`, and `clean: ["~"]`; `make dotfiles` and `./install` can replace files and remove stale links in `$HOME`.
- `make backup` rewrites tracked package and editor lists and creates a macOS defaults snapshot. Review its entire diff.

## Verification

- Run a focused hook with `pre-commit run <hook-id> --files <paths>`; formatting hooks modify files. Use `make hooks-run` only when the full repository check is warranted.
- Validate Ansible with `cd ansible && ./scripts/validate.sh`. If modules are missing, first run `ansible-galaxy collection install -r requirements.yml` there.
- CI validates only Ansible. Use local hooks for shell, fish, repository-level YAML, and application config.

## Known Constraints

- `DOTFILES_REPO` resolves Ansible role paths; application settings may still contain user-specific paths.
- OpenCode keys belong in untracked `~/.secrets/*` files, never `configs/opencode/opencode.jsonc`. Restart OpenCode after changing that config.
