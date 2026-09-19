# The following lines were added by Docker Desktop to add commands to your PATH.
export PATH="$PATH:/Users/devadathan.mb/.docker/bin"
# End of Docker Desktop section.

eval "$(/opt/homebrew/bin/brew shellenv)"

if command -v mise >/dev/null 2>&1; then
  eval "$(mise activate zsh --shims)"
fi
