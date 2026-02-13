# fzf-brew for fish shell
#
# Command: fbi (Fuzzy Brew Install)
# Purpose: Interactively select formulae to install using fzf
#
# Usage:
#   fbi              # Open fzf with all available formulae
#   fbi <query>      # Open fzf with query pre-filled (e.g., `fbi git`)
#
# Flow: fbi → __fzf_brew_run → __fzf_brew_select (shows fzf UI)
#
# See README.md for more details.

function fbi --description "Fuzzy brew install (formula)"
    __fzf_brew_run install formula $argv
end
