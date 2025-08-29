#!/usr/bin/env zsh

# Environment Variables
export GPG_TTY=$(tty)
export PGTZ='Asia/Kolkata'
export PATH=$PATH:~/go/bin
export LANG=en_US.UTF-8
export KEYTIMEOUT=50
export EDITOR="nvim" 

# PostgreSQL
export PATH="$(brew --prefix postgresql@16)/bin:$PATH"

# fnm (Node Version Manager)
FNM_PATH="/Users/devadathanmb/Library/Application Support/fnm"
if [ -d "$FNM_PATH" ]; then
  export PATH="/Users/devadathanmb/Library/Application Support/fnm:$PATH"
  eval "`fnm env`"
  source ~/.fnm_completions.zsh
fi
eval "$(fnm env --use-on-cd)"

# pnpm
export PNPM_HOME="/Users/devadathanmb/Library/pnpm"
case ":$PATH:" in
  *":$PNPM_HOME:"*) ;;
  *) export PATH="$PNPM_HOME:$PATH" ;;
esac
