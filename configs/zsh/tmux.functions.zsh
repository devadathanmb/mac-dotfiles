#!/usr/bin/env zsh
#
__fzf_tmux_kill_session() {

  # Gather session names
  local sessions sel
  sessions=$(tmux list-sessions 2>/dev/null | awk -F: '{print $1}')
  if [[ -z $sessions ]]; then
    echo "No tmux sessions found." >&2
    return 1
  fi

  # Let user pick one
  sel=$(printf '%s\n' $sessions \
        | fzf --prompt="Kill tmux session> " \
              --height=40% --border) || return

  # Confirm and kill
  if [[ -n $sel ]]; then
    tmux kill-session -t "$sel" \
      && echo "Killed tmux session: $sel" \
      || echo "Failed to kill session: $sel" >&2
  fi
}

# Public wrapper
tmux-ks() { __fzf_tmux_kill_session "$@"; }
