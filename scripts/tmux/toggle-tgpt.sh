#!/usr/bin/env bash

SESSION_NAME="tgpt_popup"

# If we are currently inside the popup session, detach from it
if [ "$(tmux display-message -p -F "#{session_name}")" = "$SESSION_NAME" ]; then
  tmux detach-client
else
  # Open the popup and create/attach to the dedicated tgpt session.
  # We turn off the status bar inside the popup to make it look cleaner.
  tmux display-popup -E -w 80% -h 80% -T "Quick AI (tgpt)" \
    "tmux new-session -A -s $SESSION_NAME 'tgpt -m' \; set-option status off"
fi
