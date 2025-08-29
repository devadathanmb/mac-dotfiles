#!/usr/bin/env zsh

alias utcnow=__utcnow

# Function to get current time in UTC
function __utcnow(){
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}
