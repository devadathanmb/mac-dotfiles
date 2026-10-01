function upgrade-agents --description 'Upgrade only mise-managed coding agents'
    mise upgrade agy \
        npm:@anthropic-ai/claude-code \
        npm:@earendil-works/pi-coding-agent \
        npm:@openai/codex \
        npm:@opencode/cli $argv
end
