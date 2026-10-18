#!/usr/bin/env bash
# shellcheck disable=SC2154 # JSON fields are assigned by name in _parse_input

# Statusline script for Claude Code. Reads a JSON payload from stdin (piped by
# the harness) and prints a two-line status line. Preview and test changes with
# the tools beside this file; see README.md.
#
#   ◆ Opus 5.5 · medium ⏐ ━━━━──────── 34%  340k/1M ⏐ cache 92% 4m      5h ━━━━━─────  35%      3h12m
#   ~/repos/revue ⏐ 󰘬 main* ↑1 ⏐ +120 −30 ⏐ #42 ✓                     7d ━━━━──────  12% Fri 6:45am
#
# Design: everything sits on a neutral grey scale and lavender is the only
# identity color. Limits carry a green/amber/red burn-rate color; elsewhere
# amber and red appear only when a threshold is crossed. Hierarchy: model,
# repo and context % in the primary tone; branch, tokens and cost muted;
# labels, times and separators faint.
#
# Must run under macOS /bin/bash 3.2: no \u escapes (glyphs are literal), no
# associative arrays. Every glyph must be single-width, since widths are
# counted in characters; a wide one (e.g. ⚡) overflows the line and the
# harness truncates the right column.

# ${#var} must count characters, not bytes, for the width math below
export LC_ALL=en_US.UTF-8
shopt -s extglob

if ! command -v jq > /dev/null; then
    printf 'statusline: jq not found'
    exit 0
fi

input=$(cat)
# STATUSLINE_NOW pins the clock so ./preview renders are reproducible
now=${STATUSLINE_NOW:-$(date +%s)}

# Dev preview (see README.md): sessions started with STATUSLINE_DEV=1 merge the
# mock written by ./use over the real payload. "+N" strings become now+N, so
# countdowns stay live.
STATUSLINE_MOCK=${STATUSLINE_MOCK:-${TMPDIR:-/tmp}/claude-statusline-mock.json}
if [ -n "${STATUSLINE_DEV:-}" ] && [ -f "$STATUSLINE_MOCK" ]; then
    input=$(jq -s --argjson now "$now" '
      .[0] * (.[1] | walk(if type == "string" and test("^\\+[0-9]+$")
                          then $now + (.[1:] | tonumber) else . end))
    ' <(printf '%s' "$input") "$STATUSLINE_MOCK" 2> /dev/null || printf '%s' "$input")
fi

# --- input ---------------------------------------------------------------------

# Null-delimited reads via fd 3 avoid splitting on newlines inside field values
# (multi-line jq output would silently corrupt a plain IFS read). The jq
# outputs must stay in the same order as the variable list below. Numbers are
# floored to integers and timestamps normalized to epoch seconds here, so the
# arithmetic below only ever sees digits or "".
_parse_input() {
    exec 3< <(printf '%s' "$input" | jq -j '
    def s: if . == null then "" else tostring end;
    def int: if type == "number" then (floor | tostring) else "" end;
    def pct: if type == "number" then (. * 100 | floor | tostring) else "" end;
    def epoch: if type == "number" then (floor | tostring)
      elif type == "string" then ((sub("\\.[0-9]+"; "") | fromdateiso8601 | tostring)? // "")
      else "" end;
    (.workspace.current_dir // .cwd | s), "\u0000",
    (.model.display_name | s), "\u0000",
    (.effort.level | s), "\u0000",
    (.fast_mode // false | s), "\u0000",
    (.vim.mode | s), "\u0000",
    (.context_window.used_percentage | int), "\u0000",
    (.context_window.context_window_size | int), "\u0000",
    (.rate_limits.five_hour.used_percentage | int), "\u0000",
    (.rate_limits.five_hour.resets_at | epoch), "\u0000",
    (.rate_limits.seven_day.used_percentage | int), "\u0000",
    (.rate_limits.seven_day.resets_at | epoch), "\u0000",
    (.rate_limits.spend_limit.used_percentage | int), "\u0000",
    (.rate_limits.spend_limit.resets_at | epoch), "\u0000",
    (.prompt_cache.caching_observed // false | s), "\u0000",
    (.prompt_cache.warm // false | s), "\u0000",
    (.prompt_cache.hit_ratio | pct), "\u0000",
    (.prompt_cache.expires_at | epoch), "\u0000",
    (.prompt_cache.last_miss_at | epoch), "\u0000",
    (.prompt_cache.last_miss_cause.causes[0]? | s), "\u0000",
    (.cost.total_cost_usd | if type == "number" then tostring else "" end), "\u0000",
    (.cost.total_duration_ms // 0 | int), "\u0000",
    (.cost.total_lines_added // 0 | int), "\u0000",
    (.cost.total_lines_removed // 0 | int), "\u0000",
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

# --- palette -------------------------------------------------------------------

# Real escape bytes, so output is printed with %s and backslashes in paths or
# branch names are never interpreted.
_rgb() { printf '\e[38;2;%d;%d;%dm' "0x${1:0:2}" "0x${1:2:2}" "0x${1:4:2}"; }
FG=$(_rgb d1d5db)     # primary: model, repo, context %
MUTED=$(_rgb 8b949e)  # secondary: branch, tokens, cost
LABEL=$(_rgb 767f8a)  # right column labels and reset times
DIM=$(_rgb 636c76)    # effort, parent path, durations
FAINT=$(_rgb 373e47)  # dots, empty bar track
ACCENT=$(_rgb 9a8cf5) # identity: ◆, context bar, PR link
GHOST=$(_rgb 535a63)  # limit meter: where an even pace would be by now
OK=$(_rgb 56d364)     # limit on pace, lines added (GitHub dark green.3)
WARN=$(_rgb e3b341)   # threshold crossed (yellow.3)
CRIT=$(_rgb ff7b72)   # act now, lines removed (red.3)
BOLD=$'\e[1m'
RESET=$'\e[0m'
SEP=" $(_rgb 4b525b)⏐${RESET} "
NBSP=$(printf '\302\240')

# --- helpers -------------------------------------------------------------------

# Reset epoch → countdown within a day ("42m", "3h12m"), else "Tue 2:30am"
_fmt_reset() {
    local secs=$(($1 - now)) day
    if [ "$secs" -le 0 ]; then
        printf 'now'
    elif [ "$secs" -lt 3600 ]; then
        printf '%dm' "$((secs / 60))"
    elif [ "$secs" -lt 86400 ]; then
        printf '%dh%02dm' "$((secs / 3600))" "$((secs % 3600 / 60))"
    else
        day=$(date -r "$1" +"%a %-I:%M%p" 2> /dev/null || date -d "@$1" +"%a %-I:%M%p")
        day=${day/%AM/am}
        printf '%s' "${day/%PM/pm}"
    fi
}

# Seconds → "2h" / "45m" / "<1m"
_fmt_duration() {
    if [ "$1" -ge 3600 ]; then
        printf '%dh' "$(($1 / 3600))"
    elif [ "$1" -ge 60 ]; then
        printf '%dm' "$(($1 / 60))"
    else
        printf '<1m'
    fi
}

# Seconds → "1h12m" / "12m5s" / "40s"
_fmt_elapsed() {
    if [ "$1" -ge 3600 ]; then
        printf '%dh%dm' "$(($1 / 3600))" "$(($1 % 3600 / 60))"
    elif [ "$1" -ge 60 ]; then
        printf '%dm%ds' "$(($1 / 60))" "$(($1 % 60))"
    else
        printf '%ds' "$1"
    fi
}

# 1234567 → "1.2M", 1000000 → "1M", 102400 → "102k"
_fmt_tokens() {
    local n=$1 tenth
    if [ "$n" -ge 1000000 ]; then
        tenth=$((n % 1000000 / 100000))
        printf '%d' "$((n / 1000000))"
        [ "$tenth" -gt 0 ] && printf '.%d' "$tenth"
        printf 'M'
    elif [ "$n" -ge 1000 ]; then
        printf '%dk' "$((n / 1000))"
    else
        printf '%d' "$n"
    fi
}

# Thin meter: heavy ━ fill, light ─ track, whole cells only (a half-cell ╸
# leaves a visible gap before the track). One fill color, picked by state. With
# a pace percentage, the empty cells up to it draw as a dim heavy ghost, so the
# gap between fill and ghost is headroom against an even burn rate.
_bar() {
    local used=$1 width=$2 color=$3 pace=${4:-0} full ghost i out=""
    full=$(((used * width + 50) / 100))
    [ "$used" -gt 0 ] && [ "$full" -eq 0 ] && full=1
    [ "$full" -gt "$width" ] && full=$width
    ghost=$(((pace * width + 50) / 100))
    out+=$color
    for ((i = 0; i < full; i++)); do out+="━"; done
    out+=$GHOST
    for ((; i < ghost; i++)); do out+="━"; done
    out+=$FAINT
    for ((; i < width; i++)); do out+="─"; done
    printf '%s' "$out$RESET"
}

# Percent of a window elapsed, from its reset epoch and length in seconds
_pace() {
    local p=$((($2 - ($1 - now)) * 100 / $2))
    [ "$p" -lt 0 ] && p=0
    [ "$p" -gt 100 ] && p=100
    printf '%d' "$p"
}

# Limit state by burn rate: compare usage to how much of the window has
# elapsed, so 60% used with an hour left is fine but 30% after ten minutes is not.
_pace_state() {
    local used=$1 reset=$2 window=$3 pace
    if [ "$used" -ge 90 ]; then
        printf 'crit'
    elif [ -z "$reset" ]; then
        if [ "$used" -ge 75 ]; then printf 'warn'; else printf 'ok'; fi
    else
        pace=$(_pace "$reset" "$window")
        if [ "$used" -gt $((pace + 20)) ]; then
            printf 'crit'
        elif [ "$used" -gt $((pace + 5)) ] || [ "$used" -ge 75 ]; then
            printf 'warn'
        else
            printf 'ok'
        fi
    fi
}

# Context state: calm until it starts to matter
_ctx_state() {
    if [ "$1" -ge 80 ]; then printf 'crit'; elif [ "$1" -ge 60 ]; then printf 'warn'; else printf 'ok'; fi
}

# State → color, given the color to use when everything is fine
_state_color() {
    case "$1" in
        crit) printf '%s' "$CRIT" ;;
        warn) printf '%s' "$WARN" ;;
        *) printf '%s' "$2" ;;
    esac
}

# Visible width with SGR colors and OSC 8 links removed. Pure bash: this runs
# a few dozen times per render while fitting the layout.
_visible_len() {
    local s=${1//$'\e['*([0-9;])m/}
    s=${s//$'\e]8;;'*([!$'\a'])$'\a'/}
    printf '%d' "${#s}"
}

# N non-breaking spaces; plain spaces get trimmed by the harness.
_nbsp() {
    local pad
    printf -v pad '%*s' "$1" ''
    printf '%s' "${pad// /$NBSP}"
}

# --- git (cached) --------------------------------------------------------------

# Branch name, "*" when dirty, ↑N/↓N against upstream. --no-optional-locks keeps
# us from contending with a concurrent git command for the index.
_git_info() {
    local dir=$1 branch marks="" counts ahead behind
    branch=$(git -C "$dir" symbolic-ref --short HEAD 2> /dev/null ||
        git -C "$dir" rev-parse --short HEAD 2> /dev/null) || return 0
    [ -n "$(git -C "$dir" --no-optional-locks status --porcelain 2> /dev/null | head -n 1)" ] && marks+="*"
    if counts=$(git -C "$dir" rev-list --left-right --count '@{u}...HEAD' 2> /dev/null); then
        read -r behind ahead <<< "$counts"
        [ "$ahead" -gt 0 ] && marks+=" ↑$ahead"
        [ "$behind" -gt 0 ] && marks+=" ↓$behind"
    fi
    printf '%s' "$branch$marks"
}

# The refresh timer re-runs us every few seconds; `git status` is the slow part
# in big repos, so reuse the result for 5s per directory. Written via a temp
# file and mv so a concurrent render never reads a half-written cache.
_git_cached() {
    local dir=$1 key file mtime info
    key=$(printf '%s' "$dir" | { md5 -q 2> /dev/null || md5sum | cut -d' ' -f1; })
    file="${TMPDIR:-/tmp}/claude-statusline-git-$key"
    mtime=$(stat -f %m "$file" 2> /dev/null || stat -c %Y "$file" 2> /dev/null) || mtime=0
    if [ $((now - mtime)) -lt 5 ]; then
        cat "$file"
    else
        info=$(_git_info "$dir")
        printf '%s' "$info" > "$file.$$" && mv -f "$file.$$" "$file"
        printf '%s' "$info"
    fi
}

# --- line 1: model, context, cache, cost, duration -----------------------------

# Medium is the baseline, so low/medium stay dim; high steps up to the primary
# tone and xhigh/max (rare, costly) to amber.
case "$effort" in
    high) effort_color=$FG ;;
    xhigh | max) effort_color=$WARN ;;
    *) effort_color=$DIM ;;
esac
model_seg=""
[ -n "$model" ] && model_seg="${ACCENT}◆${RESET} ${FG}${model}${RESET}"
[ -n "$effort" ] && model_seg+=" ${FAINT}·${RESET} ${effort_color}${effort}${RESET}"
[ "$fast_mode" = "true" ] && model_seg+=" ${WARN}↯${RESET}"
[ -n "$vim_mode" ] && model_seg+=" ${DIM}${vim_mode}${RESET}"

ctx_seg="" ctx_tokens=""
if [ -n "$ctx_used" ]; then
    ctx_state=$(_ctx_state "$ctx_used")
    ctx_seg="${SEP}$(_bar "$ctx_used" 12 "$(_state_color "$ctx_state" "$ACCENT")") $(_state_color "$ctx_state" "$FG")${ctx_used}%${RESET}"
    if [ "${ctx_size:-0}" -gt 0 ]; then
        ctx_tokens="  ${DIM}$(_fmt_tokens $((ctx_size * ctx_used / 100)))/$(_fmt_tokens "$ctx_size")${RESET}"
    fi
fi

# Cache: hit ratio and time until cold. Going cold is worth noticing, not
# alarming, so it's amber. A miss within two minutes shows its cause, dimmed:
# it explains the state rather than being one.
cache_seg="" cache_miss=""
if [ "$cache_observed" = "true" ]; then
    cache_seg="${SEP}${DIM}cache${RESET}"
    secs=$((${cache_expires:-0} - now))
    if [ "$cache_warm" != "true" ] || [ "$secs" -le 0 ]; then
        cache_seg+=" ${WARN}cold${RESET}"
    else
        [ -n "$cache_ratio" ] && cache_seg+=" ${MUTED}${cache_ratio}%${RESET}"
        cache_seg+=" ${DIM}$(_fmt_duration "$secs")${RESET}"
    fi
    if [ -n "$miss_cause" ] && [ $((now - ${miss_at:-0})) -lt 120 ]; then
        cache_miss=" ${FAINT}·${RESET} ${DIM}${miss_cause}${RESET}"
    fi
fi

# Never colored: on a subscription the cost is notional
cost_seg=""
if [ -n "$cost" ]; then
    cost_fmt=$(printf '%.2f' "$cost" 2> /dev/null)
    [ -n "$cost_fmt" ] && [ "$cost_fmt" != "0.00" ] && cost_seg="${SEP}${MUTED}\$${cost_fmt}${RESET}"
fi

time_seg=""
[ "${duration_ms:-0}" -ge 1000 ] && time_seg="${SEP}${DIM}$(_fmt_elapsed $((duration_ms / 1000)))${RESET}"

# Line 1 at a detail level: 0 = everything, 1 = no duration, 2 = no cost,
# 3 = no miss cause, 4 = no token counts. Segments lead with SEP, so drop it
# when nothing precedes the first one.
_line1() {
    local out="$model_seg$ctx_seg"
    [ "$1" -lt 4 ] && out+=$ctx_tokens
    out+=$cache_seg
    [ "$1" -lt 3 ] && out+=$cache_miss
    [ "$1" -lt 2 ] && out+=$cost_seg
    [ "$1" -lt 1 ] && out+=$time_seg
    printf '%s' "${out#"$SEP"}"
}

# --- line 2: path, branch, lines changed, PR, worktree/agent --------------------

path=$cwd
case "$cwd" in "$HOME"/*) path="~${cwd#"$HOME"}" ;; esac

# "…/parent/leaf", unless that isn't actually shorter
_collapse_path() {
    local leaf=${1##*/} parent=${1%/*} short
    short="…/${parent##*/}/${leaf}"
    if [ "${#short}" -lt "${#1}" ]; then printf '%s' "$short"; else printf '%s' "$1"; fi
}

# Parent dims, leaf stands out: the eye lands on the project name
_fmt_path() {
    local leaf=${1##*/}
    [ "$leaf" != "$1" ] && printf '%s' "${DIM}${1%/*}/${RESET}"
    printf '%s' "${FG}${BOLD}${leaf}${RESET}"
}

git_info=""
[ -n "$cwd" ] && git_info=$(_git_cached "$cwd")

l2_git="" l2_lines="" l2_pr="" l2_extra=""
# 󰘬 is nf-md-source_branch (U+F062C); needs a Nerd Font
[ -n "$git_info" ] && l2_git="${SEP}${DIM}󰘬${RESET} ${MUTED}${git_info}${RESET}"
if [ "${lines_add:-0}" != 0 ] || [ "${lines_del:-0}" != 0 ]; then
    l2_lines="${SEP}${OK}+${lines_add:-0}${RESET} ${CRIT}−${lines_del:-0}${RESET}"
fi
if [ -n "$pr_num" ]; then
    case "$pr_state" in
        approved) pr_mark=" ${OK}✓" ;;
        changes_requested) pr_mark=" ${WARN}✗" ;;
        pending | draft) pr_mark=" ${DIM}◌" ;;
        *) pr_mark="" ;;
    esac
    # OSC 8 hyperlink: Cmd+click opens the PR
    l2_pr="${SEP}"$'\e]8;;'"${pr_url}"$'\a'"${ACCENT}#${pr_num}"$'\e]8;;\a'"${pr_mark}${RESET}"
fi
[ -n "$worktree" ] && l2_extra+="${SEP}${DIM}⊞${RESET} ${MUTED}${worktree}${RESET}"
[ -n "$agent" ] && l2_extra+="${SEP}${DIM}⚙${RESET} ${MUTED}${agent}${RESET}"

# Line 2 for a path at a detail level: 0 = everything, 1 = no lines changed,
# 2 = no worktree/agent.
_line2() {
    local out=""
    [ -n "$1" ] && out=$(_fmt_path "$1")
    out+=$l2_git
    [ "$2" -lt 1 ] && out+=$l2_lines
    out+=$l2_pr
    [ "$2" -lt 2 ] && out+=$l2_extra
    printf '%s' "${out#"$SEP"}"
}

# --- right column: usage limits --------------------------------------------------

# One limit per line, so at most two; a gateway spend limit takes a free slot.
limits=()
[ -n "$fh_used" ] && limits+=("5h|$fh_used|$fh_reset|18000")
[ -n "$sd_used" ] && limits+=("7d|$sd_used|$sd_reset|604800")
[ -n "$sp_used" ] && limits+=("spend|$sp_used|$sp_reset|2592000")

# "spend" is wider than "5h"/"7d"; only widen the label column when it shows
label_w=2
[[ " ${limits[*]:0:2}" == *" spend|"* ]] && label_w=5

# Limits render as a two-row table: label, meter, used %, then reset times
# right-aligned, so both rows share every column edge. Usage is shown like
# context, so all meters fill the same way. Colors follow burn rate.

# "5h ━━━━━───── 35%" for limit $1; mode "full" includes the meter
_limit_head() {
    local spec=${limits[$1]:-} mode=$2 label used reset window color pace=0
    [ -n "$spec" ] || return 0
    IFS='|' read -r label used reset window <<< "$spec"
    color=$(_state_color "$(_pace_state "$used" "$reset" "$window")" "$OK")
    [ -n "$reset" ] && pace=$(_pace "$reset" "$window")
    printf "${LABEL}%-${label_w}s${RESET} " "$label"
    [ "$mode" = full ] && printf '%s ' "$(_bar "$used" 10 "$color" "$pace")"
    printf '%s%3d%%%s' "$color" "$used" "$RESET"
}

_limit_reset() {
    local spec=${limits[$1]:-} reset
    [ -n "$spec" ] || return 0
    IFS='|' read -r _ _ reset _ <<< "$spec"
    [ -n "$reset" ] && _fmt_reset "$reset"
    return 0
}

# Sets r1/r2 for a mode: full, nobar (no meters), short (no reset times either)
_build_right() {
    local t1="" t2="" w
    r1=$(_limit_head 0 "$1")
    r2=$(_limit_head 1 "$1")
    if [ "$1" != short ]; then
        t1=$(_limit_reset 0)
        t2=$(_limit_reset 1)
    fi
    w=$((${#t1} > ${#t2} ? ${#t1} : ${#t2}))
    [ "$w" -gt 0 ] || return 0
    [ -n "$r1" ] && r1+="$(_nbsp $((w - ${#t1} + 1)))${LABEL}${t1}${RESET}"
    [ -n "$r2" ] && r2+="$(_nbsp $((w - ${#t2} + 1)))${LABEL}${t2}${RESET}"
    return 0
}

# --- layout --------------------------------------------------------------------

# The harness sets COLUMNS; stdio is piped so tty probing is a fallback only.
cols=${COLUMNS:-}
[ "$cols" -gt 0 ] 2> /dev/null || cols=$({ stty size < /dev/tty | awk '{print $2}'; } 2> /dev/null)
[ "$cols" -gt 0 ] 2> /dev/null || cols=""
margin=4

_fits() { [ -z "$cols" ] || [ $(($(_visible_len "$1") + $(_visible_len "$2") + 2 + margin)) -le "$cols" ]; }
_both_fit() { _fits "$(_line1 "$level")" "$r1" && _fits "$l2" "$r2"; }

# Right-align $2 after $1 with NBSP padding; a fixed gap when width is unknown.
_join() {
    local pad=2
    [ -n "$cols" ] && pad=$((cols - margin - $(_visible_len "$1") - $(_visible_len "$2")))
    [ "$pad" -lt 2 ] && pad=2
    printf '%s' "$1"
    [ -n "$2" ] && printf '%s%s' "$(_nbsp "$pad")" "$2"
    return 0
}

# Shed detail until both lines fit: duration and cost, then the collapsed
# path, then limit meters, then reset times, then miss cause and token counts
# on line 1 and lines changed and worktree/agent on line 2.
_build_right full
level=0
while [ "$level" -lt 2 ] && ! _fits "$(_line1 "$level")" "$r1"; do
    level=$((level + 1))
done
l2_path=$path l2_level=0
l2=$(_line2 "$l2_path" 0)
_fits "$l2" "$r2" || {
    l2_path=$(_collapse_path "$path")
    l2=$(_line2 "$l2_path" 0)
}
_both_fit || _build_right nobar
_both_fit || _build_right short
while [ "$level" -lt 4 ] && ! _fits "$(_line1 "$level")" "$r1"; do
    level=$((level + 1))
done
while [ "$l2_level" -lt 2 ] && ! _fits "$l2" "$r2"; do
    l2_level=$((l2_level + 1))
    l2=$(_line2 "$l2_path" "$l2_level")
done

# Trailing spacer row separates us from the harness footer. Whitespace-only rows
# (NBSP included) get dropped, so use the braille blank U+2800, which renders
# empty but isn't whitespace.
printf '%s\n%s\n%s' "$(_join "$(_line1 "$level")" "$r1")" "$(_join "$l2" "$r2")" '⠀'
