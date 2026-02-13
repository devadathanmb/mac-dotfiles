# fzf-brew for fish shell
#
# Command: fcui (Fuzzy Cask UnInstall)
# Purpose: Interactively select casks to uninstall using fzf
#
# Usage:
#   fcui             # Open fzf with installed casks (via `brew list --cask`)
#   fcui <query>     # Open fzf with query pre-filled
#
# Flow: fcui → __fzf_brew_run → __fzf_brew_select (shows fzf UI)

function fcui --description "Fuzzy brew uninstall (cask)"
    __fzf_brew_run uninstall cask $argv
end
