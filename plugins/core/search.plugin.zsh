#!/usr/bin/env zsh

f() {
    if [[ "$#" -ne 2 ]]; then
        print -u2 -- "Usage: f <directory_or_file> <regex>"
        return 64
    fi

    local dotfiles_search_target="$1"
    local dotfiles_search_regex="$2"
    local dotfiles_search_command="$DOTFILES_CFG_SEARCH_COMMAND"

    if [[ ! -e "$dotfiles_search_target" ]]; then
        print -u2 -- "dotfiles: search target does not exist: $dotfiles_search_target"
        return 66
    fi

    if [[ "$dotfiles_search_command" == "auto" ]]; then
        if command -v rg >/dev/null 2>&1; then
            dotfiles_search_command="rg"
        else
            dotfiles_search_command="grep"
        fi
    fi

    case "$dotfiles_search_command" in
        rg)
            command -v rg >/dev/null 2>&1 || {
                print -u2 -- "dotfiles: configured search command is unavailable: rg"
                return 69
            }
            command rg -- "$dotfiles_search_regex" "$dotfiles_search_target"
            ;;
        grep)
            if [[ -d "$dotfiles_search_target" ]]; then
                command grep -rE -- "$dotfiles_search_regex" "$dotfiles_search_target"
            else
                command grep -E -- "$dotfiles_search_regex" "$dotfiles_search_target"
            fi
            ;;
    esac
}
