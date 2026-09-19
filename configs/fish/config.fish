# The following lines were added by Docker Desktop to add commands to your PATH.
export PATH="$PATH:/Users/devadathan.mb/.docker/bin"
# End of Docker Desktop section.

# Fish behavior
set -g fish_greeting
fish_vi_key_bindings

# Load custom configuration
source ~/.config/fish/custom/env.fish
source ~/.config/fish/custom/options.fish
source ~/.config/fish/custom/aliases/general.fish
source ~/.config/fish/custom/functions/git.fish
source ~/.config/fish/custom/external_tool_configs.fish
