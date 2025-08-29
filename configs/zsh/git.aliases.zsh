#!/usr/bin/env zsh

function __check_git_dir(){
  if [ ! -d ".git" ]; then
      echo "Not a git repository"
      return 1
  fi
}

function _git_checkout_interactive() {
  __check_git_dir
  local branch
  branch=$(git branch --all | grep -v HEAD | sed 's/.* //' | sed 's#remotes/origin/##' | sort -u | fzf --preview '
    branch={}
    if git show-ref --verify --quiet refs/heads/$branch; then
      git log --oneline --graph --date=short --color=always --pretty="format:%C(auto)%cd %h%d %s" $branch --
    elif git show-ref --verify --quiet refs/remotes/origin/$branch; then
      git log --oneline --graph --date=short --color=always --pretty="format:%C(auto)%cd %h%d %s" origin/$branch --
    else
      echo "No log data available for $branch"
    fi
  ' \
  '--preview-window=right:70%'
  )
  if [[ -n $branch ]]; then
    if git show-ref --verify --quiet refs/heads/$branch; then
      git checkout "$branch"
    else
      git checkout --track "origin/$branch"
    fi
    git pull origin
    git submodule update
  fi
}

_git_show_commits() {
  __check_git_dir
  local selected_commit
  selected_commit=$(git log --format="%h %s" | \
    fzf --preview '
      git show --color=always {1}
    ' --preview-window=right:40% )

  if [[ -n $selected_commit ]]; then
    commit_hash=$(echo $selected_commit | cut -d ' ' -f1)
    pbcopy <<< $commit_hash
    echo "Commit hash $commit_hash copied to clipboard"
  fi
}

alias gci=_git_checkout_interactive
alias gsc=_git_show_commits

# Normal git aliases
alias g=git
alias ga="git add"
alias gs="git status"
alias gg="git log --oneline --graph --decorate --all"
alias gl="git log"
alias gd="git diff"
alias gdc="git diff --cached"
alias gc="git commit -m"
alias gcm='(git checkout master &>/dev/null && git pull origin master) || (git checkout main && git pull origin main) && git submodule update'
alias gf="git fetch"
alias gr="git reset"
alias gcp="git cherry-pick"
alias gpo="git push origin"
alias gms="git merge --squash"
alias gpl="git pull"
alias gplo="git pull origin"
alias gac=_git_add_all_and_commit
alias glp="git log --graph --abbrev-commit --decorate --format=format:'%C(bold blue)%h%C(reset) - %C(bold green)(%ar)%C(reset) %C(white)%s%C(reset) %C(dim white)- %an%C(reset)%C(bold yellow)%d%C(reset)'"
alias clone="git clone"
alias gsu="git submodule update"
alias gfa="git fetch --all"
alias gcb="git checkout -b"
alias gs="git switch"
alias gco="git checkout"

function _git_add_all_and_commit(){
  # List all git unstaged files that are going to be added and committed
  echo "The following files will be added and committed:"
  git status --porcelain | sed 's/^...//g'

  # Add all files and commit
  git add .
  git commit -m "$1"
}
