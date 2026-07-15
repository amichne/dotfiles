#!/usr/bin/env bash

dotfiles_status_local_config_file() {
    if [ -n "${DOTFILES_CONFIG_FILE+x}" ]; then
        printf '%s' "$DOTFILES_CONFIG_FILE"
    else
        printf '%s' "${XDG_CONFIG_HOME:-$HOME/.config}/dotfiles/config.conf"
    fi
}

dotfiles_status_command() {
    if [ "$#" -ne 0 ]; then
        dotfiles_error "usage: dotfiles status"
        return 64
    fi

    dotfiles_config_resolve validate || return
    dotfiles_plugins_validate || return

    local dotfiles_status_zshrc
    local dotfiles_status_owner="absent"
    dotfiles_status_zshrc="$(dotfiles_install_zshrc)"
    if dotfiles_install_has_marker "$dotfiles_status_zshrc" "$DOTFILES_INSTALL_MARKER_START"; then
        dotfiles_status_owner="present"
    fi

    printf 'dotfiles status\n'
    printf 'root: %s\n' "$DOTFILES_ROOT"
    printf 'profiles: %s\n' "$(dotfiles_profile_selected)"
    printf 'local config: %s\n' "$(dotfiles_status_local_config_file)"
    printf 'zshrc: %s\n' "$dotfiles_status_zshrc"
    printf 'managed block: %s\n' "$dotfiles_status_owner"
    printf 'legacy blocks: %s\n' "$(dotfiles_install_legacy_blocks "$dotfiles_status_zshrc")"
    printf 'runtime loaded: %s\n' "${DOTFILES_RUNTIME_LOADED:-0}"
}

dotfiles_doctor_run() {
    local dotfiles_doctor_strict="$1"
    dotfiles_config_resolve validate || return
    printf 'config: ok\n'
    dotfiles_plugins_validate || return
    printf 'plugins: ok\n'

    local dotfiles_doctor_temp_dir
    dotfiles_doctor_temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles.doctor.XXXXXX")" || return
    if ! dotfiles_plugins_make_state "$dotfiles_doctor_temp_dir"; then
        rm -rf "$dotfiles_doctor_temp_dir"
        return 65
    fi

    local dotfiles_plugin_id
    local dotfiles_plugin_feature
    local dotfiles_plugin_dependencies
    local dotfiles_plugin_feature_value
    local dotfiles_dependency_id
    local dotfiles_dependency_missing
    local dotfiles_dependency_install_hint
    local dotfiles_doctor_auto_missing=0
    local dotfiles_old_ifs

    while IFS=$'\t' read -r dotfiles_plugin_id _dotfiles_plugin_relative dotfiles_plugin_feature _dotfiles_plugin_shell dotfiles_plugin_dependencies _dotfiles_plugin_description; do
        dotfiles_plugin_feature_value="on"
        if [ "$dotfiles_plugin_feature" != "-" ]; then
            dotfiles_plugin_feature_value="$(awk -F '\t' -v feature="$dotfiles_plugin_feature" '$1 == feature { print $2; exit }' "$dotfiles_doctor_temp_dir/config.tsv")"
        fi

        if [ "$dotfiles_plugin_feature_value" = "off" ]; then
            printf '%s: disabled\n' "$dotfiles_plugin_id"
            continue
        fi

        dotfiles_dependency_missing=""
        if [ "$dotfiles_plugin_dependencies" != "-" ]; then
            dotfiles_old_ifs="$IFS"
            IFS=','
            for dotfiles_dependency_id in $dotfiles_plugin_dependencies; do
                IFS="$dotfiles_old_ifs"
                if ! dotfiles_dependency_available "$dotfiles_dependency_id"; then
                    dotfiles_dependency_missing="$dotfiles_dependency_id"
                    break
                fi
                IFS=','
            done
            IFS="$dotfiles_old_ifs"
        fi

        if [ -n "$dotfiles_dependency_missing" ]; then
            dotfiles_dependency_install_hint="$(dotfiles_dependency_hint "$dotfiles_dependency_missing" || true)"
            if [ "$dotfiles_plugin_feature_value" = "on" ]; then
                dotfiles_error "$dotfiles_plugin_id: missing required dependency $dotfiles_dependency_missing"
                if [ -n "$dotfiles_dependency_install_hint" ]; then
                    dotfiles_error "$dotfiles_dependency_install_hint"
                fi
                rm -rf "$dotfiles_doctor_temp_dir"
                return 69
            fi
            printf '%s: unavailable (auto)' "$dotfiles_plugin_id"
            if [ -n "$dotfiles_dependency_install_hint" ]; then
                printf ' - %s' "$dotfiles_dependency_install_hint"
            fi
            printf '\n'
            dotfiles_doctor_auto_missing=1
        else
            printf '%s: available (%s)\n' "$dotfiles_plugin_id" "$dotfiles_plugin_feature_value"
        fi
    done <"$dotfiles_doctor_temp_dir/plugins.tsv"

    rm -rf "$dotfiles_doctor_temp_dir"
    if [ "$dotfiles_doctor_strict" -eq 1 ] && [ "$dotfiles_doctor_auto_missing" -eq 1 ]; then
        dotfiles_error "strict doctor found unavailable automatic integrations"
        return 69
    fi
    printf 'doctor: ok\n'
}

dotfiles_doctor_command() {
    local dotfiles_doctor_strict=0
    if [ "${1:-}" = "--strict" ] && [ "$#" -eq 1 ]; then
        dotfiles_doctor_strict=1
    elif [ "$#" -ne 0 ]; then
        dotfiles_error "usage: dotfiles doctor [--strict]"
        return 64
    fi
    dotfiles_doctor_run "$dotfiles_doctor_strict"
}
