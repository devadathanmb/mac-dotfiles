function __check_git_dir
    if not test -d ".git"
        echo "Not a git repository"
        return 1
    end
end

function _git_checkout_interactive
    __check_git_dir
    set branch
    set branch (git branch --all | grep -v HEAD | sed 's/.* //' | sed 's#remotes/origin/##' | sort -u | fzf --preview '
        branch={}
        if git show-ref --verify --quiet refs/heads/$branch
            git log --oneline --graph --date=short --color=always --pretty="format:%C(auto)%cd %h%d %s" $branch --
        else if git show-ref --verify --quiet refs/remotes/origin/$branch
            git log --oneline --graph --date=short --color=always --pretty="format:%C(auto)%cd %h%d %s" origin/$branch --
        else
            echo "No log data available for $branch"
        end
    ' --preview-window=right:70%)
    if test -n "$branch"
        if git show-ref --verify --quiet refs/heads/$branch
            git checkout "$branch"
        else
            git checkout --track "origin/$branch"
        end
        git pull origin
        git submodule update
    end
end

function _git_show_commits
    __check_git_dir
    set selected_commit (git log --format="%h %s" | fzf --preview '
        git show --color=always {1}
    ' --preview-window=right:40%)
    if test -n "$selected_commit"
        set commit_hash (echo $selected_commit | cut -d ' ' -f1)
        pbcopy $commit_hash
        echo "Commit hash $commit_hash copied to clipboard"
    end
end

# Aliases for functions
abbr gci _git_checkout_interactive
abbr gsc _git_show_commits

# General git aliases
function g
    git $argv
end

function ga
    git add $argv
end

function gs
    git status
end

function gg
    git log --oneline --graph --decorate --all
end

function gl
    git log
end

function gd
    git diff
end

function gdc
    git diff --cached
end

function gc
    git commit -m "$argv"
end

function gcm
    git checkout master ^/dev/null; and git pull origin master
    or begin
        git checkout main
        and git pull origin main
    end
    git submodule update
end

function gf
    git fetch
end

function gr
    git reset
end

function gcp
    git cherry-pick $argv
end

function gpo
    git push origin $argv
end

function gms
    git merge --squash
end

function gpl
    git pull
end

function gplo
    git pull origin
end

function gac
    _git_add_all_and_commit $argv
end

function glp
    git log --graph --abbrev-commit --decorate --format=format:'%C(bold blue)%h%C(reset) - %C(bold green)(%ar)%C(reset) %C(white)%s%C(reset) %C(dim white)- %an%C(reset)%C(bold yellow)%d%C(reset)'
end

function clone
    git clone $argv
end

function gsu
    git submodule update
end

function gfa
    git fetch --all
end

function gcb
    git checkout -b $argv
end

function gs
    git switch $argv
end

function gco
    git checkout $argv
end

# Function for git add and commit
function _git_add_all_and_commit
    echo "The following files will be added and committed:"
    git status --porcelain | sed 's/^...//g'
    git add .
    git commit -m "$argv"
end
