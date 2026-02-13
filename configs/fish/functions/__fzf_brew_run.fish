# fzf-brew for fish shell
#
# This is the main execution function that runs after user selects items in fzf.
# It receives the selection and runs the appropriate brew command.
#
# Flow: Public fn (fbi/fbui/fci/fcui) → __fzf_brew_select (shows fzf UI) → 
#       __fzf_brew_run (this fn, executes brew command)
#
# Arguments:
#   $action - "install" or "uninstall"
#   $kind   - "formula" or "cask"
#   $argv[3..-1] - Additional args passed through (query pre-fill)

function __fzf_brew_run --argument-names action kind --description "Run brew action from fzf selection"
    # Get user selection from fzf. This is the main UI function.
    # If user cancels (Ctrl-C/Esc), fzf returns non-zero status and we exit early.
    set -l selection (__fzf_brew_select $kind $action $argv[3..-1])
    or return $status

    # Empty selection means user exited fzf without choosing anything
    # This is a successful no-op, not an error
    if test (count $selection) -eq 0
        return 0
    end

    # Execute the appropriate brew command based on action and kind.
    # We use 'command' to bypass any shell aliases/functions.
    switch $action
        case install
            if test "$kind" = cask
                command brew install --cask $selection
            else
                command brew install $selection
            end
        case uninstall
            if test "$kind" = cask
                command brew uninstall --cask $selection
            else
                command brew uninstall $selection
            end
    end
end
