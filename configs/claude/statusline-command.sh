#!/usr/bin/env bash

# Statusline script for Claude Code. Reads a JSON payload from stdin (piped by
# the harness) and prints a formatted, colored status line to stdout.

input=$(cat)

cwd=""
model=""
remaining=""
effort=""
git_branch=""
fh_rem=""
sd_rem=""
fh_reset=""
sd_reset=""
cache_observed=""
cache_warm=""
cache_ratio=""
cache_expires=""

# Null-delimited reads via fd 3 avoid splitting on newlines inside field values
# (e.g. a cwd that contains a space is fine, but multi-line jq output would
# silently corrupt a plain IFS read). The jq outputs must stay in the same
# order as the variable list below.
_parse_input() {
    exec 3< <(printf '%s' "$input" | jq -j '
    def rem: if . == null then "" else ((100 - .) | floor | tostring) end;
    def pct: if . == null then "" else (. * 100 | floor | tostring) end;
    (.workspace.current_dir // .cwd // ""), "\u0000",
    (.model.display_name // ""), "\u0000",
    (.context_window.remaining_percentage // "" | tostring), "\u0000",
    (.effort.level // ""), "\u0000",
    (.rate_limits.five_hour.used_percentage | rem), "\u0000",
    (.rate_limits.seven_day.used_percentage | rem), "\u0000",
    (.rate_limits.five_hour.resets_at // "" | tostring), "\u0000",
    (.rate_limits.seven_day.resets_at // "" | tostring), "\u0000",
    (.prompt_cache.caching_observed // false | tostring), "\u0000",
    (.prompt_cache.warm // false | tostring), "\u0000",
    (.prompt_cache.hit_ratio | pct), "\u0000",
    (.prompt_cache.expires_at // "" | tostring), "\u0000"
  ' 2> /dev/null)
    local var
    for var in cwd model remaining effort fh_rem sd_rem fh_reset sd_reset \
        cache_observed cache_warm cache_ratio cache_expires; do
        IFS= read -r -d '' "$var" <&3 || true
    done
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

# Collapse a long path to "…/parent/leaf"; only applied when the bar is tight.
_collapse_cwd() {
    local leaf=${1##*/} parent=${1%/*} short
    parent=${parent##*/}
    short="…/${parent}/${leaf}"
    # Keep the original when collapsing wouldn't help (e.g. "/long-name")
    if [ "${#short}" -lt "${#1}" ]; then printf '%s' "$short"; else printf '%s' "$1"; fi
}

_git_branch() {
    local repo_dir=$1
    git -C "$repo_dir" rev-parse --git-dir > /dev/null 2>&1 || return
    # core.fsync=none: skip fsync on these read-only calls — safe, avoids syscall overhead
    git -C "$repo_dir" -c core.fsync=none symbolic-ref --short HEAD 2> /dev/null ||
        git -C "$repo_dir" rev-parse --short HEAD 2> /dev/null
}

# Appends "*" when the tree is dirty and ↑N/↓N when ahead/behind upstream.
# --no-optional-locks: never contend with a concurrent git command for the index.
_git_state() {
    local repo_dir=$1 dirty counts ahead behind marks=""
    dirty=$(git -C "$repo_dir" --no-optional-locks -c core.fsync=none status --porcelain 2> /dev/null | head -n 1)
    [ -n "$dirty" ] && marks+="*"
    # Fails when there is no upstream, which simply means no arrows
    if counts=$(git -C "$repo_dir" rev-list --left-right --count '@{u}...HEAD' 2> /dev/null); then
        read -r behind ahead <<< "$counts"
        [ "$ahead" -gt 0 ] && marks+=" ↑$ahead"
        [ "$behind" -gt 0 ] && marks+=" ↓$behind"
    fi
    printf '%s' "$marks"
}

if [ -n "$cwd" ]; then
    git_branch=$(_git_branch "$cwd")
    [ -n "$git_branch" ] && git_branch+=$(_git_state "$cwd")
fi

# Colors: GitHub Dark High Contrast (bright ANSI palette)
BLUE='\033[38;2;108;182;255m'    # #6cb6ff - bright blue   - path
GREEN='\033[38;2;38;205;77m'     # #26cd4d - bright green  - git branch / healthy gauge
MODEL='\033[38;2;240;184;150m'   # #f0b896 - soft peach    - model
YELLOW='\033[38;2;240;183;47m'   # #f0b72f - bright yellow - medium gauge
RED='\033[38;2;255;110;110m'     # #ff6e6e - bright red    - low gauge
DIMGRAY='\033[38;2;160;174;185m' # #a0aeb9 - mid gray      - brackets / labels / reset times
RESET='\033[0m'

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

# Gauge color for the session gauges (context, cache):
# >= 80 good, 50-79 medium, < 50 low.
_tier_color() {
    if [ "$1" -ge 80 ] 2> /dev/null; then
        echo "$GREEN"
    elif [ "$1" -ge 50 ] 2> /dev/null; then
        echo "$YELLOW"
    else
        echo "$RED"
    fi
}

# Subscription limits are stricter: > 50% remaining → green, > 20% → yellow,
# else red (danger).
_limit_color() {
    if [ "$1" -gt 50 ] 2> /dev/null; then
        echo "$GREEN"
    elif [ "$1" -gt 20 ] 2> /dev/null; then
        echo "$YELLOW"
    else
        echo "$RED"
    fi
}

# Build a usage block: "[label: <colored %>% | reset time]"
# Brackets, labels and reset time are dim; only the number is colored.
_usage_block() {
    local label=$1 rem=$2 reset_epoch=$3 reset_label=""
    [ -n "$reset_epoch" ] && reset_label=" | $(_fmt_reset "$reset_epoch")"
    printf "${DIMGRAY}[%s: $(_limit_color "$rem")%s%%${DIMGRAY}%s]${RESET}" "$label" "$rem" "$reset_label"
}

# Build the prompt cache block: "[Cache: <hit %> | time until cold]", or a red
# "[Cache: cold]" once the cached prefix has expired. Hidden when caching isn't
# reported (older Claude Code, or a provider that doesn't expose it).
_cache_block() {
    [ "$cache_observed" = "true" ] || return
    local secs=$((cache_expires - $(date +%s)))
    if [ "$cache_warm" != "true" ] || [ -z "$cache_expires" ] || [ "$secs" -le 0 ]; then
        printf '%s' "${DIMGRAY}[Cache: ${RED}cold${DIMGRAY}]${RESET}"
        return
    fi

    local left_label
    if [ "$secs" -ge 3600 ]; then
        left_label="$((secs / 3600))h"
    elif [ "$secs" -ge 60 ]; then
        left_label="$((secs / 60))m"
    else
        left_label="<1m"
    fi
    if [ -n "$cache_ratio" ]; then
        printf "${DIMGRAY}[Cache: $(_tier_color "$cache_ratio")%s%%${DIMGRAY} | %s]${RESET}" "$cache_ratio" "$left_label"
    else
        printf "${DIMGRAY}[Cache: %s]${RESET}" "$left_label"
    fi
}

# Visible width of a string with ANSI escapes removed.
_visible_len() {
    local plain
    plain=$(printf '%b' "$1" | sed $'s/\\x1b\\[[0-9;]*m//g')
    printf '%s' "${#plain}"
}

# Terminal width: the harness pipes stdio, so ask the controlling tty.
_term_cols() {
    local cols
    cols=$({ stty size < /dev/tty | awk '{print $2}'; } 2> /dev/null)
    [ -n "$cols" ] || cols=${COLUMNS:-}
    printf '%s' "$cols"
}

left=""
right=""

[ -n "$git_branch" ] && left+=" $(printf "${GREEN}%s${RESET}" "$git_branch")"
if [ -n "$model" ]; then
    if [ -n "$effort" ]; then
        effort_label="$(printf '%s' "${effort^}")"
        left+=" $(printf "${MODEL}[%s | %s]${RESET}" "$model" "$effort_label")"
    else
        left+=" $(printf "${MODEL}[%s]${RESET}" "$model")"
    fi
fi

# Strip decimal before integer comparison — bash arithmetic can't handle floats
if [ -n "$remaining" ]; then
    remaining_int=${remaining%.*}
    left+=" $(printf "${DIMGRAY}[CTX: $(_tier_color "$remaining_int")%s%%${DIMGRAY}]${RESET}" "$remaining_int")"
fi

cache_block=$(_cache_block)
[ -n "$cache_block" ] && left+=" $cache_block"

# 5-hour and 7-day subscription limits (absent for non-subscription auth)
if [ -n "$fh_rem" ] && [ -n "$sd_rem" ]; then
    right="$(_usage_block "5h" "$fh_rem" "$fh_reset") $(_usage_block "7d" "$sd_rem" "$sd_reset")"
fi

# Layout: path + branch/model/ctx/cache on the left, usage limits right-aligned.
# Leave a margin (the harness truncates near the edge). The path is collapsed
# only when everything else wouldn't fit; with an unknown width, fall back to
# a fixed length cap.
cols=$(_term_cols)
margin=5
right_len=$(_visible_len "$right")
left_len=$(_visible_len "$left")
if [ -n "$cols" ]; then
    avail=$((cols - margin - left_len - right_len - 1))
else
    avail=32
fi
if [ "${#short_cwd}" -gt "$avail" ] 2> /dev/null; then
    short_cwd=$(_collapse_cwd "$short_cwd")
fi
output="$(printf "${BLUE}%s${RESET}" "$short_cwd")$left"

if [ -n "$right" ]; then
    pad=1
    if [ -n "$cols" ]; then
        gap=$((cols - margin - $(_visible_len "$output") - right_len))
        [ "$gap" -ge 1 ] 2> /dev/null && pad=$gap
    fi
    # NBSP survives the harness's whitespace trimming
    output+="$(printf '%*s' "$pad" '' | sed 's/ /\xc2\xa0/g')$right"
fi

printf "%b" "$output"
