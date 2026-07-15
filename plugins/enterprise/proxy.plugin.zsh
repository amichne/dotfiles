#!/usr/bin/env zsh

with-proxy() {
    if [[ "$#" -eq 0 ]]; then
        print -u2 -- "Usage: with-proxy <command> [args]"
        return 64
    fi
    "$DOTFILES_ROOT/bin/dotfiles" proxy exec -- "$@"
}
