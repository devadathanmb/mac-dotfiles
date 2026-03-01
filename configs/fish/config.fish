# No greeting
set fish_greeting


if status is-interactive
    atuin init fish | source
end


# Enable vim mode
fish_vi_key_bindings

# Source stuff
source ~/.config/fish/custom/options.fish
source ~/.config/fish/custom/aliases/init.fish
source ~/.config/fish/custom/functions/init.fish
source ~/.config/fish/custom/env.fish
source ~/.config/fish/custom/external_tool_configs.fish

# Init zoxide
zoxide init fish | source

# Created by `pipx` on 2026-02-28 12:47:03
set PATH $PATH /Users/devadathanmb/Library/Python/3.9/bin
