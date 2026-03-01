# ASDF configuration code
if test -z $ASDF_DATA_DIR
    set _asdf_shims "$HOME/.asdf/shims"
else
    set _asdf_shims "$ASDF_DATA_DIR/shims"
end

# Keep asdf shims first in PATH so shimmed binaries win over system ones.
set -gx PATH $_asdf_shims (string match -v -- $_asdf_shims $PATH)
set --erase _asdf_shims
