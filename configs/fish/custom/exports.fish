# Environment Variables
set -gx GPG_TTY (tty)
set -gx PGTZ Asia/Kolkata
set -gx PATH $PATH ~/go/bin
set -gx LANG 'en_US.UTF-8'
set -gx KEYTIMEOUT 50
set -gx EDITOR nvim

# FZF
set -x FZF_DEFAULT_OPTS "--bind=tab:down,shift-tab:up,ctrl-space:toggle"

# PostgreSQL
set -gx PATH (brew --prefix postgresql@16)/bin $PATH

# Pnpm
set -x PNPM_HOME /Users/devadathanmb/Library/pnpm
if not contains $PNPM_HOME $PATH
    set -x PATH $PNPM_HOME $PATH
end

# Local bin
set -x LOCAL_BIN_PATH ~/.local/bin
if not contains $LOCAL_BIN_PATH $PATH
    set -x PATH $LOCAL_BIN_PATH $PATH
end
