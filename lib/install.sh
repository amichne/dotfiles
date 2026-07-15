#!/usr/bin/env bash

DOTFILES_INSTALL_MARKER_START="# >>> dotfiles shell entrypoint >>>"
DOTFILES_INSTALL_MARKER_END="# <<< dotfiles shell entrypoint <<<"
DOTFILES_APOLLO_MARKER_START="# >>> apollo shell entrypoint >>>"
DOTFILES_APOLLO_MARKER_END="# <<< apollo shell entrypoint <<<"
DOTFILES_ARTEMIS_MARKER_START="# >>> artemis shell entrypoint >>>"
DOTFILES_ARTEMIS_MARKER_END="# <<< artemis shell entrypoint <<<"

dotfiles_install_zshrc() {
    printf '%s' "${ZDOTDIR:-$HOME}/.zshrc"
}

dotfiles_install_local_config() {
    printf '%s' "${XDG_CONFIG_HOME:-$HOME/.config}/dotfiles/config.conf"
}

dotfiles_install_has_marker() {
    local dotfiles_install_file="$1"
    local dotfiles_install_marker="$2"
    [ -f "$dotfiles_install_file" ] && grep -qF "$dotfiles_install_marker" "$dotfiles_install_file"
}

dotfiles_install_has_unmanaged_apollo() {
    local dotfiles_install_file="$1"
    [ -f "$dotfiles_install_file" ] \
        && grep -Eq '^[[:space:]]*(source|\.)[[:space:]]+"?\$\{?APOLLO\}?"?/zsh-entrypoint\.sh"?[[:space:]]*$' "$dotfiles_install_file"
}

dotfiles_install_legacy_blocks() {
    local dotfiles_install_file="$1"
    local dotfiles_install_legacy=""

    if dotfiles_install_has_marker "$dotfiles_install_file" "$DOTFILES_APOLLO_MARKER_START"; then
        dotfiles_install_legacy="apollo"
    fi
    if dotfiles_install_has_unmanaged_apollo "$dotfiles_install_file"; then
        if [ -n "$dotfiles_install_legacy" ]; then
            dotfiles_install_legacy="$dotfiles_install_legacy,apollo-unmanaged"
        else
            dotfiles_install_legacy="apollo-unmanaged"
        fi
    fi
    if dotfiles_install_has_marker "$dotfiles_install_file" "$DOTFILES_ARTEMIS_MARKER_START"; then
        if [ -n "$dotfiles_install_legacy" ]; then
            dotfiles_install_legacy="$dotfiles_install_legacy,artemis"
        else
            dotfiles_install_legacy="artemis"
        fi
    fi
    printf '%s' "${dotfiles_install_legacy:-none}"
}

dotfiles_install_plan() {
    local dotfiles_install_target
    local dotfiles_install_config
    local dotfiles_install_owned="absent"
    dotfiles_install_target="$(dotfiles_install_zshrc)"
    dotfiles_install_config="$(dotfiles_install_local_config)"

    if dotfiles_install_has_marker "$dotfiles_install_target" "$DOTFILES_INSTALL_MARKER_START"; then
        dotfiles_install_owned="present"
    fi

    printf 'target: %s\n' "$dotfiles_install_target"
    printf 'dotfiles block: %s\n' "$dotfiles_install_owned"
    printf 'legacy blocks: %s\n' "$(dotfiles_install_legacy_blocks "$dotfiles_install_target")"
    if [ -f "$dotfiles_install_config" ]; then
        printf 'local config: present (%s)\n' "$dotfiles_install_config"
    else
        printf 'local config: will create (%s)\n' "$dotfiles_install_config"
    fi
}

dotfiles_install_filter_blocks() {
    local dotfiles_install_source="$1"
    local dotfiles_install_destination="$2"
    local dotfiles_install_migrate="$3"

    if [ ! -f "$dotfiles_install_source" ]; then
        : >"$dotfiles_install_destination"
        return
    fi

    awk \
        -v dot_start="$DOTFILES_INSTALL_MARKER_START" \
        -v dot_end="$DOTFILES_INSTALL_MARKER_END" \
        -v apollo_start="$DOTFILES_APOLLO_MARKER_START" \
        -v apollo_end="$DOTFILES_APOLLO_MARKER_END" \
        -v artemis_start="$DOTFILES_ARTEMIS_MARKER_START" \
        -v artemis_end="$DOTFILES_ARTEMIS_MARKER_END" \
        -v migrate="$dotfiles_install_migrate" '
            {
                compact_line = $0
                gsub(/[[:space:]]/, "", compact_line)
            }
            $0 == dot_start { skip = "dotfiles"; next }
            $0 == dot_end && skip == "dotfiles" { skip = ""; next }
            migrate == 1 && $0 == apollo_start { skip = "apollo"; next }
            migrate == 1 && $0 == apollo_end && skip == "apollo" { skip = ""; next }
            migrate == 1 && $0 == artemis_start { skip = "artemis"; next }
            migrate == 1 && $0 == artemis_end && skip == "artemis" { skip = ""; next }
            migrate == 1 && $0 ~ /^[[:space:]]*export[[:space:]]+APOLLO=/ { next }
            migrate == 1 && compact_line ~ /^(source|[.])"?([$]APOLLO|[$][{]APOLLO[}])"?\/zsh-entrypoint[.]sh"?$/ { next }
            skip == "" { print }
        ' "$dotfiles_install_source" >"$dotfiles_install_destination"
}

dotfiles_install_quote_single() {
    printf '%s' "$1" | sed "s/'/'\\\\''/g"
}

dotfiles_install_preserve_mode() {
    local dotfiles_install_original="$1"
    local dotfiles_install_temporary="$2"
    local dotfiles_install_mode

    [ -f "$dotfiles_install_original" ] || return 0
    dotfiles_install_mode="$(stat -f '%Lp' "$dotfiles_install_original" 2>/dev/null || stat -c '%a' "$dotfiles_install_original" 2>/dev/null || true)"
    if [ -n "$dotfiles_install_mode" ]; then
        chmod "$dotfiles_install_mode" "$dotfiles_install_temporary"
    fi
}

dotfiles_install_atomic_replace() {
    local dotfiles_install_target="$1"
    local dotfiles_install_content="$2"
    local dotfiles_install_parent
    local dotfiles_install_temporary

    dotfiles_install_parent="$(dirname "$dotfiles_install_target")"
    mkdir -p "$dotfiles_install_parent"
    dotfiles_install_temporary="$(mktemp "$dotfiles_install_parent/.dotfiles.zshrc.XXXXXX")" || return
    cp "$dotfiles_install_content" "$dotfiles_install_temporary" || {
        rm -f "$dotfiles_install_temporary"
        return 1
    }
    dotfiles_install_preserve_mode "$dotfiles_install_target" "$dotfiles_install_temporary"
    mv -f "$dotfiles_install_temporary" "$dotfiles_install_target"
}

dotfiles_install_seed_local_config() {
    local dotfiles_install_config
    dotfiles_install_config="$(dotfiles_install_local_config)"
    if [ -f "$dotfiles_install_config" ]; then
        return 0
    fi

    mkdir -p "$(dirname "$dotfiles_install_config")"
    chmod 700 "$(dirname "$dotfiles_install_config")" 2>/dev/null || true
    {
        printf '# Machine-local dotfiles configuration. Data only; do not write shell code.\n'
        printf '# See: %s/docs/configuration.md\n' "$DOTFILES_ROOT"
    } >"$dotfiles_install_config"
    chmod 600 "$dotfiles_install_config"
}

dotfiles_install_apply() {
    local dotfiles_install_migrate=0
    if [ "${1:-}" = "--migrate" ] && [ "$#" -eq 1 ]; then
        dotfiles_install_migrate=1
    elif [ "$#" -ne 0 ]; then
        dotfiles_error "usage: dotfiles install apply [--migrate]"
        return 64
    fi

    local dotfiles_install_target
    local dotfiles_install_legacy
    local dotfiles_install_parent
    local dotfiles_install_filtered
    local dotfiles_install_next
    local dotfiles_install_escaped_root
    dotfiles_install_target="$(dotfiles_install_zshrc)"
    dotfiles_install_legacy="$(dotfiles_install_legacy_blocks "$dotfiles_install_target")"

    if [ "$dotfiles_install_legacy" != "none" ] && [ "$dotfiles_install_migrate" -ne 1 ]; then
        dotfiles_error "legacy shell blocks detected; rerun with --migrate"
        return 65
    fi

    dotfiles_install_parent="$(dirname "$dotfiles_install_target")"
    mkdir -p "$dotfiles_install_parent"
    dotfiles_install_filtered="$(mktemp "$dotfiles_install_parent/.dotfiles.filtered.XXXXXX")" || return
    dotfiles_install_next="$(mktemp "$dotfiles_install_parent/.dotfiles.next.XXXXXX")" || {
        rm -f "$dotfiles_install_filtered"
        return 1
    }

    dotfiles_install_filter_blocks "$dotfiles_install_target" "$dotfiles_install_filtered" "$dotfiles_install_migrate" || {
        rm -f "$dotfiles_install_filtered" "$dotfiles_install_next"
        return 1
    }
    dotfiles_install_escaped_root="$(dotfiles_install_quote_single "$DOTFILES_ROOT")"

    cp "$dotfiles_install_filtered" "$dotfiles_install_next"
    if [ -s "$dotfiles_install_next" ]; then
        printf '\n' >>"$dotfiles_install_next"
    fi
    {
        printf '%s\n' "$DOTFILES_INSTALL_MARKER_START"
        printf "export DOTFILES_ROOT='%s'\n" "$dotfiles_install_escaped_root"
        printf 'if [[ -r "$DOTFILES_ROOT/shell/zsh/entrypoint.zsh" ]]; then\n'
        printf '    source "$DOTFILES_ROOT/shell/zsh/entrypoint.zsh"\n'
        printf 'else\n'
        printf '    print -u2 -- "dotfiles: missing entrypoint: $DOTFILES_ROOT/shell/zsh/entrypoint.zsh"\n'
        printf 'fi\n'
        printf '%s\n' "$DOTFILES_INSTALL_MARKER_END"
    } >>"$dotfiles_install_next"

    dotfiles_install_atomic_replace "$dotfiles_install_target" "$dotfiles_install_next" || {
        rm -f "$dotfiles_install_filtered" "$dotfiles_install_next"
        return 1
    }
    rm -f "$dotfiles_install_filtered" "$dotfiles_install_next"
    dotfiles_install_seed_local_config
}

dotfiles_install_uninstall() {
    if [ "$#" -ne 0 ]; then
        dotfiles_error "usage: dotfiles install uninstall"
        return 64
    fi

    local dotfiles_install_target
    local dotfiles_install_parent
    local dotfiles_install_filtered
    dotfiles_install_target="$(dotfiles_install_zshrc)"
    [ -f "$dotfiles_install_target" ] || return 0

    dotfiles_install_parent="$(dirname "$dotfiles_install_target")"
    dotfiles_install_filtered="$(mktemp "$dotfiles_install_parent/.dotfiles.uninstall.XXXXXX")" || return
    dotfiles_install_filter_blocks "$dotfiles_install_target" "$dotfiles_install_filtered" 0 || {
        rm -f "$dotfiles_install_filtered"
        return 1
    }
    dotfiles_install_atomic_replace "$dotfiles_install_target" "$dotfiles_install_filtered" || {
        rm -f "$dotfiles_install_filtered"
        return 1
    }
    rm -f "$dotfiles_install_filtered"
}

dotfiles_install_command() {
    local dotfiles_install_action="${1:-plan}"
    if [ "$#" -gt 0 ]; then
        shift
    fi

    case "$dotfiles_install_action" in
        plan)
            if [ "$#" -ne 0 ]; then
                dotfiles_error "usage: dotfiles install plan"
                return 64
            fi
            dotfiles_install_plan
            ;;
        apply) dotfiles_install_apply "$@" ;;
        uninstall) dotfiles_install_uninstall "$@" ;;
        *)
            dotfiles_error "unknown install command: $dotfiles_install_action"
            return 64
            ;;
    esac
}
