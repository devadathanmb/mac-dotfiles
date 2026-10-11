#!/usr/bin/env sh

if ! command -v fzf > /dev/null 2>&1; then
    tmux display-message "fzf is not installed"
    exit 1
fi

session=$(tmux display-message -p '#S')
current_target=$(tmux display-message -p '#S:#I')

windows=$(tmux list-windows -t "$session" \
    -F "#{window_index}: #{window_name}#{?window_active, (active),} [#{window_panes} panes]$(printf '\t')#{session_name}:#{window_index}")

ordered_windows=$(printf '%s\n' "$windows" | awk -F '\t' -v cur="$current_target" '
  $2 == cur { current = $0; next }
  { rest = rest $0 "\n" }
  END {
    if (current != "") print current
    printf "%s", rest
  }
')

selected=$(printf '%s\n' "$ordered_windows" | fzf \
    --prompt='window> ' \
    --layout=reverse \
    --height=100% \
    --border \
    --color='bg:#0A0C10,bg+:#161b22,fg:#c9d1d9,fg+:#ffffff,hl:#58a6ff,hl+:#79c0ff,info:#58a6ff,prompt:#58a6ff,pointer:#3fb950,marker:#d29922,spinner:#58a6ff,header:#6e7681,border:#30363d,preview-border:#30363d,preview-bg:#0A0C10,separator:#30363d,scrollbar:#30363d,gutter:#0A0C10,query:#c9d1d9' \
    --delimiter='\t' \
    --with-nth=1 \
    --preview-window='right,65%,border-left' \
    --preview='tmux list-panes -t {2} -F "#{?pane_active,*, } #{pane_index}: #{pane_current_command}  #{pane_current_path}"; printf "\n--- active pane ---\n"; tmux capture-pane -p -e -S -40 -t {2}' ||
    true)

[ -z "$selected" ] && exit 0

target=$(printf '%s' "$selected" | awk -F '\t' '{print $2}')
tmux select-window -t "$target"
