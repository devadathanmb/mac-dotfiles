#!/usr/bin/env sh

if ! command -v fzf >/dev/null 2>&1; then
  tmux display-message "fzf is not installed"
  exit 1
fi

session=$(tmux display-message -p '#S')
current_target=$(tmux display-message -p '#S:#I')

windows=$(tmux list-windows -t "$session" \
  -F '#{window_index}: #{window_name}#{?window_active, (active),} [#{window_panes} panes] ::: #{session_name}:#{window_index}')

ordered_windows=$(printf '%s\n' "$windows" | awk -F ' ::: ' -v cur="$current_target" '
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
    --delimiter=' ::: ' \
    --with-nth=1 \
    --preview-window='right,65%,border-left' \
    --preview='tmux list-panes -t {2} -F "#{?pane_active,*, } #{pane_index}: #{pane_current_command}  #{pane_current_path}"; printf "\n--- active pane ---\n"; tmux capture-pane -p -e -S -40 -t {2}' \
    || true)

[ -z "$selected" ] && exit 0

target=$(printf '%s' "$selected" | awk -F ' ::: ' '{print $2}')
tmux select-window -t "$target"
