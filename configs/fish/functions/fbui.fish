# fzf-brew for fish shell
#
# Command: fbui (Fuzzy Brew UnInstall)
# Purpose: Interactively select formulae to uninstall using fzf
#
# Usage:
#   fbui             # Open fzf with installed formulae (via `brew leaves`)
#   fbui <query>     # Open fzf with query pre-filled
#
# Note: Uses `brew leaves` to show only formulae that are not dependencies
# of other installed packages. This prevents accidentally breaking dependencies.
#
# Flow: fbui → __fzf_brew_run → __fzf_brew_select (shows fzf UI)

function fbui --description "Fuzzy brew uninstall (formula)"
    __fzf_brew_run uninstall formula $argv
end
