ANSIBLE_DIR := ansible
PLAYBOOK    := ansible-playbook
# prevent idle/disk/system sleep during long installs
CAFFEINATE  := caffeinate -ims

# cd into ansible/ so ansible.cfg is picked up; caffeinate the whole run.
play = cd $(ANSIBLE_DIR) && $(CAFFEINATE) $(PLAYBOOK) playbooks/$(1).yml $(ARGS)

.DEFAULT_GOAL := help
.PHONY: help bootstrap all packages macos dotfiles zsh editors asdf backup

help:        ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n",$$1,$$2}'

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

asdf:        ## Install asdf + latest Python/Node
	$(call play,asdf)

backup:      ## Back up installed packages/extensions/macOS defaults into the repo
	$(call play,backup)
