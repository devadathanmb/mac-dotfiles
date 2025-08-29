#! /usr/bin/env bash

set -e

# Zap lives in ~/.local/share/zap, so check if it exists there
if [ ! -d ~/.local/share/zap ]; then
   echo "Installing zap zsh..."
  zsh <(curl -s https://raw.githubusercontent.com/zap-zsh/zap/master/install.zsh) --branch release-v1
fi