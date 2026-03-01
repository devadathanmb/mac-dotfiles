# Eza aliases
alias ls="eza --group-directories-first --icons=auto"
alias ll='ls -lh --git'
alias la="ll -a"
alias tree='ll --tree --level=2'

alias sof="source ~/.config/fish/config.fish && echo 'Sourced fish configs 🐟!'"

# Util aliases
alias lsa="ls -la"
alias lsl="ls -l"
alias lgit="lazygit"
alias ldocker="lazydocker"
alias down="cd ~/Downloads"
alias mv="mv -i"
alias brewup="echo 'Brewing...' && brew update && brew upgrade && brew cleanup && clear && echo 'Brew complete'"


# Vim Aliases
alias vim="nvim -u ~/.config/cvim/init.lua"
alias lvim="nvim -u ~/.config/nvim/init.lua"
alias nvim="nvim -u ~/.config/cvim/init.lua"
