#!/usr/bin/env zsh

# Custom Functions
__DOTFILES_PATH="$HOME/.mac-dots/"

# FZF CD Widget
fzf-cd-widget() {
    local dir="$(find . -type d -print 2> /dev/null | fzf --preview 'ls {}' +m)"
    if [ -n "$dir" ]; then
        cd "$dir"
        zle reset-prompt
    fi
}
zle -N fzf-cd-widget

# Alias listing function
function _alias_ls(){
    alias_files=(
        ~/.zshrc
        ~/.config/zsh/git.aliases.zsh
        ~/.config/zsh/general.aliases.zsh
    )

    __extract_aliases() {
        for file in "${alias_files[@]}"; do
            if [[ -f "$file" ]]; then
                grep '^alias ' "$file" | sed -E 's/^alias //'
            fi
        done
    }

    selected_alias=$(__extract_aliases | fzf --prompt="Select an alias: ")
    selected_alias_alias=$(echo "$selected_alias" | cut -d '=' -f 1)

    if [[ -n "$selected_alias" ]]; then
        if command -v pbcopy &> /dev/null; then
            echo -n "$selected_alias_alias" | pbcopy
        elif command -v xclip &> /dev/null; then
            echo -n "$selected_alias_alias" | xclip -selection clipboard
        else
            echo "No clipboard utility found. Install pbcopy or xclip."
            exit 1
        fi
        echo "Alias copied to clipboard: $selected_alias"
    else
        echo "No alias selected."
    fi
}

# Incognito mode function
function incognito() {
    local icon_on=$'\uf070'
    local icon_off=$'\uf06e'

    if [[ "$1" == "on" ]]; then
        if [[ -z "$OLD_HISTFILE" ]]; then
            export OLD_HISTFILE=$HISTFILE
            unset HISTFILE
            echo "${icon_on} Incognito mode activated. History will not be saved."
        else
            echo "Incognito mode is already active."
        fi
    elif [[ "$1" == "off" ]]; then
        if [[ -n "$OLD_HISTFILE" ]]; then
            export HISTFILE=$OLD_HISTFILE
            unset OLD_HISTFILE
            echo "${icon_off} Incognito mode deactivated. History will be saved normally."
        else
            echo "Incognito mode is not active."
        fi
    else
        echo "Usage: incognito [on|off]"
    fi
}

# Directory and file copying function
function _make_dirs_and_copy_files() {
    local source_dir=$1
    shift
    local target_dirs=("$@")

    if [[ -z $source_dir || ${#target_dirs[@]} -eq 0 ]]; then
        echo "Usage: _make_dirs_and_copy_files <source_dir> <target_dir1> <target_dir2> ..."
        return 1
    fi

    if [[ ! -d $source_dir ]]; then
        echo "Source directory does not exist: $source_dir"
        return 1
    fi

    for target_dir in "${target_dirs[@]}"; do
        if [[ -d $target_dir ]]; then
            echo "Target directory already exists: $target_dir"
            continue
        fi
        mkdir -p "$target_dir" && echo "Created directory: $target_dir"
        cp -r "$source_dir"/* "$target_dir" && echo "Copied files from $source_dir to $target_dir"
    done
}

# Quick FZF CD
function __fzf_cd() {
    local dir="$(find . -type d -print 2> /dev/null | fzf --preview 'ls {}' +m)"
    if [ -n "$dir" ]; then
        cd "$dir"
    fi
}

# Clean downloads function
TRASH="/tmp/trash"
function _clean_downloads() {
    local downloads_dir="$HOME/Downloads"
    local trash_dir="$TRASH"

    mkdir -p "$trash_dir"
    find "$downloads_dir" -maxdepth 1 -type f \( -iname "*.pdf" -o -iname "*.csv" -o -iname "*.zip" -o -iname "*.xlsx" \) -exec mv -f {} "$trash_dir" \; 2>/dev/null
    echo "Moved files from $downloads_dir to $trash_dir"
}

# Aliases for functions
alias als="_alias_ls"
alias cpdir="_make_dirs_and_copy_files"
alias soz="source ~/.zshrc && echo '⚡Sourced ~/.zshrc ⚡'"
alias szsh="soz"
alias dotsup="cd $__DOTFILES_PATH && gac 'Update dotfiles' && gpo && echo 'Dotfiles updated and pushed'"
alias cdf="__fzf_cd"
alias shh="incognito"
alias brewup="echo 'Brewing...' && brew update && brew upgrade && brew cleanup && clear && echo 'Brew complete'"
alias cleandown="_clean_downloads"
