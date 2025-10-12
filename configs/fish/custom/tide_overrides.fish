# General Prompt Settings
set --global tide_left_prompt_items pwd git newline character
set --global tide_right_prompt_items status cmd_duration context jobs
set --global tide_prompt_add_newline_before true
set --global tide_prompt_pad_items false

# PWD (Directory) Colors - matching Pure's blue
set --global tide_pwd_bg_color normal
set --global tide_pwd_color_anchors 0000FF # Blue
set --global tide_pwd_color_dirs 0000FF # Blue
set --global tide_pwd_color_truncated_dirs 8787AF # Muted blue for truncated
set --global tide_pwd_icon

# Git Colors - matching Pure's minimal style
set --global tide_git_bg_color normal
set --global tide_git_bg_color_unstable normal
set --global tide_git_bg_color_urgent normal
set --global tide_git_color_branch normal # Default terminal color
set --global tide_git_color_upstream 00FFFF # Cyan
set --global tide_git_color_dirty normal
set --global tide_git_color_staged normal
set --global tide_git_color_stash 00FFFF # Cyan
set --global tide_git_color_untracked normal
set --global tide_git_color_conflicted FF0000 # Red
set --global tide_git_color_operation normal

# Character (Prompt Symbol) Colors - matching Pure
set --global tide_character_color 00FF00 # Magenta for success
set --global tide_character_color_failure FF0000 # Red for failure
set --global tide_character_icon ❯
set --global tide_character_vi_icon_default ❮

# Command Duration - matching Pure's yellow
set --global tide_cmd_duration_bg_color normal
set --global tide_cmd_duration_color FFFF00 # Yellow
set --global tide_cmd_duration_decimals 0
set --global tide_cmd_duration_threshold 3000

# Status 
set --global tide_status_bg_color normal
set --global tide_status_bg_color_failure normal
set --global tide_status_color normal
set --global tide_status_color_failure FF0000 # Red

# Context (user@host)
set --global tide_context_always_display false
set --global tide_context_bg_color normal
set --global tide_context_color_default normal
set --global tide_context_color_root FFFF00 # Yellow
set --global tide_context_color_ssh FFFF00 # Yellow

# Jobs
set --global tide_jobs_bg_color normal
set --global tide_jobs_color 00FFFF # Cyan

# Remove separators for cleaner look like Pure
set --global tide_left_prompt_separator_diff_color ' '
set --global tide_left_prompt_separator_same_color ' '
set --global tide_right_prompt_separator_diff_color ' '
set --global tide_right_prompt_separator_same_color ' '

# Disable frames
set --global tide_left_prompt_frame_enabled false
set --global tide_right_prompt_frame_enabled false
