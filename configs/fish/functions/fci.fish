# fzf-brew for fish shell
#
# Command: fci (Fuzzy Cask Install)
# Purpose: Interactively select casks to install using fzf
#
# Usage:
#   fci              # Open fzf with all available casks
#   fci <query>      # Open fzf with query pre-filled (e.g., `fci chrome`)
#
# Flow: fci → __fzf_brew_run → __fzf_brew_select (shows fzf UI)

function fci --description "Fuzzy brew install (cask)"
    __fzf_brew_run install cask $argv
end
