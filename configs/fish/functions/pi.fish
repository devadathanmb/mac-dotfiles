function pi --description "Run Pi with local MCP credentials"
    # Add `ENV_VAR path/to/secret` entries here; the key never enters MCP config.
    set -l secret_specs \
        "EXA_API_KEY $HOME/.secrets/exa-api-key"

    for secret_spec in $secret_specs
        set -l parts (string split -m 1 ' ' -- $secret_spec)
        set -l variable_name $parts[1]
        set -l secret_file $parts[2]

        if not test -r "$secret_file"
            echo "pi: $variable_name is unavailable; continuing without it." >&2
            continue
        end

        set -l secret_value (string trim -- < "$secret_file")
        if test -z "$secret_value"
            echo "pi: $variable_name secret file is empty; continuing without it." >&2
            continue
        end

        # Function scope prevents credentials from remaining in the interactive shell.
        set -fx $variable_name "$secret_value"
    end

    command pi $argv
end
