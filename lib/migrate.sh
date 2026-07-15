#!/usr/bin/env bash

dotfiles_migrate_apollo_parse_file() {
    local dotfiles_migrate_file="$1"
    local dotfiles_migrate_line
    local dotfiles_migrate_line_number=0
    local dotfiles_migrate_name
    local dotfiles_migrate_raw
    local dotfiles_migrate_value
    local dotfiles_migrate_first
    local dotfiles_migrate_last
    local dotfiles_migrate_remainder

    while IFS= read -r dotfiles_migrate_line || [ -n "$dotfiles_migrate_line" ]; do
        dotfiles_migrate_line_number=$((dotfiles_migrate_line_number + 1))
        if [[ "$dotfiles_migrate_line" =~ ^[[:space:]]*$ ]] \
            || [[ "$dotfiles_migrate_line" =~ ^[[:space:]]*# ]]; then
            continue
        fi

        if [[ "$dotfiles_migrate_line" =~ ^[[:space:]]*(export[[:space:]]+)?([A-Z][A-Z0-9_]*)=(.*)$ ]]; then
            dotfiles_migrate_name="${BASH_REMATCH[2]}"
            dotfiles_migrate_raw="${BASH_REMATCH[3]}"
        else
            dotfiles_error "unsupported Apollo profile statement in $dotfiles_migrate_file:$dotfiles_migrate_line_number"
            return 65
        fi

        dotfiles_migrate_raw="$(printf '%s' "$dotfiles_migrate_raw" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
        case "$dotfiles_migrate_raw" in
            *'$('*|*'`'*|*';'*|*'|'*|*'&'*|*'<'*|*'>'*|*'\\'*)
                dotfiles_error "unsupported shell expression in $dotfiles_migrate_file:$dotfiles_migrate_line_number"
                return 65
                ;;
        esac

        dotfiles_migrate_value="$dotfiles_migrate_raw"
        if [ -n "$dotfiles_migrate_raw" ]; then
            dotfiles_migrate_first="${dotfiles_migrate_raw:0:1}"
            dotfiles_migrate_last="${dotfiles_migrate_raw: -1}"
            if { [ "$dotfiles_migrate_first" = "'" ] && [ "$dotfiles_migrate_last" = "'" ]; } \
                || { [ "$dotfiles_migrate_first" = '"' ] && [ "$dotfiles_migrate_last" = '"' ]; }; then
                dotfiles_migrate_value="${dotfiles_migrate_raw:1:${#dotfiles_migrate_raw}-2}"
            elif [ "$dotfiles_migrate_first" = "'" ] \
                || [ "$dotfiles_migrate_first" = '"' ] \
                || [ "$dotfiles_migrate_last" = "'" ] \
                || [ "$dotfiles_migrate_last" = '"' ] \
                || [[ "$dotfiles_migrate_raw" =~ [[:space:]] ]]; then
                dotfiles_error "unsupported shell expression in $dotfiles_migrate_file:$dotfiles_migrate_line_number"
                return 65
            fi
        fi

        dotfiles_migrate_value="${dotfiles_migrate_value//\$HOME/\$\{HOME\}}"
        dotfiles_migrate_remainder="${dotfiles_migrate_value//\$\{HOME\}/}"
        if [[ "$dotfiles_migrate_remainder" == *'$'* ]] \
            || [[ "$dotfiles_migrate_value" =~ [[:cntrl:]] ]]; then
            dotfiles_error "unsupported shell expression in $dotfiles_migrate_file:$dotfiles_migrate_line_number"
            return 65
        fi

        printf '%s\t%s\n' "$dotfiles_migrate_name" "$dotfiles_migrate_value"
    done <"$dotfiles_migrate_file"
}

dotfiles_migrate_apollo_collect() {
    local dotfiles_migrate_source="$1"
    local dotfiles_migrate_records="$2"
    local dotfiles_migrate_apollo_profile="$dotfiles_migrate_source/config/apollo/profile.env"
    local dotfiles_migrate_artemis_profile="$dotfiles_migrate_source/artemis/config/profile.env.example"

    if [ ! -d "$dotfiles_migrate_source" ]; then
        dotfiles_error "Apollo source directory is missing: $dotfiles_migrate_source"
        return 66
    fi
    if [ ! -f "$dotfiles_migrate_artemis_profile" ]; then
        dotfiles_error "Artemis profile is missing: $dotfiles_migrate_artemis_profile"
        return 66
    fi

    : >"$dotfiles_migrate_records"
    if [ -f "$dotfiles_migrate_apollo_profile" ]; then
        dotfiles_migrate_apollo_parse_file "$dotfiles_migrate_apollo_profile" >>"$dotfiles_migrate_records" || return
    fi
    dotfiles_migrate_apollo_parse_file "$dotfiles_migrate_artemis_profile" >>"$dotfiles_migrate_records" || return

    if ! awk -F '\t' '
        seen[$1]++ { print "dotfiles: duplicate Apollo profile key: " $1 > "/dev/stderr"; failed = 1 }
        END { exit failed }
    ' "$dotfiles_migrate_records"; then
        return 65
    fi
}

dotfiles_migrate_apollo_value() {
    local dotfiles_migrate_records="$1"
    local dotfiles_migrate_key="$2"
    awk -F '\t' -v key="$dotfiles_migrate_key" '$1 == key { print substr($0, length($1) + 2); found = 1 } END { exit !found }' \
        "$dotfiles_migrate_records"
}

dotfiles_migrate_apollo_emit_toggle() {
    local dotfiles_migrate_records="$1"
    local dotfiles_migrate_source_key="$2"
    local dotfiles_migrate_target_key="$3"
    local dotfiles_migrate_value

    if ! dotfiles_migrate_value="$(dotfiles_migrate_apollo_value "$dotfiles_migrate_records" "$dotfiles_migrate_source_key")"; then
        return 0
    fi
    case "$dotfiles_migrate_value" in
        0) printf '%s=off\n' "$dotfiles_migrate_target_key" ;;
        1) printf '%s=on\n' "$dotfiles_migrate_target_key" ;;
        *)
            dotfiles_error "invalid Apollo boolean for $dotfiles_migrate_source_key: $dotfiles_migrate_value"
            return 65
            ;;
    esac
}

dotfiles_migrate_apollo_emit_value() {
    local dotfiles_migrate_records="$1"
    local dotfiles_migrate_source_key="$2"
    local dotfiles_migrate_target_key="$3"
    local dotfiles_migrate_value

    if dotfiles_migrate_value="$(dotfiles_migrate_apollo_value "$dotfiles_migrate_records" "$dotfiles_migrate_source_key")"; then
        printf '%s=%s\n' "$dotfiles_migrate_target_key" "$dotfiles_migrate_value"
    fi
}

dotfiles_migrate_apollo_render_records() {
    local dotfiles_migrate_records="$1"
    local dotfiles_migrate_terminal_paths="0"
    local dotfiles_migrate_locale="0"

    dotfiles_migrate_apollo_emit_toggle "$dotfiles_migrate_records" ART_ENABLE_SDKMAN feature.sdkman
    dotfiles_migrate_apollo_emit_toggle "$dotfiles_migrate_records" ART_ENABLE_WARP_INTEGRATION feature.warp

    dotfiles_migrate_terminal_paths="$(dotfiles_migrate_apollo_value "$dotfiles_migrate_records" ART_ENABLE_TERMINAL_PATHS || printf '0')"
    case "$dotfiles_migrate_terminal_paths" in
        0) ;;
        1)
            dotfiles_migrate_apollo_emit_value "$dotfiles_migrate_records" ARTEMIS_PREPEND_PATHS path.prepend
            dotfiles_migrate_apollo_emit_value "$dotfiles_migrate_records" ARTEMIS_APPEND_PATHS path.append
            dotfiles_migrate_apollo_emit_value "$dotfiles_migrate_records" ARTEMIS_CODEX_HOME tools.codex-home
            dotfiles_migrate_apollo_emit_value "$dotfiles_migrate_records" ARTEMIS_JAVA_HOME tools.java-home
            ;;
        *)
            dotfiles_error "invalid Apollo boolean for ART_ENABLE_TERMINAL_PATHS: $dotfiles_migrate_terminal_paths"
            return 65
            ;;
    esac

    dotfiles_migrate_apollo_emit_value "$dotfiles_migrate_records" ARTEMIS_HISTFILE shell.history-file
    dotfiles_migrate_locale="$(dotfiles_migrate_apollo_value "$dotfiles_migrate_records" ART_ENABLE_LOCALE || printf '0')"
    case "$dotfiles_migrate_locale" in
        0) ;;
        1) dotfiles_migrate_apollo_emit_value "$dotfiles_migrate_records" ARTEMIS_LANG shell.locale ;;
        *)
            dotfiles_error "invalid Apollo boolean for ART_ENABLE_LOCALE: $dotfiles_migrate_locale"
            return 65
            ;;
    esac
}

dotfiles_migrate_apollo_with_records() {
    local dotfiles_migrate_action="$1"
    local dotfiles_migrate_source="$2"
    local dotfiles_migrate_records
    dotfiles_migrate_records="$(mktemp)" || return

    if ! dotfiles_migrate_apollo_collect "$dotfiles_migrate_source" "$dotfiles_migrate_records"; then
        rm -f "$dotfiles_migrate_records"
        return 65
    fi

    case "$dotfiles_migrate_action" in
        render)
            dotfiles_migrate_apollo_render_records "$dotfiles_migrate_records"
            ;;
        plan)
            printf 'source: %s\n' "$dotfiles_migrate_source"
            printf 'mapped configuration:\n'
            dotfiles_migrate_apollo_render_records "$dotfiles_migrate_records" | sed 's/^/  /'
            printf 'explicit ownership decisions:\n'
            printf '  APOLLO_PROFILE: external agent/provider concern\n'
            printf '  ART_ENABLE_GPG_TTY: retired from shell startup\n'
            printf '  config/gh/hosts.yml: excluded credential material\n'
            printf '  config/jira/config.yml: excluded enterprise host and credential material\n'
            ;;
    esac
    local dotfiles_migrate_status=$?
    rm -f "$dotfiles_migrate_records"
    return "$dotfiles_migrate_status"
}

dotfiles_migrate_apollo_command() {
    local dotfiles_migrate_action="${1:-plan}"
    local dotfiles_migrate_source=""
    if [ "$#" -gt 0 ]; then
        shift
    fi

    case "$dotfiles_migrate_action" in
        plan|render) ;;
        *)
            dotfiles_error "unknown Apollo migration command: $dotfiles_migrate_action"
            return 64
            ;;
    esac
    if [ "${1:-}" != "--source" ] || [ "$#" -ne 2 ] || [ -z "${2:-}" ]; then
        dotfiles_error "usage: dotfiles migrate apollo <$dotfiles_migrate_action> --source <path>"
        return 64
    fi
    dotfiles_migrate_source="$2"
    dotfiles_migrate_apollo_with_records "$dotfiles_migrate_action" "$dotfiles_migrate_source"
}

dotfiles_migrate_command() {
    local dotfiles_migrate_kind="${1:-}"
    if [ "$#" -gt 0 ]; then
        shift
    fi
    case "$dotfiles_migrate_kind" in
        apollo) dotfiles_migrate_apollo_command "$@" ;;
        *)
            dotfiles_error "usage: dotfiles migrate apollo <plan|render> --source <path>"
            return 64
            ;;
    esac
}
