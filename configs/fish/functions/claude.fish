# Unset $TMUX so Claude Code uses its full truecolor palette.
# Claude Code has a palette selection bug: when $TMUX is set it picks a muted
# "tmux-compatible" theme even when COLORTERM=truecolor and chalk level=3.
function claude --wraps claude --description 'Claude Code (truecolor fix: runs with TMUX unset)'
    env -u TMUX command claude $argv
end
