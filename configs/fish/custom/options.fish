# Cursor and shell behavior
set -g fish_cursor_default block blink
set -g fish_cursor_insert line blink
set -g fish_cursor_replace_one underscore blink
set -g fish_cursor_visual block blink

# Change delay to 10ms to avoid re-rendering prompt when you're too quick
set -g fish_escape_delay_ms 10

# Syntax highlighting
set -g fish_color_command green
set -g fish_color_param cyan
set -g fish_color_option magenta
set -g fish_color_quote yellow
set -g fish_color_escape cyan
set -g fish_color_redirection yellow
set -g fish_color_operator brmagenta
set -g fish_color_end brmagenta
set -g fish_color_comment brblack
set -g fish_color_error red --bold
set -g fish_color_valid_path --underline
set -g fish_color_autosuggestion brblack
set -g fish_color_search_match --background=brblack
set -g fish_color_selection white --bold --background=brblack
set -g fish_color_user brgreen
set -g fish_color_host normal
set -g fish_color_cwd blue
set -g fish_color_cwd_root red

# Completion pager
set -g fish_pager_color_completion normal
set -g fish_pager_color_description yellow
set -g fish_pager_color_prefix cyan --bold
set -g fish_pager_color_progress brwhite --background=cyan
