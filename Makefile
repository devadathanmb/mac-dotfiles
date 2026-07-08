ANSIBLE_DIR := ansible
PLAYBOOK    := ansible-playbook
# prevent idle/disk/system sleep during long installs
CAFFEINATE  := caffeinate -ims

RAYCAST_CONFIG_DIR        := configs/raycast
RAYCAST_BACKUP_DEST       := $(RAYCAST_CONFIG_DIR)/raycast-x-backup.rayconfig
RAYCAST_BACKUP_SOURCE_DIR ?= $(HOME)
RAYCAST_EXPORT_DEEPLINK   := raycast://extensions/raycast/raycast/export-settings-data?launchType=userInitiated

# cd into ansible/ so ansible.cfg is picked up; caffeinate the whole run.
play = cd $(ANSIBLE_DIR) && $(CAFFEINATE) $(PLAYBOOK) playbooks/$(1).yml $(ARGS)

.DEFAULT_GOAL := help
.PHONY: help bootstrap all packages macos dotfiles zsh editors mise backup raycast-backup raycast-backup-mv hooks hooks-run

help:        ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n",$$1,$$2}'

bootstrap:   ## First-time setup: install Homebrew + Ansible, run everything
	./$(ANSIBLE_DIR)/bootstrap.sh $(ARGS)

all:         ## Run the full main playbook (brew + ansible already present)
	$(call play,main)

packages:    ## Install Homebrew formulae + casks
	$(call play,packages)

macos:       ## Apply macOS defaults
	$(call play,macos)

dotfiles:    ## Symlink dotfiles (dotbot)
	$(call play,dotbot)

zsh:         ## Set up zsh
	$(call play,zsh)

editors:     ## Install editor extensions (VSCode/Cursor/Zed)
	$(call play,editors)

mise:        ## Install mise + latest Python/Node
	$(call play,mise)

backup:      ## Back up installed packages/extensions/macOS defaults into the repo
	$(call play,backup)

raycast-backup: ## Open Raycast Beta's export prompt
	@open -b com.raycast-x.macos "$(RAYCAST_EXPORT_DEEPLINK)"
	@printf 'Export the .rayconfig file, then run `make raycast-backup-mv`.\n'

raycast-backup-mv: ## Move latest Raycast export from RAYCAST_BACKUP_SOURCE_DIR into the repo
	@mkdir -p "$(RAYCAST_CONFIG_DIR)"
	@latest=""; \
		for candidate in "$(RAYCAST_BACKUP_SOURCE_DIR)"/*.rayconfig; do \
			[ -e "$$candidate" ] || continue; \
			if [ -z "$$latest" ] || [ "$$candidate" -nt "$$latest" ]; then \
				latest="$$candidate"; \
			fi; \
		done; \
		if [ -z "$$latest" ]; then \
			printf 'No .rayconfig file found in %s\n' "$(RAYCAST_BACKUP_SOURCE_DIR)" >&2; \
			exit 1; \
		fi; \
		mv -f "$$latest" "$(RAYCAST_BACKUP_DEST)"; \
		printf 'Moved %s -> %s\n' "$$latest" "$(RAYCAST_BACKUP_DEST)"

hooks:       ## Install repo-managed pre-commit hooks into .git/hooks
	pre-commit install --install-hooks

hooks-run:   ## Run all pre-commit hooks against the full repo
	pre-commit run --all-files
