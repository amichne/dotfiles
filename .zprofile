# Login shells need local commands and mise shims without interactive hooks.
typeset -U path
path=("$HOME/.local/bin" "${MISE_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/mise}/shims" $path /opt/homebrew/bin /usr/local/bin /home/linuxbrew/.linuxbrew/bin)
