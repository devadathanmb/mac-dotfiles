# fzf-brew for fish shell
#
# This is the core UI function that displays the fzf interface.
# It handles candidate generation (what to show in fzf) and UI configuration.
#
# Candidate sources:
#   - Install formula: `brew formulae` (all available formulae)
#   - Install cask:    `brew casks` (all available casks)
#   - Uninstall formula: `brew leaves` (formulae not depended on by others)
#   - Uninstall cask:    `brew list --cask` (installed casks)
#
# Note on brew leaves vs brew list --formula:
#   We use `brew leaves` for uninstall because it shows only formulae that are
#   not dependencies of other installed formulae. This prevents accidentally
#   uninstalling something that other packages need.
#
# Arguments:
#   $kind   - "formula" or "cask" (determines preview command and candidate source)
#   $action - "install" or "uninstall" (determines candidate source)
#   $argv[3..-1] - Query pre-fill (optional, passed as --query to fzf)

function __fzf_brew_select --argument-names kind action --description "Select brew items via fzf"
    # Fail fast if dependencies missing
    __fzf_brew_require; or return $status

    # Capture any additional args as query pre-fill
    set -l query $argv[3..-1]
    set -l candidates

    # Generate candidate list based on action and kind
    # We use different brew commands to get the appropriate list
    switch $action
        case install
            if test "$kind" = cask
                # brew casks = list all available casks in Homebrew
                set candidates (command brew casks)
            else
                # brew formulae = list all available formulae in Homebrew
                set candidates (command brew formulae)
            end
        case uninstall
            if test "$kind" = cask
                # brew list --cask = show only installed casks
                set candidates (command brew list --cask)
            else
                # brew leaves = installed formulae that aren't dependencies of others
                # Using leaves prevents uninstalling required dependencies
                set candidates (command brew leaves)
            end
        case '*'
            printf 'fzf-brew: unknown action %s\n' $action >&2
            return 2
    end

    # No candidates found (e.g., no casks installed)
    if test (count $candidates) -eq 0
        return 1
    end

    # Configure preview command based on kind
    # HOMEBREW_COLOR=true forces colored output even when piped
    set -l preview_cmd "HOMEBREW_COLOR=true brew info {}"
    set -l home_cmd "brew home {}"
    if test "$kind" = cask
        set preview_cmd "HOMEBREW_COLOR=true brew info --cask {}"
        set home_cmd "brew home --cask {}"
    end

    # Default fzf UI configuration (can be overridden by user variables)
    set -l preview_window "right:60%:wrap"
    if set -q FZF_BREW_PREVIEW_WINDOW
        set preview_window $FZF_BREW_PREVIEW_WINDOW
    end

    set -l height "40%"
    if set -q FZF_BREW_HEIGHT
        set height $FZF_BREW_HEIGHT
    end

    set -l home_bind "ctrl-o"
    if set -q FZF_BREW_HOME_BIND
        set home_bind $FZF_BREW_HOME_BIND
    end

    # Build fzf options
    # --multi = allow multiple selections (shift-tab to toggle)
    # --preview = show brew info in side panel
    # --bind = custom key bindings (home = open homepage in browser)
    set -l fzf_opts --multi --height $height --preview $preview_cmd --preview-window $preview_window
    set -l bind_cmd "$home_bind:execute-silent($home_cmd)"
    set -a fzf_opts --bind $bind_cmd

    # Add query pre-fill if user provided args (e.g., `fbi git` starts with "git")
    if test (count $query) -gt 0
        set -l query_str (string join ' ' $query)
        set -a fzf_opts --query $query_str
    end

    # Allow user to pass additional fzf options via environment variable
    if set -q FZF_BREW_FZF_OPTS
        set -a fzf_opts $FZF_BREW_FZF_OPTS
    end

    # Run fzf and capture selection
    # Pipe candidates to fzf via printf to handle newlines properly
    set -l selection (printf '%s\n' $candidates | command fzf $fzf_opts)
    set -l exit_status $status
    if test $exit_status -ne 0
        return $exit_status
    end

    # Return selected items (one per line)
    # Empty selection = user exited without choosing
    if test (count $selection) -eq 0
        return 0
    end

    printf '%s\n' $selection
end
