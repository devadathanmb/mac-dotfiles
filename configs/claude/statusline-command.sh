#!/usr/bin/env bash
# shellcheck disable=SC2154 # JSON fields are assigned by name in _parse_input

# Statusline script for Claude Code. Reads a JSON payload from stdin (piped by
# the harness) and prints a two-line, colored status line to stdout:
#
#   ◆ model · effort │ ctx bar │ cache │ cost │ duration     5h  38% · 8:40pm
#   ⎇ branch │ +lines/−lines │ path │ PR │ worktree/agent      7d  72% · Oct 13 2:30am
#
# Subscription limits sit right-aligned, one per line, showing what's left,
# colored by burn rate. Context shows what's used, so its bar fills up.

# ${#var} must count characters, not bytes, for the width math below
export LC_ALL=en_US.UTF-8

input=$(cat)
now=$(date +%s)

# Null-delimited reads via fd 3 avoid splitting on newlines inside field values
# (multi-line jq output would silently corrupt a plain IFS read). The jq
# outputs must stay in the same order as the variable list below.
_parse_input() {
    exec 3< <(printf '%s' "$input" | jq -j '
    def s: if . == null then "" else tostring end;
    def int: if . == null then "" else (floor | tostring) end;
    def pct: if . == null then "" else (. * 100 | floor | tostring) end;
    (.workspace.current_dir // .cwd | s), "\u0000",
    (.model.display_name | s), "\u0000",
    (.effort.level | s), "\u0000",
    (.fast_mode // false | s), "\u0000",
    (.vim.mode | s), "\u0000",
    (.context_window.used_percentage | int), "\u0000",
    (.context_window.context_window_size | int), "\u0000",
    (.rate_limits.five_hour.used_percentage | int), "\u0000",
    (.rate_limits.five_hour.resets_at | s), "\u0000",
    (.rate_limits.seven_day.used_percentage | int), "\u0000",
    (.rate_limits.seven_day.resets_at | s), "\u0000",
    (.rate_limits.spend_limit.used_percentage | int), "\u0000",
    (.rate_limits.spend_limit.resets_at | s), "\u0000",
    (.prompt_cache.caching_observed // false | s), "\u0000",
    (.prompt_cache.warm // false | s), "\u0000",
    (.prompt_cache.hit_ratio | pct), "\u0000",
    (.prompt_cache.expires_at | s), "\u0000",
    (.prompt_cache.last_miss_at | s), "\u0000",
    (.prompt_cache.last_miss_cause.causes[0]? | s), "\u0000",
    (.cost.total_cost_usd | s), "\u0000",
    (.cost.total_duration_ms // 0 | int), "\u0000",
    (.cost.total_lines_added // 0 | s), "\u0000",
    (.cost.total_lines_removed // 0 | s), "\u0000",
    (.pr.number | s), "\u0000",
    (.pr.url | s), "\u0000",
    (.pr.review_state | s), "\u0000",
    (.worktree.name // .workspace.git_worktree | s), "\u0000",
    (.agent.name | s), "\u0000"
  ' 2> /dev/null)
    local var
    for var in cwd model effort fast_mode vim_mode ctx_used ctx_size \
        fh_used fh_reset sd_used sd_reset sp_used sp_reset \
        cache_observed cache_warm cache_ratio cache_expires miss_at miss_cause \
        cost duration_ms lines_add lines_del pr_num pr_url pr_state worktree agent; do
        IFS= read -r -d '' "$var" <&3 || true
    done
    exec 3<&-
}

_parse_input

# Colors, after kcchien/claude-code-statusline. Real escape bytes, so output is
# printed with %s and backslashes in paths or branch names are never interpreted.
BRAND=$'\e[38;2;114;102;234m'   # #7266ea - Anthropic purple ◆ / PR
CYAN=$'\e[38;2;86;212;221m'     # #56d4dd - model
BLUE=$'\e[38;2;108;182;255m'    # #6cb6ff - path
GREEN=$'\e[38;2;46;204;113m'    # #2ecc71 - healthy / lines added
YELLOW=$'\e[38;2;241;196;15m'   # #f1c40f - warning / cost / worktree
ORANGE=$'\e[38;2;236;126;34m'   # #ec7e22 - xhigh effort
RED=$'\e[38;2;231;76;60m'       # #e74c3c - danger / lines removed
GRAY=$'\e[38;2;160;174;185m'    # #a0aeb9 - branch / labels / reset times
FAINT=$'\e[38;2;60;60;60m'      # #3c3c3c - empty bar cells
SEPGRAY=$'\e[38;2;90;96;104m'   # #5a6068 - separators
RESET=$'\e[0m'
SEP=" ${SEPGRAY}|${RESET} "

# Ten-step green → yellow → orange → red ramp shared by the bar and percentages
RAMP_R=(46 116 186 241 239 236 233 231 211 192)
RAMP_G=(204 195 186 196 161 126 101 76 66 57)
RAMP_B=(113 89 64 15 24 34 44 60 50 43)

# --- formatting helpers ------------------------------------------------------

# Format a reset epoch: "8m" within the hour, "5:00pm" today, else "Mar 13 12:30pm"
_fmt_reset() {
    local epoch=$1 secs=$(($1 - now)) fmt="%b %-d %-I:%M%p"
    if [ "$secs" -le 0 ]; then
        printf 'now'
        return
    elif [ "$secs" -lt 3600 ]; then
        printf '%sm' "$((secs / 60))"
        return
    fi
    [ "$(date -r "$epoch" +%F)" = "$(date +%F)" ] && fmt="%-I:%M%p"
    date -r "$epoch" +"$fmt" | sed 's/AM$/am/; s/PM$/pm/'
}

# Seconds → "2h" / "45m" / "<1m"
_fmt_duration() {
    local secs=$1
    if [ "$secs" -ge 3600 ]; then
        printf '%sh' "$((secs / 3600))"
    elif [ "$secs" -ge 60 ]; then
        printf '%sm' "$((secs / 60))"
    else
        printf '<1m'
    fi
}

# Seconds → "1h12m" / "12m5s" / "40s"
_fmt_elapsed() {
    local secs=$1
    if [ "$secs" -ge 3600 ]; then
        printf '%dh%dm' "$((secs / 3600))" "$((secs % 3600 / 60))"
    elif [ "$secs" -ge 60 ]; then
        printf '%dm%ds' "$((secs / 60))" "$((secs % 60))"
    else
        printf '%ds' "$secs"
    fi
}

# 1234567 → "1.2M", 102400 → "102k"
_fmt_tokens() {
    local n=$1
    if [ "$n" -ge 1000000 ]; then
        printf '%d.%dM' "$((n / 1000000))" "$((n % 1000000 / 100000))"
    elif [ "$n" -ge 1000 ]; then
        printf '%dk' "$((n / 1000))"
    else
        printf '%d' "$n"
    fi
}

# Ramp color for a 0-100 position.
_ramp() {
    local i=$(($1 / 10))
    [ "$i" -gt 9 ] && i=9
    [ "$i" -lt 0 ] && i=0
    printf '\e[38;2;%d;%d;%dm' "${RAMP_R[i]}" "${RAMP_G[i]}" "${RAMP_B[i]}"
}

# Solid block bar: each filled cell takes the ramp color of its position, so a
# fuller bar visibly runs into orange and red. Empty cells are faint.
_bar() {
    local used=$1 width=10 i filled out=""
    filled=$(((used * width + 50) / 100))
    [ "$used" -gt 0 ] && [ "$filled" -eq 0 ] && filled=1
    [ "$filled" -gt "$width" ] && filled=$width
    for ((i = 0; i < width; i++)); do
        if [ "$i" -lt "$filled" ]; then
            out+="$(_ramp $((i * 10)))█"
        else
            out+="${FAINT}░"
        fi
    done
    printf '%s' "$out$RESET"
}

# Color for a limit by burn rate: compare usage to how much of the window has
# elapsed, so 60% used with an hour left is fine but 30% after ten minutes is not.
_pace_color() {
    local used=$1 reset=$2 window=$3 pace
    if [ "$used" -ge 90 ]; then
        printf '%s' "$RED"
        return
    elif [ -z "$reset" ]; then
        _ramp "$used"
        return
    fi
    pace=$(((window - (reset - now)) * 100 / window))
    if [ "$used" -gt $((pace + 20)) ]; then
        printf '%s' "$RED"
    elif [ "$used" -gt $((pace + 5)) ] || [ "$used" -ge 75 ]; then
        printf '%s' "$YELLOW"
    else
        printf '%s' "$GREEN"
    fi
}

# Visible width with SGR colors and OSC 8 links removed.
_visible_len() {
    local plain
    plain=$(printf '%s' "$1" | sed -E $'s/\e\\[[0-9;]*m//g; s/\e\\]8;;[^\a]*\a//g')
    printf '%s' "${#plain}"
}

# N non-breaking spaces; plain spaces get trimmed by the harness.
_nbsp() { printf '%*s' "$1" '' | sed 's/ /\xc2\xa0/g'; }

# --- git (cached) --------------------------------------------------------------

# Branch name, "*" when dirty, ↑N/↓N against upstream. --no-optional-locks keeps
# us from contending with a concurrent git command for the index.
_git_info() {
    local dir=$1 branch marks="" counts ahead behind
    branch=$(git -C "$dir" symbolic-ref --short HEAD 2> /dev/null ||
        git -C "$dir" rev-parse --short HEAD 2> /dev/null) || return
    [ -n "$(git -C "$dir" --no-optional-locks status --porcelain 2> /dev/null | head -n 1)" ] && marks+="*"
    if counts=$(git -C "$dir" rev-list --left-right --count '@{u}...HEAD' 2> /dev/null); then
        read -r behind ahead <<< "$counts"
        [ "$ahead" -gt 0 ] && marks+=" ↑$ahead"
        [ "$behind" -gt 0 ] && marks+=" ↓$behind"
    fi
    printf '%s' "$branch$marks"
}

# The refresh timer re-runs us every few seconds; `git status` is the slow part
# in big repos, so reuse the result for 5s per directory.
_git_cached() {
    local dir=$1 file
    file="${TMPDIR:-/tmp}/claude-statusline-git-$(printf '%s' "$dir" | md5 -q)"
    if [ -f "$file" ] && [ $((now - $(stat -f %m "$file"))) -lt 5 ]; then
        cat "$file"
    else
        _git_info "$dir" | tee "$file"
    fi
}

# --- line 1: model, context, cache, cost, duration -----------------------------

case "$effort" in
    high) effort_color=$YELLOW ;;
    xhigh) effort_color=$ORANGE ;;
    max) effort_color=$RED ;;
    *) effort_color=$GRAY ;;
esac
model_seg=""
[ -n "$model" ] && model_seg="${BRAND}◆${RESET} ${CYAN}${model}${RESET}"
[ -n "$effort" ] && model_seg+=" ${GRAY}·${RESET} ${effort_color}${effort}${RESET}"
[ "$fast_mode" = "true" ] && model_seg+=" ${YELLOW}⚡${RESET}"
[ -n "$vim_mode" ] && model_seg+=" ${GRAY}[${vim_mode}]${RESET}"

ctx_seg="" ctx_tokens=""
if [ -n "$ctx_used" ]; then
    ctx_seg="${SEP}$(_bar "$ctx_used") $(_ramp "$ctx_used")${ctx_used}%${RESET}"
    if [ "${ctx_size:-0}" -gt 0 ]; then
        ctx_tokens=" ${GRAY}$(_fmt_tokens $((ctx_size * ctx_used / 100)))/$(_fmt_tokens "$ctx_size")${RESET}"
    fi
fi

# Cache: hit ratio and time until cold; red "cold" once expired. A miss within
# the last two minutes shows its cause so you can see what broke the prefix.
cache_seg="" cache_miss=""
if [ "$cache_observed" = "true" ]; then
    cache_seg="${SEP}${GRAY}cache${RESET}"
    secs=$((${cache_expires:-0} - now))
    if [ "$cache_warm" != "true" ] || [ "$secs" -le 0 ]; then
        cache_seg+=" ${RED}cold${RESET}"
    else
        # Hit ratio is "higher is better", so invert it onto the ramp
        [ -n "$cache_ratio" ] && cache_seg+=" $(_ramp $((100 - cache_ratio)))${cache_ratio}%${RESET}"
        cache_seg+=" ${GRAY}· $(_fmt_duration "$secs")${RESET}"
    fi
    if [ -n "$miss_cause" ] && [ $((now - ${miss_at:-0})) -lt 120 ]; then
        cache_miss=" ${YELLOW}miss: ${miss_cause}${RESET}"
    fi
fi

cost_seg=""
if [ -n "$cost" ]; then
    cost_fmt=$(printf '%.2f' "$cost")
    if [ "$cost_fmt" != "0.00" ]; then
        cost_color=$YELLOW
        [ "${cost_fmt%%.*}" -ge 10 ] && cost_color=$RED
        cost_seg="${SEP}${cost_color}\$${cost_fmt}${RESET}"
    fi
fi

time_seg=""
[ "${duration_ms:-0}" -ge 1000 ] && time_seg="${SEP}${GRAY}$(_fmt_elapsed $((duration_ms / 1000)))${RESET}"

# Line 1 at a detail level: 0 = everything, 1 = no duration, 2 = no cost,
# 3 = no miss cause, 4 = no token counts.
_line1() {
    local level=$1
    printf '%s' "$model_seg$ctx_seg"
    [ "$level" -lt 4 ] && printf '%s' "$ctx_tokens"
    printf '%s' "$cache_seg"
    [ "$level" -lt 3 ] && printf '%s' "$cache_miss"
    [ "$level" -lt 2 ] && printf '%s' "$cost_seg"
    [ "$level" -lt 1 ] && printf '%s' "$time_seg"
    return 0
}

# --- line 2: branch, lines changed, path, PR, worktree/agent --------------------

path="$cwd"
case "$cwd" in "$HOME"/*) path="~${cwd#"$HOME"}" ;; esac

# "…/parent/leaf", unless that isn't actually shorter
_collapse_path() {
    local leaf=${1##*/} parent=${1%/*} short
    short="…/${parent##*/}/${leaf}"
    if [ "${#short}" -lt "${#1}" ]; then printf '%s' "$short"; else printf '%s' "$1"; fi
}

git_info=""
[ -n "$cwd" ] && git_info=$(_git_cached "$cwd")

l2_head=""
[ -n "$git_info" ] && l2_head="${GRAY}⎇ ${git_info}${RESET}${SEP}"
if [ "$lines_add" != 0 ] || [ "$lines_del" != 0 ]; then
    l2_head+="${GREEN}+${lines_add}${RESET}${GRAY}/${RESET}${RED}−${lines_del}${RESET}${SEP}"
fi

l2_tail=""
if [ -n "$pr_num" ]; then
    case "$pr_state" in
        approved) pr_mark=" ${GREEN}✓" ;;
        changes_requested) pr_mark=" ${RED}✗" ;;
        pending | draft) pr_mark=" ${GRAY}◌" ;;
        *) pr_mark="" ;;
    esac
    # OSC 8 hyperlink: Cmd+click opens the PR
    l2_tail+="${SEP}"$'\e]8;;'"${pr_url}"$'\a'"${BRAND}#${pr_num}"$'\e]8;;\a'"${pr_mark}${RESET}"
fi
[ -n "$worktree" ] && l2_tail+="${SEP}${YELLOW}⚙ ${worktree}${RESET}"
[ -n "$agent" ] && l2_tail+="${SEP}${YELLOW}⚙ ${agent}${RESET}"

_line2() { printf '%s' "$l2_head${BLUE}$1${RESET}$l2_tail"; }

# --- right column: usage limits --------------------------------------------------

# One limit per line, so at most two; a gateway spend limit takes a free slot.
limits=()
[ -n "$fh_used" ] && limits+=("5h|$fh_used|$fh_reset|18000")
[ -n "$sd_used" ] && limits+=("7d|$sd_used|$sd_reset|604800")
[ -n "$sp_used" ] && limits+=("spend|$sp_used|$sp_reset|2592000")

# "spend" is wider than "5h"/"7d"; only widen the label column when it shows
label_w=2
[[ " ${limits[*]:0:2}" == *" spend|"* ]] && label_w=5

# "5h  38% · 8:40pm" for limit $1; the reset time is dropped when $2 is "short".
_limit() {
    local spec=${limits[$1]:-} mode=$2 label used reset window rem color out
    [ -n "$spec" ] || return
    IFS='|' read -r label used reset window <<< "$spec"
    rem=$((used > 100 ? 0 : 100 - used))
    color=$(_pace_color "$used" "$reset" "$window")
    out="${GRAY}$(printf "%-${label_w}s" "$label")${RESET} ${color}$(printf '%3s' "$rem")%${RESET}"
    [ -n "$reset" ] && [ "$mode" != short ] && out+=" ${GRAY}· $(_fmt_reset "$reset")${RESET}"
    printf '%s' "$out"
}

# Sets r1/r2 for a mode, padding the narrower one so both line up.
_build_right() {
    local w1 w2
    r1=$(_limit 0 "$1")
    r2=$(_limit 1 "$1")
    [ -n "$r1" ] && [ -n "$r2" ] || return
    w1=$(_visible_len "$r1")
    w2=$(_visible_len "$r2")
    if [ "$w1" -lt "$w2" ]; then r1+=$(_nbsp $((w2 - w1))); else r2+=$(_nbsp $((w1 - w2))); fi
}

# --- layout --------------------------------------------------------------------

# The harness sets COLUMNS; stdio is piped so tty probing is a fallback only.
cols=${COLUMNS:-}
[ "$cols" -gt 0 ] 2> /dev/null || cols=$({ stty size < /dev/tty | awk '{print $2}'; } 2> /dev/null)
[ "$cols" -gt 0 ] 2> /dev/null || cols=""
margin=4

_fits() { [ -z "$cols" ] || [ $(($(_visible_len "$1") + $(_visible_len "$2") + 2 + margin)) -le "$cols" ]; }

# Right-align $2 after $1 with NBSP padding; a fixed gap when width is unknown.
_join() {
    local pad=2
    [ -n "$cols" ] && pad=$((cols - margin - $(_visible_len "$1") - $(_visible_len "$2")))
    [ "$pad" -lt 2 ] && pad=2
    printf '%s' "$1"
    [ -n "$2" ] && printf '%s%s' "$(_nbsp "$pad")" "$2"
}

# Shed detail until both lines fit: drop duration and cost and collapse the
# path, then reset times, then the miss cause and token counts.
_build_right full
level=0
while [ "$level" -lt 2 ] && ! _fits "$(_line1 "$level")" "$r1"; do
    level=$((level + 1))
done
l2=$(_line2 "$path")
_fits "$l2" "$r2" || l2=$(_line2 "$(_collapse_path "$path")")
if ! _fits "$(_line1 "$level")" "$r1" || ! _fits "$l2" "$r2"; then
    _build_right short
fi
while [ "$level" -lt 4 ] && ! _fits "$(_line1 "$level")" "$r1"; do
    level=$((level + 1))
done

# Trailing spacer row separates us from the harness footer. Whitespace-only rows
# (NBSP included) get dropped, so use the braille blank U+2800, which renders
# empty but isn't whitespace.
printf '%s\n%s\n%s' "$(_join "$(_line1 "$level")" "$r1")" "$(_join "$l2" "$r2")" $'\u2800'
