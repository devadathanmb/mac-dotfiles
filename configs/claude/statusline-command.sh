#!/usr/bin/env bash

input=$(cat)

cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // ""')
model=$(echo "$input" | jq -r '.model.display_name // ""')
remaining=$(echo "$input" | jq -r '.context_window.remaining_percentage // empty')

# Use ~/path format, but show full path when in $HOME itself
short_cwd=$(echo "$cwd" | sed "s|^$HOME|~|")
[ "$short_cwd" = "~" ] && short_cwd="$cwd"

# Get git branch (skip optional locks)
git_branch=""
if git -C "$cwd" rev-parse --git-dir > /dev/null 2>&1; then
  git_branch=$(git -C "$cwd" -c core.fsync=none symbolic-ref --short HEAD 2>/dev/null \
    || git -C "$cwd" rev-parse --short HEAD 2>/dev/null)
fi

# Fetch subscription usage limits from the Anthropic API.
# Results are cached to /tmp/claude_usage_cache for 60 seconds to avoid
# hammering the API on every status line refresh.
USAGE_CACHE="/tmp/claude_usage_cache"
usage_json=""

_load_usage() {
  # Use cache if it exists and is less than 60 seconds old
  if [ -f "$USAGE_CACHE" ] && \
     [ $(( $(date +%s) - $(date -r "$USAGE_CACHE" +%s 2>/dev/null || echo 0) )) -lt 300 ]; then
    usage_json=$(cat "$USAGE_CACHE")
    return
  fi

  # Get OAuth access token from macOS Keychain
  local creds
  creds=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null) || return
  local token
  token=$(printf '%s' "$creds" | jq -r '.claudeAiOauth.accessToken // empty' 2>/dev/null)
  [ -n "$token" ] || return

  # Fetch usage from Anthropic API
  local response
  response=$(curl -sf --max-time 5 \
    -H "Authorization: Bearer $token" \
    -H "anthropic-beta: oauth-2025-04-20" \
    -H "User-Agent: claude-code/2.0.32" \
    -H "Accept: application/json" \
    "https://api.anthropic.com/api/oauth/usage" 2>/dev/null) || return

  # Validate it looks like the expected shape before caching
  printf '%s' "$response" | jq -e '.five_hour.utilization, .seven_day.utilization' > /dev/null 2>&1 || return

  printf '%s' "$response" > "$USAGE_CACHE"
  usage_json="$response"
}

_load_usage

# Colors: GitHub Dark High Contrast (bright ANSI palette)
BLUE='\033[38;2;108;182;255m'   # #6cb6ff - bright blue   - path
GREEN='\033[38;2;38;205;77m'    # #26cd4d - bright green  - git branch
CYAN='\033[38;2;86;212;221m'    # #56d4dd - bright cyan   - model
YELLOW='\033[38;2;240;183;47m'  # #f0b72f - bright yellow - usage limits
RED='\033[38;2;255;110;110m'    # #ff6e6e - bright red    - low % warning
GRAY='\033[38;2;230;237;243m'   # #e6edf3 - bright white  - context
RESET='\033[0m'

output=""

# Directory
output+="$(printf "${BLUE}%s${RESET}" "$short_cwd")"

# Git branch
if [ -n "$git_branch" ]; then
  output+=" $(printf "${GREEN}%s${RESET}" "$git_branch")"
fi

# Model
if [ -n "$model" ]; then
  output+=" $(printf "${CYAN}[%s]${RESET}" "$model")"
fi

# Context remaining (red when <= 20%)
if [ -n "$remaining" ]; then
  remaining_int=${remaining%.*}
  if [ "$remaining_int" -le 20 ] 2>/dev/null; then
    output+=" $(printf "${RED}[ctx: %s%%]${RESET}" "$remaining_int")"
  else
    output+=" $(printf "${GRAY}[ctx: %s%%]${RESET}" "$remaining_int")"
  fi
fi

# 5-hour and 7-day subscription usage limits (omitted silently on error)
if [ -n "$usage_json" ]; then
  fh_util=$(printf '%s' "$usage_json" | jq -r '.five_hour.utilization // empty' 2>/dev/null)
  sd_util=$(printf '%s' "$usage_json" | jq -r '.seven_day.utilization // empty' 2>/dev/null)

  if [ -n "$fh_util" ] && [ -n "$sd_util" ]; then
    fh_rem=$(( 100 - ${fh_util%.*} ))
    sd_rem=$(( 100 - ${sd_util%.*} ))

    # Choose color: red if either value is <= 20%, otherwise yellow
    if [ "$fh_rem" -le 20 ] || [ "$sd_rem" -le 20 ] 2>/dev/null; then
      usage_color="$RED"
    else
      usage_color="$YELLOW"
    fi

    output+=" $(printf "${usage_color}[5h: %s%% | 7d: %s%%]${RESET}" "$fh_rem" "$sd_rem")"
  fi
fi

printf "%b" "$output"
