#!/usr/bin/env zsh

# Key Bindings Configuration
# bindkey "^d" fzf-cd-widget
bindkey '^X' create_completion
bindkey "^o" 'nvim $(fzf)^M'
bindkey '^[[P' delete-char
bindkey "^p" up-line-or-beginning-search
bindkey "^n" down-line-or-beginning-search
bindkey "^k" up-line-or-beginning-search
bindkey "^j" down-line-or-beginning-search
bindkey "^a" beginning-of-line
bindkey "^e" end-of-line
bindkey -r "^u"
