#!/usr/bin/env bash

dotfiles_error() {
    printf 'dotfiles: %s\n' "$*" >&2
}

dotfiles_require_file() {
    local dotfiles_required_file="$1"
    if [ ! -f "$dotfiles_required_file" ]; then
        dotfiles_error "required file is missing: $dotfiles_required_file"
        return 66
    fi
}

dotfiles_require_safe_profile_name() {
    local dotfiles_profile_name="$1"
    case "$dotfiles_profile_name" in
        ''|*[!A-Za-z0-9_-]*)
            dotfiles_error "invalid profile name: $dotfiles_profile_name"
            return 65
            ;;
    esac
}
