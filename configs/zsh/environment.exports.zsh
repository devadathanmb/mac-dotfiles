#!/usr/bin/env zsh

# Environment Variables
export GPG_TTY=$(tty)
export PGTZ='Asia/Kolkata'
export PATH=$PATH:~/go/bin
export LANG=en_US.UTF-8
export KEYTIMEOUT=50
export EDITOR="nvim"

# PostgreSQL
export PATH="$(brew --prefix postgresql@17)/bin:$PATH"

# pnpm
export PNPM_HOME="$HOME/Library/pnpm"
case ":$PATH:" in
  *":$PNPM_HOME:"*) ;;
  *) export PATH="$PNPM_HOME:$PATH" ;;
esac
