#!/usr/bin/env bash

dotfiles_dependencies_file() {
    printf '%s' "${DOTFILES_DEPENDENCIES_FILE:-$DOTFILES_ROOT/config/dependencies.tsv}"
}

dotfiles_dependencies_normalize_file() {
    local dotfiles_dependencies_source="$1"
    dotfiles_require_file "$dotfiles_dependencies_source" || return

    awk -F '\t' -v OFS='\t' '
        function fail(message) {
            print "dotfiles: " message > "/dev/stderr"
            failed = 1
        }
        /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
        {
            if (NF != 5) {
                fail("invalid dependency row " FNR ": expected 5 tab-separated fields")
                next
            }
            if ($1 !~ /^[a-z][a-z0-9-]*$/) {
                fail("invalid dependency id: " $1)
                next
            }
            if (seen[$1]++) {
                fail("duplicate dependency id: " $1)
                next
            }
            if ($2 != "command" && $2 != "file" && $2 != "directory") {
                fail("invalid dependency kind for " $1 ": " $2)
                next
            }
            if ($3 == "" || $3 ~ /[\r\n]/) {
                fail("invalid dependency probe for " $1)
                next
            }
            if ($4 !~ /^(any|darwin|linux)(,(darwin|linux))*$/) {
                fail("invalid dependency platforms for " $1 ": " $4)
                next
            }
            if ($5 == "") {
                fail("missing dependency install hint for " $1)
                next
            }
            print
        }
        END { if (failed) exit 65 }
    ' "$dotfiles_dependencies_source"
}

dotfiles_dependencies_normalize() {
    local dotfiles_dependencies_temp
    local dotfiles_dependencies_source
    local dotfiles_external_root
    local dotfiles_external_dependencies
    dotfiles_dependencies_temp="$(mktemp "${TMPDIR:-/tmp}/dotfiles.dependencies.XXXXXX")" || return
    : >"$dotfiles_dependencies_temp"

    if [ -n "${DOTFILES_DEPENDENCIES_FILE+x}" ]; then
        dotfiles_dependencies_source="$(dotfiles_dependencies_file)"
        dotfiles_dependencies_normalize_file "$dotfiles_dependencies_source" >"$dotfiles_dependencies_temp" || {
            rm -f "$dotfiles_dependencies_temp"
            return 65
        }
    else
        dotfiles_dependencies_normalize_file "$DOTFILES_ROOT/config/dependencies.tsv" >"$dotfiles_dependencies_temp" || {
            rm -f "$dotfiles_dependencies_temp"
            return 65
        }
        while IFS= read -r dotfiles_external_root; do
            [ -n "$dotfiles_external_root" ] || continue
            dotfiles_external_dependencies="$dotfiles_external_root/dependencies.tsv"
            [ -e "$dotfiles_external_dependencies" ] || continue
            if [ -L "$dotfiles_external_dependencies" ]; then
                dotfiles_error "external dependency manifest must not be a symlink: $dotfiles_external_dependencies"
                rm -f "$dotfiles_dependencies_temp"
                return 65
            fi
            dotfiles_dependencies_normalize_file "$dotfiles_external_dependencies" >>"$dotfiles_dependencies_temp" || {
                rm -f "$dotfiles_dependencies_temp"
                return 65
            }
        done < <(dotfiles_config_external_roots)
    fi

    awk -F '\t' '
        seen[$1]++ {
            print "dotfiles: duplicate dependency id: " $1 > "/dev/stderr"
            failed = 1
            next
        }
        { print }
        END { if (failed) exit 65 }
    ' "$dotfiles_dependencies_temp"
    local dotfiles_dependencies_status=$?
    rm -f "$dotfiles_dependencies_temp"
    return "$dotfiles_dependencies_status"
}

dotfiles_dependency_row() {
    local dotfiles_dependency_id="$1"
    dotfiles_dependencies_normalize | awk -F '\t' -v dependency_id="$dotfiles_dependency_id" '
        $1 == dependency_id { print; found = 1; exit }
        END { if (!found) exit 1 }
    '
}

dotfiles_dependency_exists() {
    local dotfiles_dependency_id="$1"
    dotfiles_dependency_row "$dotfiles_dependency_id" >/dev/null 2>&1
}

dotfiles_dependency_platform_matches() {
    local dotfiles_platforms="$1"
    local dotfiles_kernel
    dotfiles_kernel="$(uname -s 2>/dev/null || printf unknown)"

    case "$dotfiles_platforms:$dotfiles_kernel" in
        any:*|*darwin*:Darwin|*linux*:Linux) return 0 ;;
        *) return 1 ;;
    esac
}

dotfiles_dependency_expand_probe() {
    local dotfiles_probe="$1"
    dotfiles_probe="${dotfiles_probe//'${HOME}'/$HOME}"
    dotfiles_probe="${dotfiles_probe//'${XDG_CONFIG_HOME}'/${XDG_CONFIG_HOME:-$HOME/.config}}"
    dotfiles_probe="${dotfiles_probe//'${DOTFILES_ROOT}'/$DOTFILES_ROOT}"
    if [[ "$dotfiles_probe" == *'${'* ]]; then
        dotfiles_error "unsupported dependency probe placeholder: $dotfiles_probe"
        return 65
    fi
    printf '%s' "$dotfiles_probe"
}

dotfiles_dependency_available() {
    local dotfiles_dependency_id="$1"
    local dotfiles_dependency_row_value
    dotfiles_dependency_row_value="$(dotfiles_dependency_row "$dotfiles_dependency_id")" || return 1

    local dotfiles_dependency_kind
    local dotfiles_dependency_probe
    local dotfiles_dependency_platforms
    IFS=$'\t' read -r _dotfiles_dependency_id dotfiles_dependency_kind dotfiles_dependency_probe dotfiles_dependency_platforms _dotfiles_dependency_hint <<<"$dotfiles_dependency_row_value"

    dotfiles_dependency_platform_matches "$dotfiles_dependency_platforms" || return 1
    dotfiles_dependency_probe="$(dotfiles_dependency_expand_probe "$dotfiles_dependency_probe")" || return

    case "$dotfiles_dependency_kind" in
        command) command -v "$dotfiles_dependency_probe" >/dev/null 2>&1 ;;
        file) [ -f "$dotfiles_dependency_probe" ] ;;
        directory) [ -d "$dotfiles_dependency_probe" ] ;;
    esac
}

dotfiles_dependency_hint() {
    local dotfiles_dependency_id="$1"
    local dotfiles_dependency_row_value
    dotfiles_dependency_row_value="$(dotfiles_dependency_row "$dotfiles_dependency_id")" || return 1
    printf '%s' "${dotfiles_dependency_row_value##*$'\t'}"
}
