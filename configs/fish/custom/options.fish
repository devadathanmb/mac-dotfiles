# FZF
set -x FZF_DEFAULT_OPTS "--bind=tab:down,shift-tab:up,ctrl-space:toggle"

# Option overrides
set -g fish_cursor_default block blink
set -g fish_cursor_insert line blink
set -g fish_cursor_replace_one underscore blink
set -g fish_cursor_visual block blink

# Change delay to 10ms to avoid re-rendering prompt when you're too quick
set -g fish_escape_delay_ms 10

# # color customizatons
# set -U fish_color_command green
# set -U fish_color_error red
# set -U fish_color_redirection yellow

# Commands and basics
set -g fish_color_command green
set -g fish_color_param cyan
set -g fish_color_option magenta

# Quotes and strings
set -g fish_color_quote yellow
set -g fish_color_escape cyan

# Operators and special characters
set -g fish_color_redirection yellow
set -g fish_color_operator brmagenta
set -g fish_color_end brmagenta

# Comments
set -g fish_color_comment brblack

# Errors and validation
set -g fish_color_error red --bold
set -g fish_color_valid_path --underline

# Autosuggestions
set -g fish_color_autosuggestion brblack

# Search
set -g fish_color_search_match --background=brblack

# Selection
set -g fish_color_selection white --bold --background=brblack

# Prompts (optional)
set -g fish_color_user brgreen
set -g fish_color_host normal
set -g fish_color_cwd blue
set -g fish_color_cwd_root red

# Pager (completion menu)
set -g fish_pager_color_completion normal
set -g fish_pager_color_description yellow
set -g fish_pager_color_prefix cyan --bold
set -g fish_pager_color_progress brwhite --background=cyan
