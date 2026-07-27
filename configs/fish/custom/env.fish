# Environment variables
if status is-interactive
    set -gx GPG_TTY (tty)
end
set -gx FZF_DEFAULT_OPTS "--bind=tab:down,shift-tab:up,ctrl-space:toggle,ctrl-u:preview-up,ctrl-d:preview-down --height=50%"
set -gx PGTZ Asia/Kolkata
set -gx LANG en_US.UTF-8
set -gx KEYTIMEOUT 50
set -gx EDITOR nvim
set -gx PNPM_HOME "$HOME/Library/pnpm"

# PATH entries are kept global so sourcing this file does not persist universal variables.
fish_add_path --global --path --prepend \
    /opt/homebrew/opt/postgresql@17/bin \
    $PNPM_HOME \
    ~/.local/bin \
    ~/.spicetify \
    ~/.amp/bin \
    ~/.antigravity/antigravity/bin \
    ~/.bun/bin
fish_add_path --global --path --append \
    ~/go/bin \
    ~/Library/Python/3.9/bin
