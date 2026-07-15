#!/usr/bin/env bash

dotfiles_home_require_chezmoi() {
    if ! command -v chezmoi >/dev/null 2>&1; then
        dotfiles_error "optional dependency is unavailable: chezmoi"
        dotfiles_error "$(dotfiles_dependency_hint chezmoi 2>/dev/null || printf 'Install chezmoi with an approved package provider.')"
        return 69
    fi
}

dotfiles_home_chezmoi() {
    command chezmoi \
        --source "$DOTFILES_ROOT/home" \
        --destination "$HOME" \
        --no-pager \
        --no-tty \
        --refresh-externals=never \
        "$@"
}

dotfiles_home_command() {
    local dotfiles_home_action="${1:-plan}"
    if [ "$#" -gt 0 ]; then
        shift
    fi
    if [ "$#" -ne 0 ]; then
        dotfiles_error "usage: dotfiles home <plan|apply|status>"
        return 64
    fi

    dotfiles_home_require_chezmoi || return
    case "$dotfiles_home_action" in
        plan) dotfiles_home_chezmoi diff ;;
        apply) dotfiles_home_chezmoi apply ;;
        status) dotfiles_home_chezmoi status ;;
        *)
            dotfiles_error "unknown home command: $dotfiles_home_action"
            return 64
            ;;
    esac
}
