# Shared by login and interactive shells. Prefer Brew to old mise shim links.
typeset -U path
path=("$HOME/.local/bin" "${MISE_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/mise}/shims" $path)
for _shell_brew in ${HOMEBREW_PREFIX:+"$HOMEBREW_PREFIX"} /opt/homebrew /home/linuxbrew/.linuxbrew /usr/local; do
    if [[ -x $_shell_brew/bin/brew ]]; then
        path=("$_shell_brew/bin" $path)
        break
    fi
done
unset _shell_brew
