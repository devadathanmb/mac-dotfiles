#!/usr/bin/env bash

# Statusline script for Claude Code. Reads a JSON payload from stdin (piped by
# the harness) and prints a formatted, colored status line to stdout.

input=$(cat)

cwd=""
model=""
remaining=""
effort=""
git_branch=""
usage_json=""
fh_rem=""
sd_rem=""
fh_reset=""
sd_reset=""

# Null-delimited reads via fd 3 avoid splitting on newlines inside field values
# (e.g. a cwd that contains a space is fine, but multi-line jq output would
# silently corrupt a plain IFS read).
_parse_input() {
    exec 3< <(printf '%s' "$input" | jq -j '
    (.workspace.current_dir // .cwd // ""), "\u0000",
    (.model.display_name // ""), "\u0000",
    (.context_window.remaining_percentage // "" | tostring), "\u0000",
    (.effort.level // ""), "\u0000"
  ' 2> /dev/null)
    IFS= read -r -d '' cwd <&3 || true
    IFS= read -r -d '' model <&3 || true
    IFS= read -r -d '' remaining <&3 || true
    IFS= read -r -d '' effort <&3 || true
    exec 3<&-
}

_parse_input

# Use ~/path format, but show full path when in $HOME itself
short_cwd="$cwd"
case "$cwd" in
    "$HOME")
        short_cwd="$cwd"
        ;;
    "$HOME"/*)
        short_cwd="~${cwd#"$HOME"}"
        ;;
esac

_git_branch() {
    local repo_dir=$1
    git -C "$repo_dir" rev-parse --git-dir > /dev/null 2>&1 || return
    # core.fsync=none: skip fsync on these read-only calls — safe, avoids syscall overhead
    git -C "$repo_dir" -c core.fsync=none symbolic-ref --short HEAD 2> /dev/null ||
        git -C "$repo_dir" rev-parse --short HEAD 2> /dev/null
}

[ -n "$cwd" ] && git_branch=$(_git_branch "$cwd")

# Subscription usage is fetched from the Anthropic API and cached locally.
# 3 min TTL: short enough to catch rate-limit changes, long enough to avoid
# hammering the API on every keypress.
USAGE_CACHE="/tmp/claude_usage_cache"
USAGE_CACHE_TTL=180
CURL_SUCCESS_LOG="/tmp/claude_usage_curl_success.log"
CURL_ERROR_LOG="/tmp/claude_usage_curl_error.log"

_usage_cache_is_fresh() {
    [ -f "$USAGE_CACHE" ] || return 1

    local now modified
    now=$(date +%s)
    modified=$(date -r "$USAGE_CACHE" +%s 2> /dev/null || echo 0)
    [ $((now - modified)) -lt "$USAGE_CACHE_TTL" ]
}

_load_usage() {
    if _usage_cache_is_fresh; then
        usage_json=$(< "$USAGE_CACHE")
        return
    fi

    local creds token response curl_exit curl_err
    # macOS Keychain: Claude Code stores OAuth credentials under this service name
    creds=$(security find-generic-password -s "Claude Code-credentials" -w 2> /dev/null) || return
    token=$(printf '%s' "$creds" | jq -r '.claudeAiOauth.accessToken // empty' 2> /dev/null)
    [ -n "$token" ] || return

    curl_err=$(mktemp)
    # Guarantee temp file cleanup on any exit path from this function
    trap 'rm -f "$curl_err"' RETURN

    response=$(curl -sf --max-time 5 \
        -H "Authorization: Bearer $token" \
        -H "anthropic-beta: oauth-2025-04-20" \
        -H "User-Agent: claude-code/2.0.32" \
        -H "Accept: application/json" \
        "https://api.anthropic.com/api/oauth/usage" 2> "$curl_err")
    curl_exit=$?

    if [ $curl_exit -ne 0 ]; then
        printf '[%s] curl failed (exit %s): %s\n' \
            "$(date -Iseconds)" "$curl_exit" "$(cat "$curl_err")" >> "$CURL_ERROR_LOG"
        return
    fi
    printf '[%s] curl succeeded: %s\n' "$(date -Iseconds)" "$response" >> "$CURL_SUCCESS_LOG"

    # Validate the response has the fields we need before caching
    printf '%s' "$response" | jq -e '.five_hour.utilization, .seven_day.utilization' > /dev/null 2>&1 || return

    printf '%s' "$response" > "$USAGE_CACHE"
    usage_json="$response"
}

_load_usage

# Colors: GitHub Dark High Contrast (bright ANSI palette)
BLUE='\033[38;2;108;182;255m'    # #6cb6ff - bright blue   - path
GREEN='\033[38;2;38;205;77m'     # #26cd4d - bright green  - git branch / 5h usage
CYAN='\033[38;2;86;212;221m'     # #56d4dd - bright cyan   - model
YELLOW='\033[38;2;240;183;47m'   # #f0b72f - bright yellow - 7d usage
RED='\033[38;2;255;110;110m'     # #ff6e6e - bright red    - >= 80% used / low ctx
GRAY='\033[38;2;215;222;228m'    # #d7dee4 - off-white     - usage labels
DIMGRAY='\033[38;2;160;174;185m' # #a0aeb9 - mid gray      - context
RESET='\033[0m'

# Same null-delimited read pattern as _parse_input — see comment there
_parse_usage() {
    exec 3< <(printf '%s' "$usage_json" | jq -j '
    ((100 - (.five_hour.utilization // 100)) | floor | tostring), "\u0000",
    ((100 - (.seven_day.utilization // 100)) | floor | tostring), "\u0000",
    (.five_hour.resets_at // ""), "\u0000",
    (.seven_day.resets_at // ""), "\u0000"
  ' 2> /dev/null)
    IFS= read -r -d '' fh_rem <&3 || true
    IFS= read -r -d '' sd_rem <&3 || true
    IFS= read -r -d '' fh_reset <&3 || true
    IFS= read -r -d '' sd_reset <&3 || true
    exec 3<&-
}

# macOS date -j rejects fractional seconds and colon-separated UTC offsets,
# so we normalise before parsing: strip subseconds, Z→+0000, +HH:MM→+HHMM.
_ts_to_epoch() {
    local normalised
    normalised=$(printf '%s' "$1" |
        sed 's/\.[0-9]*//; s/Z$/+0000/; s/+\([0-9][0-9]\):\([0-9][0-9]\)$/+\1\2/')
    date -j -f "%Y-%m-%dT%H:%M:%S%z" "$normalised" "+%s" 2> /dev/null
}

# Format a reset epoch into a human-readable label:
#   < 60 min  → "8m" / "45s"
#   same day  → "5:00pm"
#   other day → "Mar 13 12:30pm"
_fmt_reset() {
    local epoch=$1 now secs
    now=$(date +%s)
    secs=$((epoch - now))

    if [ "$secs" -le 0 ] 2> /dev/null; then
        echo "now"
        return
    fi

    if [ "$secs" -lt 3600 ]; then
        local m=$((secs / 60)) s=$((secs % 60))
        if [ "$m" -gt 0 ]; then echo "${m}m"; else echo "${s}s"; fi
        return
    fi

    local today reset_day
    today=$(date +%Y-%m-%d)
    reset_day=$(date -r "$epoch" +%Y-%m-%d 2> /dev/null)
    if [ "$reset_day" = "$today" ]; then
        date -r "$epoch" +"%l:%M%p" 2> /dev/null | sed 's/^ //; s/AM$/am/; s/PM$/pm/'
        return
    fi

    date -r "$epoch" +"%b %-d %-I:%M%p" 2> /dev/null | sed 's/AM$/am/; s/PM$/pm/'
}

# > 50% remaining → green, > 20% → yellow, else red (danger)
_pct_color() {
    local rem=$1
    if [ "$rem" -gt 50 ] 2> /dev/null; then
        echo "$GREEN"
    elif [ "$rem" -gt 20 ] 2> /dev/null; then
        echo "$YELLOW"
    else
        echo "$RED"
    fi
}

# Build a usage block: "[label: <colored %>% | RESET: time]"
# Labels and brackets are gray; only the number is colored.
_usage_block() {
    local label=$1 rem=$2 reset_ts=$3
    local pct_color reset_label=""
    pct_color=$(_pct_color "$rem")
    if [ -n "$reset_ts" ]; then
        local epoch
        epoch=$(_ts_to_epoch "$reset_ts" 2> /dev/null)
        [ -n "$epoch" ] && reset_label=" | RESET: $(_fmt_reset "$epoch")"
    fi
    printf "${GRAY}[%s: ${pct_color}%s%%${GRAY}%s]${RESET}" "$label" "$rem" "$reset_label"
}

output=""

output+="$(printf "${BLUE}%s${RESET}" "$short_cwd")"
[ -n "$git_branch" ] && output+=" $(printf "${GREEN}%s${RESET}" "$git_branch")"
if [ -n "$model" ]; then
    if [ -n "$effort" ]; then
        effort_label="$(printf '%s' "${effort^}")"
        output+=" $(printf "${CYAN}[%s | %s]${RESET}" "$model" "$effort_label")"
    else
        output+=" $(printf "${CYAN}[%s]${RESET}" "$model")"
    fi
fi

# Strip decimal before integer comparison — bash arithmetic can't handle floats
if [ -n "$remaining" ]; then
    remaining_int=${remaining%.*}
    if [ "$remaining_int" -le 20 ] 2> /dev/null; then
        output+=" $(printf "${RED}[CTX: %s%%]${RESET}" "$remaining_int")"
    else
        output+=" $(printf "${DIMGRAY}[CTX: %s%%]${RESET}" "$remaining_int")"
    fi
fi

# 5-hour and 7-day subscription usage limits
if [ -n "$usage_json" ]; then
    _parse_usage
    if [ -n "$fh_rem" ] && [ -n "$sd_rem" ]; then
        output+=" $(_usage_block "5h" "$fh_rem" "$fh_reset")"
        output+=" $(_usage_block "7d" "$sd_rem" "$sd_reset")"
    fi
fi

printf "%b" "$output"
