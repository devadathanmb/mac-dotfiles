# No greeting
set fish_greeting

if status is-interactive
    # fish 4.0 deprecates `bind -k`. transform's Atuin's init to drop -k and ensure up-binding works
    if type -q atuin
        set -l __atuin_init (atuin init fish | string replace -ra -- 'bind -M ([^ ]+)\s+-k ' 'bind -M $1 ' | string replace -ra -- 'bind\s+-k ' 'bind ')
        if test -n "$__atuin_init"
            printf '%s\n' $__atuin_init | source
            if functions -q _atuin_bind_up
                bind up _atuin_bind_up
                bind -M insert up _atuin_bind_up
            end
        else
            # fallback: source unmodified but silence deprecation noise
            atuin init fish 2>/dev/null | source
        end
    end
    # this fixes the "sparse" layout of the tide prompt
    set first_line true
    function sparse_prompt --on-event fish_prompt
        if test "$first_line" = true
            set first_line false
            return
        end

        # print newline for sparse layout
        echo
    end
end

# Enable vim mode
fish_vi_key_bindings

# color customizatons
set -U fish_color_command green
set -U fish_color_error red

# Source stuff
source ~/.config/fish/custom/options_overrides.fish
source ~/.config/fish/custom/aliases.fish
source ~/.config/fish/custom/exports.fish
source ~/.config/fish/custom/functions_git_helpers.fish
# source ~/.config/fish/custom/tide_overrides.fish

# Init zoxide
zoxide init fish | source
