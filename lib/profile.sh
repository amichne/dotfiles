#!/usr/bin/env bash

dotfiles_profile_selection_file() {
    printf '%s' "${XDG_CONFIG_HOME:-$HOME/.config}/dotfiles/profiles"
}

dotfiles_profile_validate_list() {
    local dotfiles_profile_list="$1"
    local dotfiles_profile_name
    local dotfiles_old_ifs

    [ -n "$dotfiles_profile_list" ] || {
        dotfiles_error "profile selection must not be empty"
        return 65
    }

    dotfiles_old_ifs="$IFS"
    IFS=','
    for dotfiles_profile_name in $dotfiles_profile_list; do
        IFS="$dotfiles_old_ifs"
        dotfiles_require_safe_profile_name "$dotfiles_profile_name" || return
        if [ ! -f "$DOTFILES_ROOT/profiles/$dotfiles_profile_name.conf" ]; then
            dotfiles_error "profile does not exist: $dotfiles_profile_name"
            return 66
        fi
        IFS=','
    done
    IFS="$dotfiles_old_ifs"
}

dotfiles_profile_read_file() {
    local dotfiles_profile_file="$1"
    awk '
        /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
        {
            count++
            value = $0
        }
        END {
            if (count == 0) exit 1
            if (count > 1) {
                print "dotfiles: profile selection file must contain one data line" > "/dev/stderr"
                exit 65
            }
            print value
        }
    ' "$dotfiles_profile_file"
}

dotfiles_profile_selected() {
    local dotfiles_profile_value
    local dotfiles_profile_file

    if [ -n "${DOTFILES_PROFILES+x}" ]; then
        dotfiles_profile_value="$DOTFILES_PROFILES"
    else
        dotfiles_profile_file="$(dotfiles_profile_selection_file)"
        if [ -f "$dotfiles_profile_file" ]; then
            dotfiles_profile_value="$(dotfiles_profile_read_file "$dotfiles_profile_file")" || return
        else
            dotfiles_profile_value="portable"
        fi
    fi

    dotfiles_profile_validate_list "$dotfiles_profile_value" || return
    printf '%s' "$dotfiles_profile_value"
}

dotfiles_profile_set() {
    local dotfiles_profile_value="$1"
    local dotfiles_profile_file
    local dotfiles_profile_parent
    local dotfiles_profile_temporary
    dotfiles_profile_validate_list "$dotfiles_profile_value" || return

    dotfiles_profile_file="$(dotfiles_profile_selection_file)"
    dotfiles_profile_parent="$(dirname "$dotfiles_profile_file")"
    mkdir -p "$dotfiles_profile_parent"
    chmod 700 "$dotfiles_profile_parent" 2>/dev/null || true
    dotfiles_profile_temporary="$(mktemp "$dotfiles_profile_parent/.profiles.XXXXXX")" || return
    printf '%s\n' "$dotfiles_profile_value" >"$dotfiles_profile_temporary"
    chmod 600 "$dotfiles_profile_temporary"
    mv -f "$dotfiles_profile_temporary" "$dotfiles_profile_file"
}

dotfiles_profile_command() {
    local dotfiles_profile_action="${1:-get}"
    if [ "$#" -gt 0 ]; then
        shift
    fi

    case "$dotfiles_profile_action" in
        get)
            if [ "$#" -ne 0 ]; then
                dotfiles_error "usage: dotfiles profile get"
                return 64
            fi
            dotfiles_profile_selected
            printf '\n'
            ;;
        set)
            if [ "$#" -ne 1 ]; then
                dotfiles_error "usage: dotfiles profile set <profile[,profile]>"
                return 64
            fi
            dotfiles_profile_set "$1"
            ;;
        *)
            dotfiles_error "unknown profile command: $dotfiles_profile_action"
            return 64
            ;;
    esac
}
