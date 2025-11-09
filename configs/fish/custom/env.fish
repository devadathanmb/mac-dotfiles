# Environment Variables
set -gx GPG_TTY (tty)
set -gx PGTZ Asia/Kolkata
set -gx PATH $PATH ~/go/bin
set -gx LANG 'en_US.UTF-8'
set -gx KEYTIMEOUT 50
set -gx EDITOR nvim


# PostgreSQL
set -gx PATH "/opt/homebrew/opt/postgresql@17/bin" $PATH

# Pnpm
set -x _PNPM_HOME /Users/devadathanmb/Library/pnpm
if not contains $_PNPM_HOME $PATH
    set -x PATH $_PNPM_HOME $PATH
end

# Local bin
set -x _LOCAL_BIN_PATH ~/.local/bin
if not contains $_LOCAL_BIN_PATH $PATH
    set -x PATH $_LOCAL_BIN_PATH $PATH
end

# Spicetify
set -x _SPICETIFY_PATH ~/.spicetify
if not contains $_SPICETIFY_PATH $PATH
    set -x PATH $_SPICETIFY_PATH $PATH
end
