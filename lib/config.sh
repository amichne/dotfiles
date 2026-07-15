#!/usr/bin/env bash

dotfiles_config_schema_file() {
    printf '%s' "${DOTFILES_SCHEMA_FILE:-$DOTFILES_ROOT/config/schema.tsv}"
}

dotfiles_config_collect_layers() {
    DOTFILES_CONFIG_LAYERS=()

    local dotfiles_profiles
    dotfiles_profiles="$(dotfiles_profile_selected)" || return
    local dotfiles_profile_name
    local dotfiles_old_ifs

    if [ -n "$dotfiles_profiles" ]; then
        dotfiles_old_ifs="$IFS"
        IFS=','
        for dotfiles_profile_name in $dotfiles_profiles; do
            IFS="$dotfiles_old_ifs"
            dotfiles_require_safe_profile_name "$dotfiles_profile_name" || return
            DOTFILES_CONFIG_LAYERS+=("$DOTFILES_ROOT/profiles/$dotfiles_profile_name.conf")
            IFS=','
        done
        IFS="$dotfiles_old_ifs"
    fi

    local dotfiles_external_profiles="${DOTFILES_PROFILE_FILES:-}"
    local dotfiles_external_profile
    if [ -n "$dotfiles_external_profiles" ]; then
        dotfiles_old_ifs="$IFS"
        IFS=':'
        for dotfiles_external_profile in $dotfiles_external_profiles; do
            IFS="$dotfiles_old_ifs"
            if [ -z "$dotfiles_external_profile" ]; then
                dotfiles_error "DOTFILES_PROFILE_FILES contains an empty path"
                return 65
            fi
            DOTFILES_CONFIG_LAYERS+=("$dotfiles_external_profile")
            IFS=':'
        done
        IFS="$dotfiles_old_ifs"
    fi

    local dotfiles_local_config
    if [ -n "${DOTFILES_CONFIG_FILE+x}" ]; then
        dotfiles_local_config="$DOTFILES_CONFIG_FILE"
        if [ -z "$dotfiles_local_config" ]; then
            dotfiles_error "DOTFILES_CONFIG_FILE must not be empty"
            return 65
        fi
        DOTFILES_CONFIG_LAYERS+=("$dotfiles_local_config")
    else
        dotfiles_local_config="${XDG_CONFIG_HOME:-$HOME/.config}/dotfiles/config.conf"
        if [ -f "$dotfiles_local_config" ]; then
            DOTFILES_CONFIG_LAYERS+=("$dotfiles_local_config")
        fi
    fi

    local dotfiles_layer_file
    for dotfiles_layer_file in "${DOTFILES_CONFIG_LAYERS[@]}"; do
        dotfiles_require_file "$dotfiles_layer_file" || return
    done
}

dotfiles_config_resolve() {
    local dotfiles_output_mode="$1"
    local dotfiles_schema_file
    dotfiles_schema_file="$(dotfiles_config_schema_file)"
    dotfiles_require_file "$dotfiles_schema_file" || return
    dotfiles_config_collect_layers || return

    awk \
        -v schema_file="$dotfiles_schema_file" \
        -v output_mode="$dotfiles_output_mode" \
        -v config_home="$HOME" \
        -v config_xdg_home="${XDG_CONFIG_HOME:-$HOME/.config}" \
        -v config_root="$DOTFILES_ROOT" \
        -f - \
        "$dotfiles_schema_file" "${DOTFILES_CONFIG_LAYERS[@]}" <<'AWK'
BEGIN {
    FS = "\t"
    OFS = "\t"
    failed = 0
}

function fail(message) {
    if (!failed) {
        print "dotfiles: " message > "/dev/stderr"
    }
    failed = 1
}

function valid_name(value) {
    return value ~ /^[A-Za-z_][A-Za-z0-9_]*$/
}

function valid_key(value) {
    return value ~ /^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)+$/
}

function replace_literal(input, needle, replacement,    position, output) {
    output = ""
    while ((position = index(input, needle)) > 0) {
        output = output substr(input, 1, position - 1) replacement
        input = substr(input, position + length(needle))
    }
    return output input
}

function expand_placeholders(key, value,    placeholder_start, placeholder) {
    value = replace_literal(value, "${HOME}", config_home)
    value = replace_literal(value, "${XDG_CONFIG_HOME}", config_xdg_home)
    value = replace_literal(value, "${DOTFILES_ROOT}", config_root)

    placeholder_start = match(value, /\$\{[A-Za-z_][A-Za-z0-9_]*\}/)
    if (placeholder_start > 0) {
        placeholder = substr(value, placeholder_start, RLENGTH)
        fail("unsupported placeholder for " key ": " placeholder)
    }
    return value
}

function value_is_valid(key, type, value,    choices, choice_count, choice_index, path_count, path_index) {
    if (type == "bool") {
        if (value == "0" || value == "1") return 1
        fail("invalid bool for " key ": " value)
        return 0
    }
    if (type == "toggle") {
        if (value == "on" || value == "off" || value == "auto") return 1
        fail("invalid toggle for " key ": " value)
        return 0
    }
    if (type == "uint") {
        if (value ~ /^[0-9]+$/) return 1
        fail("invalid uint for " key ": " value)
        return 0
    }
    if (type == "command") {
        if (value ~ /^[A-Za-z0-9_.+-]+$/) return 1
        fail("invalid command for " key ": " value)
        return 0
    }
    if (type ~ /^enum:/) {
        choice_count = split(substr(type, 6), choices, ",")
        for (choice_index = 1; choice_index <= choice_count; choice_index++) {
            if (value == choices[choice_index]) return 1
        }
        fail("invalid enum for " key ": " value)
        return 0
    }
    if (type == "path") {
        if (value == "" || value ~ /^\//) return 1
        fail("invalid path for " key ": " value)
        return 0
    }
    if (type == "path-list") {
        if (value == "") return 1
        path_count = split(value, choices, ":")
        for (path_index = 1; path_index <= path_count; path_index++) {
            if (choices[path_index] !~ /^\//) {
                fail("invalid path-list for " key ": " value)
                return 0
            }
        }
        return 1
    }
    if (type == "url") {
        if (value == "" || value ~ /^https?:\/\/[^[:space:]@]+$/) return 1
        fail("invalid url for " key ": " value)
        return 0
    }
    if (type == "csv") {
        if (value == "" || value !~ /(^,|,$|,,|[\t\r\n])/) return 1
        fail("invalid csv for " key ": " value)
        return 0
    }
    if (type == "string" || type == "secret-ref") {
        if (value !~ /[\t\r\n]/) return 1
        fail("invalid " type " for " key)
        return 0
    }
    fail("unsupported schema type for " key ": " type)
    return 0
}

FILENAME == schema_file {
    if ($0 ~ /^[[:space:]]*#/ || $0 ~ /^[[:space:]]*$/) next
    if (NF != 6) {
        fail("invalid schema row " FNR ": expected 6 tab-separated fields")
        next
    }

    schema_key = $1
    schema_type = $2
    schema_default = expand_placeholders(schema_key, $3)
    schema_runtime = $4
    schema_override = $5
    schema_description = $6

    if (!valid_key(schema_key)) {
        fail("invalid schema key: " schema_key)
        next
    }
    if (schema_key in types) {
        fail("duplicate schema key: " schema_key)
        next
    }
    if (!valid_name(schema_runtime)) {
        fail("invalid runtime variable for " schema_key ": " schema_runtime)
        next
    }
    if (schema_override != "-" && !valid_name(schema_override)) {
        fail("invalid override variable for " schema_key ": " schema_override)
        next
    }
    if (schema_description == "") {
        fail("missing schema description for " schema_key)
        next
    }
    if (!value_is_valid(schema_key, schema_type, schema_default)) next

    key_count++
    keys[key_count] = schema_key
    types[schema_key] = schema_type
    values[schema_key] = schema_default
    runtime_vars[schema_key] = schema_runtime
    override_vars[schema_key] = schema_override
    descriptions[schema_key] = schema_description
    sources[schema_key] = "default"
    next
}

{
    if (failed) next
    if ($0 ~ /^[[:space:]]*#/ || $0 ~ /^[[:space:]]*$/) next

    equals_index = index($0, "=")
    if (equals_index < 2) {
        fail("invalid configuration row in " FILENAME ":" FNR)
        next
    }

    config_key = substr($0, 1, equals_index - 1)
    config_value = substr($0, equals_index + 1)
    if (config_key !~ /^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)+$/) {
        fail("invalid configuration key: " config_key)
        next
    }
    if (!(config_key in types)) {
        fail("unknown configuration key: " config_key)
        next
    }
    config_value = expand_placeholders(config_key, config_value)
    if (failed) next
    layer_key = FILENAME SUBSEP config_key
    if (layer_key in seen_layer_keys) {
        fail("duplicate configuration key: " config_key " in " FILENAME)
        next
    }
    seen_layer_keys[layer_key] = 1
    if (!value_is_valid(config_key, types[config_key], config_value)) next

    values[config_key] = config_value
    sources[config_key] = FILENAME
}

END {
    if (failed) exit 65
    if (key_count == 0) {
        print "dotfiles: schema contains no keys" > "/dev/stderr"
        exit 65
    }

    for (row_index = 1; row_index <= key_count; row_index++) {
        config_key = keys[row_index]
        override_name = override_vars[config_key]
        if (override_name != "-" && override_name in ENVIRON) {
            override_value = expand_placeholders(config_key, ENVIRON[override_name])
            if (failed) exit 65
            if (!value_is_valid(config_key, types[config_key], override_value)) exit 65
            values[config_key] = override_value
            sources[config_key] = "env:" override_name
        }
    }
    if (failed) exit 65

    if (output_mode == "validate") exit 0
    for (row_index = 1; row_index <= key_count; row_index++) {
        config_key = keys[row_index]
        if (output_mode == "runtime") {
            print runtime_vars[config_key], values[config_key]
        } else {
            display_value = values[config_key]
            if (output_mode == "list" && types[config_key] == "secret-ref") {
                display_value = values[config_key] == "" ? "<unset>" : "<configured>"
            }
            print config_key, display_value, sources[config_key], descriptions[config_key]
        }
    }
}
AWK
}

dotfiles_config_command() {
    local dotfiles_config_action="${1:-list}"
    if [ "$#" -gt 0 ]; then
        shift
    fi

    case "$dotfiles_config_action" in
        validate)
            if [ "$#" -ne 0 ]; then
                dotfiles_error "usage: dotfiles config validate"
                return 64
            fi
            dotfiles_config_resolve validate
            ;;
        list)
            if [ "${1:-}" = "--format" ] && [ "${2:-}" = "tsv" ] && [ "$#" -eq 2 ]; then
                dotfiles_config_resolve list
            elif [ "$#" -eq 0 ]; then
                printf 'key\tvalue\tsource\tdescription\n'
                dotfiles_config_resolve list
            else
                dotfiles_error "usage: dotfiles config list [--format tsv]"
                return 64
            fi
            ;;
        export)
            if [ "${1:-}" != "--format" ] || [ "${2:-}" != "tsv" ] || [ "$#" -ne 2 ]; then
                dotfiles_error "usage: dotfiles config export --format tsv"
                return 64
            fi
            dotfiles_config_resolve runtime
            ;;
        *)
            dotfiles_error "unknown config command: $dotfiles_config_action"
            return 64
            ;;
    esac
}

dotfiles_config_get_value() {
    local dotfiles_config_key="$1"
    local dotfiles_config_records
    dotfiles_config_records="$(dotfiles_config_resolve raw)" || return
    printf '%s\n' "$dotfiles_config_records" | awk -F '\t' -v config_key="$dotfiles_config_key" '
        $1 == config_key { print $2; found = 1; exit }
        END { if (!found) exit 1 }
    '
}

dotfiles_config_external_roots() {
    local dotfiles_external_roots_value
    local dotfiles_external_root
    local dotfiles_old_ifs
    dotfiles_external_roots_value="$(dotfiles_config_get_value plugins.external-roots)" || return
    [ -n "$dotfiles_external_roots_value" ] || return 0

    dotfiles_old_ifs="$IFS"
    IFS=':'
    for dotfiles_external_root in $dotfiles_external_roots_value; do
        IFS="$dotfiles_old_ifs"
        printf '%s\n' "$dotfiles_external_root"
        IFS=':'
    done
    IFS="$dotfiles_old_ifs"
}
