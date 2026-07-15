#!/usr/bin/env zsh

with-github-token() {
    if [[ "$#" -eq 0 ]]; then
        print -u2 -- "Usage: with-github-token <command> [args]"
        return 64
    fi
    "$DOTFILES_ROOT/bin/dotfiles" credential exec github -- "$@"
}
