#!/usr/bin/env zsh

# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

# ZSH Configuration
set -o ignoreeof

# Load Zap Plugin Manager
[ -f "$HOME/.local/share/zap/zap.zsh" ] && source "$HOME/.local/share/zap/zap.zsh"

# Core Plugins
plug "zsh-users/zsh-autosuggestions"
plug "hlissner/zsh-autopair"
plug "zap-zsh/supercharge"
plug "zap-zsh/exa"
plug "chrishrb/zsh-kubectl"
plug "zap-zsh/vim"
# plug "kutsan/zsh-system-clipboard"
plug "zap-zsh/fzf"
plug "zap-zsh/completions"
plug "Aloxaf/fzf-tab"
plug "Freed-Wu/fzf-tab-source"
plug "wintermi/zsh-brew"
plug "zsh-users/zsh-history-substring-search"
plug "zsh-users/zsh-syntax-highlighting"
plug "romkatv/powerlevel10k"
plug "MichaelAquilina/zsh-you-should-use"
plug "junegunn/fzf-git.sh"
plug "thirteen37/fzf-brew"

# Load custom configs
plug ~/.config/zsh/init.zsh

# Initialize Tools
eval "$(zoxide init zsh)"

# Powerlevel10k Configuration
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

# Rsync fix for non-interactive shells
if [[ $- != *i* ]]; then
    return
fi

eval "$(atuin init zsh --disable-up-arrow)"
source "/Users/devadathanmb/.deno/env"
export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"

export PATH=$PATH:/Users/devadathanmb/.spicetify

# Added by Antigravity
export PATH="/Users/devadathanmb/.antigravity/antigravity/bin:$PATH"

# Amp CLI
export PATH="/Users/devadathanmb/.amp/bin:$PATH"
