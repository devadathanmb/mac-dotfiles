# Interactive integrations
if status is-interactive
    if command -q atuin
        atuin init fish | source
    end
    if command -q zoxide
        zoxide init fish | source
    end
end

# mise manages language/tool versions.
if command -q mise
    mise activate fish | source
end
