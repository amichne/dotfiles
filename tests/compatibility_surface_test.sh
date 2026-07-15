#!/usr/bin/env bash

set -euo pipefail

TEST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
TEST_TMP="$(mktemp -d)"
trap 'rm -rf "$TEST_TMP"' EXIT

# shellcheck source=tests/testlib.sh
. "$TEST_ROOT/tests/testlib.sh"

export HOME="$TEST_TMP/home"
export XDG_CONFIG_HOME="$HOME/.config"
export DOTFILES_CONFIG_FILE="$XDG_CONFIG_HOME/dotfiles/config.conf"
export DOTFILES_PROFILES=portable
unset DOTFILES_SCHEMA_FILE DOTFILES_PROFILE_FILES DOTFILES_PLUGIN_MANIFEST_FILE DOTFILES_DEPENDENCIES_FILE

mkdir -p "$(dirname "$DOTFILES_CONFIG_FILE")"
: >"$DOTFILES_CONFIG_FILE"

surface_output="$(
    PATH="/usr/bin:/bin" DOTFILES_ROOT="$TEST_ROOT" zsh -fc '
        source "$DOTFILES_ROOT/shell/zsh/entrypoint.zsh" || exit 1
        alias l 2>/dev/null || true
        for command_name in zs rr f main push commit; do
            whence -w "$command_name" 2>/dev/null || print -r -- "$command_name: missing"
        done
    '
)"

assert_surface() {
    local label="$1"
    local expected="$2"
    if printf '%s\n' "$surface_output" | grep -qFx "$expected"; then
        test_pass "$label"
    else
        test_fail "$label" "missing surface: $expected"
    fi
}

assert_surface "l keeps the established listing alias" "l='ls -lah'"
assert_surface "zs remains a shell command" "zs: function"
assert_surface "rr remains repository-root navigation" "rr: function"
assert_surface "f remains the short search helper" "f: function"
assert_surface "main remains a Git workflow command" "main: function"
assert_surface "push remains a Git workflow command" "push: function"
assert_surface "commit remains a Git workflow command" "commit: function"

test_summary
