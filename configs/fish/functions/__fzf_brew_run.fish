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

    # Build the final brew command once so interactive shells can inject the
    # exact command line into the prompt before execution.
    set -l brew_args brew
    switch $action
        case install
            if test "$kind" = cask
                set -a brew_args install --cask $selection
            else
                set -a brew_args install $selection
            end
        case uninstall
            if test "$kind" = cask
                set -a brew_args uninstall --cask $selection
            else
                set -a brew_args uninstall $selection
            end
    end

    # In interactive fish sessions, replace the prompt buffer so the user sees
    # the expanded brew command as the command being executed.
    if status is-interactive
        set -l brew_cmd (string join -- ' ' (string escape --style=script -- $brew_args))
        commandline -r $brew_cmd
        commandline -f repaint execute
        return 0
    end

    # Non-interactive sessions (tests, scripts) cannot edit the command line,
    # so execute directly. We use 'command' to bypass shell aliases/functions.
    command $brew_args
end
