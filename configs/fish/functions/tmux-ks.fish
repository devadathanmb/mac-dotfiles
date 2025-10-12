function tmux-ks
    # Gather session names
    set sessions (tmux list-sessions 2>/dev/null | awk -F: '{print $1}')
    if test -z "$sessions"
        echo "No tmux sessions found." >&2
        return 1
    end

    # Let user pick one
    set sel (printf '%s\n' $sessions | fzf --prompt="Kill tmux session> " --height=40% --border)
    or return

    # Confirm and kill
    if test -n "$sel"
        if tmux kill-session -t "$sel"
            echo "Killed tmux session: $sel"
        else
            echo "Failed to kill session: $sel" >&2
        end
    end
end
