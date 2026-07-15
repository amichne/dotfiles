#!/usr/bin/env bash

dotfiles_plugins_manifest_file() {
    printf '%s' "${DOTFILES_PLUGIN_MANIFEST_FILE:-$DOTFILES_ROOT/config/plugins.tsv}"
}

dotfiles_plugins_validate_root() {
    local dotfiles_plugin_root="$1"
    if [ -L "$dotfiles_plugin_root" ]; then
        dotfiles_error "external plugin root must not be a symlink: $dotfiles_plugin_root"
        return 65
    fi
    if [ ! -d "$dotfiles_plugin_root" ]; then
        dotfiles_error "plugin root is missing: $dotfiles_plugin_root"
        return 66
    fi
}

dotfiles_plugins_normalize_manifest() {
    local dotfiles_plugin_root="$1"
    local dotfiles_plugins_source="$2"
    dotfiles_plugins_validate_root "$dotfiles_plugin_root" || return
    dotfiles_require_file "$dotfiles_plugins_source" || return
    if [ -L "$dotfiles_plugins_source" ]; then
        dotfiles_error "plugin manifest must not be a symlink: $dotfiles_plugins_source"
        return 65
    fi

    awk -F '\t' -v OFS='\t' -v plugin_root="$dotfiles_plugin_root" '
        function fail(message) {
            print "dotfiles: " message > "/dev/stderr"
            failed = 1
        }
        /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
        {
            if (NF != 6) {
                fail("invalid plugin row " FNR ": expected 6 tab-separated fields")
                next
            }
            if ($1 !~ /^[a-z][a-z0-9-]*$/) {
                fail("invalid plugin id: " $1)
                next
            }
            if (seen[$1]++) {
                fail("duplicate plugin id: " $1)
                next
            }
            if ($2 == "" || $2 ~ /^\// || $2 ~ /(^|\/)\.\.($|\/)/) {
                fail("plugin path must remain relative to the trusted root: " $2)
                next
            }
            if ($3 != "-" && $3 !~ /^feature\.[a-z][a-z0-9-]*$/) {
                fail("invalid plugin feature for " $1 ": " $3)
                next
            }
            if ($4 != "zsh") {
                fail("unsupported plugin shell for " $1 ": " $4)
                next
            }
            if ($5 != "-" && $5 !~ /^[a-z][a-z0-9-]*(,[a-z][a-z0-9-]*)*$/) {
                fail("invalid plugin dependency list for " $1 ": " $5)
                next
            }
            if ($6 == "") {
                fail("missing plugin description for " $1)
                next
            }
            $2 = plugin_root "/" $2
            print
        }
        END { if (failed) exit 65 }
    ' "$dotfiles_plugins_source"
}

dotfiles_plugins_normalize() {
    local dotfiles_plugins_temp
    local dotfiles_plugins_source
    local dotfiles_external_root
    local dotfiles_external_manifest
    dotfiles_plugins_temp="$(mktemp "${TMPDIR:-/tmp}/dotfiles.manifests.XXXXXX")" || return
    : >"$dotfiles_plugins_temp"

    if [ -n "${DOTFILES_PLUGIN_MANIFEST_FILE+x}" ]; then
        dotfiles_plugins_source="$(dotfiles_plugins_manifest_file)"
        dotfiles_plugins_normalize_manifest "$DOTFILES_ROOT" "$dotfiles_plugins_source" >"$dotfiles_plugins_temp" || {
            rm -f "$dotfiles_plugins_temp"
            return 65
        }
    else
        dotfiles_plugins_normalize_manifest "$DOTFILES_ROOT" "$DOTFILES_ROOT/config/plugins.tsv" >"$dotfiles_plugins_temp" || {
            rm -f "$dotfiles_plugins_temp"
            return 65
        }
        while IFS= read -r dotfiles_external_root; do
            [ -n "$dotfiles_external_root" ] || continue
            dotfiles_plugins_validate_root "$dotfiles_external_root" || {
                rm -f "$dotfiles_plugins_temp"
                return
            }
            dotfiles_external_root="$(cd "$dotfiles_external_root" && pwd -P)" || {
                rm -f "$dotfiles_plugins_temp"
                return 65
            }
            dotfiles_external_manifest="$dotfiles_external_root/plugins.tsv"
            dotfiles_plugins_normalize_manifest "$dotfiles_external_root" "$dotfiles_external_manifest" >>"$dotfiles_plugins_temp" || {
                rm -f "$dotfiles_plugins_temp"
                return 65
            }
        done < <(dotfiles_config_external_roots)
    fi

    awk -F '\t' '
        seen[$1]++ {
            print "dotfiles: duplicate plugin id: " $1 > "/dev/stderr"
            failed = 1
            next
        }
        { print }
        END { if (failed) exit 65 }
    ' "$dotfiles_plugins_temp"
    local dotfiles_plugins_status=$?
    rm -f "$dotfiles_plugins_temp"
    return "$dotfiles_plugins_status"
}

dotfiles_plugins_trusted_roots() {
    printf '%s\n' "$DOTFILES_ROOT"
    if [ -z "${DOTFILES_PLUGIN_MANIFEST_FILE+x}" ]; then
        dotfiles_config_external_roots
    fi
}

dotfiles_plugin_physical_path() {
    local dotfiles_plugin_candidate="$1"

    if [ -L "$dotfiles_plugin_candidate" ]; then
        dotfiles_error "plugin file must not be a symlink: $dotfiles_plugin_candidate"
        return 65
    fi
    if [ ! -f "$dotfiles_plugin_candidate" ]; then
        dotfiles_error "plugin file is missing: $dotfiles_plugin_candidate"
        return 66
    fi

    local dotfiles_plugin_parent
    local dotfiles_plugin_physical
    local dotfiles_trusted_root
    local dotfiles_trusted_physical
    local dotfiles_plugin_is_trusted=0
    dotfiles_plugin_parent="$(cd "$(dirname "$dotfiles_plugin_candidate")" && pwd -P)" || return
    dotfiles_plugin_physical="$dotfiles_plugin_parent/$(basename "$dotfiles_plugin_candidate")"

    while IFS= read -r dotfiles_trusted_root; do
        [ -n "$dotfiles_trusted_root" ] || continue
        dotfiles_plugins_validate_root "$dotfiles_trusted_root" || return
        dotfiles_trusted_physical="$(cd "$dotfiles_trusted_root" && pwd -P)" || return
        case "$dotfiles_plugin_physical" in
            "$dotfiles_trusted_physical"/*)
                dotfiles_plugin_is_trusted=1
                break
                ;;
        esac
    done < <(dotfiles_plugins_trusted_roots)

    if [ "$dotfiles_plugin_is_trusted" -ne 1 ]; then
        dotfiles_error "plugin path escapes all trusted roots: $dotfiles_plugin_candidate"
        return 65
    fi
    printf '%s' "$dotfiles_plugin_physical"
}

dotfiles_plugins_make_state() {
    local dotfiles_plugins_temp_dir="$1"
    dotfiles_plugins_normalize >"$dotfiles_plugins_temp_dir/plugins.tsv" || return
    dotfiles_dependencies_normalize >"$dotfiles_plugins_temp_dir/dependencies.tsv" || return
    dotfiles_config_resolve list >"$dotfiles_plugins_temp_dir/config.tsv" || return
}

dotfiles_plugins_validate() {
    local dotfiles_plugins_temp_dir
    dotfiles_plugins_temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles.plugins.XXXXXX")" || return
    if ! dotfiles_plugins_make_state "$dotfiles_plugins_temp_dir"; then
        rm -rf "$dotfiles_plugins_temp_dir"
        return 65
    fi

    local dotfiles_plugin_id
    local dotfiles_plugin_relative
    local dotfiles_plugin_feature
    local dotfiles_plugin_dependencies
    local dotfiles_plugin_feature_value
    local dotfiles_dependency_id
    local dotfiles_old_ifs

    while IFS=$'\t' read -r dotfiles_plugin_id dotfiles_plugin_relative dotfiles_plugin_feature _dotfiles_plugin_shell dotfiles_plugin_dependencies _dotfiles_plugin_description; do
        dotfiles_plugin_physical_path "$dotfiles_plugin_relative" >/dev/null || {
            rm -rf "$dotfiles_plugins_temp_dir"
            return
        }

        if [ "$dotfiles_plugin_feature" != "-" ]; then
            dotfiles_plugin_feature_value="$(awk -F '\t' -v feature="$dotfiles_plugin_feature" '$1 == feature { print $2; found = 1; exit } END { if (!found) exit 1 }' "$dotfiles_plugins_temp_dir/config.tsv")" || {
                dotfiles_error "plugin $dotfiles_plugin_id references unknown feature: $dotfiles_plugin_feature"
                rm -rf "$dotfiles_plugins_temp_dir"
                return 65
            }
            case "$dotfiles_plugin_feature_value" in
                on|off|auto) ;;
                *)
                    dotfiles_error "plugin $dotfiles_plugin_id feature is not a toggle: $dotfiles_plugin_feature"
                    rm -rf "$dotfiles_plugins_temp_dir"
                    return 65
                    ;;
            esac
        fi

        if [ "$dotfiles_plugin_dependencies" != "-" ]; then
            dotfiles_old_ifs="$IFS"
            IFS=','
            for dotfiles_dependency_id in $dotfiles_plugin_dependencies; do
                IFS="$dotfiles_old_ifs"
                if ! awk -F '\t' -v dependency_id="$dotfiles_dependency_id" '$1 == dependency_id { found = 1 } END { exit found ? 0 : 1 }' "$dotfiles_plugins_temp_dir/dependencies.tsv"; then
                    dotfiles_error "plugin $dotfiles_plugin_id references unknown dependency: $dotfiles_dependency_id"
                    rm -rf "$dotfiles_plugins_temp_dir"
                    return 65
                fi
                IFS=','
            done
            IFS="$dotfiles_old_ifs"
        fi
    done <"$dotfiles_plugins_temp_dir/plugins.tsv"

    rm -rf "$dotfiles_plugins_temp_dir"
}

dotfiles_plugins_paths() {
    dotfiles_plugins_validate || return

    local dotfiles_plugins_temp_dir
    dotfiles_plugins_temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles.paths.XXXXXX")" || return
    if ! dotfiles_plugins_make_state "$dotfiles_plugins_temp_dir"; then
        rm -rf "$dotfiles_plugins_temp_dir"
        return 65
    fi

    local dotfiles_plugin_id
    local dotfiles_plugin_relative
    local dotfiles_plugin_feature
    local dotfiles_plugin_dependencies
    local dotfiles_plugin_feature_value
    local dotfiles_plugin_load
    local dotfiles_dependency_id
    local dotfiles_old_ifs

    while IFS=$'\t' read -r dotfiles_plugin_id dotfiles_plugin_relative dotfiles_plugin_feature _dotfiles_plugin_shell dotfiles_plugin_dependencies _dotfiles_plugin_description; do
        dotfiles_plugin_feature_value="on"
        if [ "$dotfiles_plugin_feature" != "-" ]; then
            dotfiles_plugin_feature_value="$(awk -F '\t' -v feature="$dotfiles_plugin_feature" '$1 == feature { print $2; exit }' "$dotfiles_plugins_temp_dir/config.tsv")"
        fi

        [ "$dotfiles_plugin_feature_value" != "off" ] || continue
        dotfiles_plugin_load=1

        if [ "$dotfiles_plugin_dependencies" != "-" ]; then
            dotfiles_old_ifs="$IFS"
            IFS=','
            for dotfiles_dependency_id in $dotfiles_plugin_dependencies; do
                IFS="$dotfiles_old_ifs"
                if ! dotfiles_dependency_available "$dotfiles_dependency_id"; then
                    if [ "$dotfiles_plugin_feature_value" = "on" ]; then
                        dotfiles_error "enabled plugin $dotfiles_plugin_id is missing dependency: $dotfiles_dependency_id"
                        rm -rf "$dotfiles_plugins_temp_dir"
                        return 69
                    fi
                    dotfiles_plugin_load=0
                    break
                fi
                IFS=','
            done
            IFS="$dotfiles_old_ifs"
        fi

        if [ "$dotfiles_plugin_load" -eq 1 ]; then
            dotfiles_plugin_physical_path "$dotfiles_plugin_relative" || {
                rm -rf "$dotfiles_plugins_temp_dir"
                return
            }
            printf '\n'
        fi
    done <"$dotfiles_plugins_temp_dir/plugins.tsv"

    rm -rf "$dotfiles_plugins_temp_dir"
}

dotfiles_plugins_list() {
    dotfiles_plugins_validate || return

    local dotfiles_plugins_temp_dir
    dotfiles_plugins_temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles.list.XXXXXX")" || return
    if ! dotfiles_plugins_make_state "$dotfiles_plugins_temp_dir"; then
        rm -rf "$dotfiles_plugins_temp_dir"
        return 65
    fi

    local dotfiles_plugin_id
    local dotfiles_plugin_file
    local dotfiles_plugin_feature
    local dotfiles_plugin_dependencies
    local dotfiles_plugin_description
    local dotfiles_plugin_feature_value
    local dotfiles_plugin_state
    local dotfiles_dependency_id
    local dotfiles_old_ifs

    printf 'id\tstate\tfeature\tdependencies\tpath\tdescription\n'
    while IFS=$'\t' read -r dotfiles_plugin_id dotfiles_plugin_file dotfiles_plugin_feature _dotfiles_plugin_shell dotfiles_plugin_dependencies dotfiles_plugin_description; do
        dotfiles_plugin_feature_value="on"
        if [ "$dotfiles_plugin_feature" != "-" ]; then
            dotfiles_plugin_feature_value="$(awk -F '\t' -v feature="$dotfiles_plugin_feature" '$1 == feature { print $2; exit }' "$dotfiles_plugins_temp_dir/config.tsv")"
        fi

        dotfiles_plugin_state="active"
        if [ "$dotfiles_plugin_feature_value" = "off" ]; then
            dotfiles_plugin_state="disabled"
        elif [ "$dotfiles_plugin_dependencies" != "-" ]; then
            dotfiles_old_ifs="$IFS"
            IFS=','
            for dotfiles_dependency_id in $dotfiles_plugin_dependencies; do
                IFS="$dotfiles_old_ifs"
                if ! dotfiles_dependency_available "$dotfiles_dependency_id"; then
                    if [ "$dotfiles_plugin_feature_value" = "on" ]; then
                        dotfiles_plugin_state="missing-required"
                    else
                        dotfiles_plugin_state="unavailable-auto"
                    fi
                    break
                fi
                IFS=','
            done
            IFS="$dotfiles_old_ifs"
        fi

        printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
            "$dotfiles_plugin_id" \
            "$dotfiles_plugin_state" \
            "$dotfiles_plugin_feature" \
            "$dotfiles_plugin_dependencies" \
            "$dotfiles_plugin_file" \
            "$dotfiles_plugin_description"
    done <"$dotfiles_plugins_temp_dir/plugins.tsv"

    rm -rf "$dotfiles_plugins_temp_dir"
}

dotfiles_plugins_command() {
    local dotfiles_plugins_action="${1:-list}"
    if [ "$#" -gt 0 ]; then
        shift
    fi
    if [ "$#" -ne 0 ]; then
        dotfiles_error "usage: dotfiles plugins <validate|list|paths>"
        return 64
    fi

    case "$dotfiles_plugins_action" in
        validate) dotfiles_plugins_validate ;;
        list) dotfiles_plugins_list ;;
        paths) dotfiles_plugins_paths ;;
        *)
            dotfiles_error "unknown plugins command: $dotfiles_plugins_action"
            return 64
            ;;
    esac
}
