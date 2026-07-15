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
export DOTFILES_FEATURE_SDKMAN=on
unset DOTFILES_SCHEMA_FILE DOTFILES_PROFILE_FILES DOTFILES_PLUGIN_MANIFEST_FILE DOTFILES_DEPENDENCIES_FILE

mkdir -p "$HOME/.sdkman/bin" "$(dirname "$DOTFILES_CONFIG_FILE")"
: >"$DOTFILES_CONFIG_FILE"
cat >"$HOME/.sdkman/bin/sdkman-init.sh" <<'EOF'
export SDKMAN_STUB_LOAD_COUNT=$((${SDKMAN_STUB_LOAD_COUNT:-0} + 1))
sdk() {
    print -r -- "SDK:$*"
}
EOF

lazy_output="$(PATH="/usr/bin:/bin" DOTFILES_ROOT="$TEST_ROOT" zsh -fc '
    source "$DOTFILES_ROOT/shell/zsh/entrypoint.zsh" || exit 1
    print -r -- "BEFORE=${SDKMAN_STUB_LOAD_COUNT:-0}"
    sdk version || exit 1
    print -r -- "AFTER=${SDKMAN_STUB_LOAD_COUNT:-0}"
')"

if printf '%s\n' "$lazy_output" | grep -qFx "BEFORE=0"; then
    test_pass "SDKMAN is not sourced during shell startup"
else
    test_fail "SDKMAN is not sourced during shell startup" "SDKMAN loaded eagerly"
fi
if printf '%s\n' "$lazy_output" | grep -qFx "SDK:version" \
    && printf '%s\n' "$lazy_output" | grep -qFx "AFTER=1"; then
    test_pass "first SDKMAN command initializes exactly once"
else
    test_fail "first SDKMAN command initializes exactly once" "lazy dispatch failed"
fi

test_summary
