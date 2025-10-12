function incognito
    set icon_on (printf '\uf070')
    set icon_off (printf '\uf06e')

    if test "$argv[1]" = on
        if not set -q OLD_HISTFILE
            set -x OLD_HISTFILE $HISTFILE
            set -e HISTFILE
            echo "$icon_on Incognito mode activated. History will not be saved."
        else
            echo "Incognito mode is already active."
        end
    else if test "$argv[1]" = off
        if set -q OLD_HISTFILE
            set -x HISTFILE $OLD_HISTFILE
            set -e OLD_HISTFILE
            echo "$icon_off Incognito mode deactivated. History will be saved normally."
        else
            echo "Incognito mode is not active."
        end
    else
        echo "Usage: incognito [on|off]"
    end
end
