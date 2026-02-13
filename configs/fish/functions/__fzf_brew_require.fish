# fzf-brew for fish shell
# 
# A fish-native port of the zsh fzf-brew plugin. Provides fuzzy find 
# functionality for Homebrew formulae and casks.
#
# Commands:
#   fbi   - Fuzzy install formula (brew formulae → fzf → brew install)
#   fbui  - Fuzzy uninstall formula (brew leaves → fzf → brew uninstall)
#   fci   - Fuzzy install cask (brew casks → fzf → brew install --cask)
#   fcui  - Fuzzy uninstall cask (brew list --cask → fzf → brew uninstall --cask)
#
# Key features:
#   - Multi-select with shift-tab (fzf default)
#   - Preview panel showing brew info
#   - Ctrl-space opens homepage via `brew home`
#   - Query pre-fill: pass args like `fbi git` to start with "git" query
#
# This is a private helper function that validates dependencies exist.
# It's called by all public functions to fail fast if brew or fzf missing.

function __fzf_brew_require --description "Ensure fzf-brew dependencies are available"
    # 127 = command not found (bash/fish standard exit code)
    if not type -q brew
        printf 'fzf-brew: Homebrew not found in PATH\n' >&2
        return 127
    end

    if not type -q fzf
        printf 'fzf-brew: fzf not found in PATH\n' >&2
        return 127
    end
end
