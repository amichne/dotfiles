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

enterprise_root="$TEST_TMP/enterprise"
mkdir -p "$(dirname "$DOTFILES_CONFIG_FILE")" "$enterprise_root"

cat >"$enterprise_root/dependencies.tsv" <<'EOF'
enterprise-shell	command	sh	any	Install a POSIX shell through the enterprise package provider.
EOF
cat >"$enterprise_root/plugins.tsv" <<'EOF'
enterprise-fixture	plugin.zsh	-	zsh	enterprise-shell	External enterprise fixture.
EOF
cat >"$enterprise_root/plugin.zsh" <<'EOF'
typeset -g DOTFILES_ENTERPRISE_FIXTURE_LOADED=1
EOF
printf 'plugins.external-roots=%s\n' "$enterprise_root" >"$DOTFILES_CONFIG_FILE"

assert_success \
    "external trusted root composes with built-in manifests" \
    "$TEST_ROOT/bin/dotfiles" plugins validate

assert_output_contains \
    "external plugin path resolves inside its physical trusted root" \
    "$enterprise_root/plugin.zsh" \
    "$TEST_ROOT/bin/dotfiles" plugins paths

runtime_status=0
runtime_output="$(PATH="/usr/bin:/bin" DOTFILES_ROOT="$TEST_ROOT" zsh -fc '
    source "$DOTFILES_ROOT/shell/zsh/entrypoint.zsh" || exit 1
    print -r -- "ENTERPRISE=${DOTFILES_ENTERPRISE_FIXTURE_LOADED:-0}"
')" || runtime_status=$?
if [ "$runtime_status" -eq 0 ] && [ "$runtime_output" = "ENTERPRISE=1" ]; then
    test_pass "external enterprise plugin loads through the normal Zsh boundary"
else
    test_fail "external enterprise plugin loads through the normal Zsh boundary" "plugin marker missing"
fi

cat >"$enterprise_root/plugins.tsv" <<'EOF'
shell-core	plugin.zsh	-	zsh	enterprise-shell	Duplicate built-in id fixture.
EOF
assert_failure_contains \
    "duplicate plugin ids across roots are rejected" \
    "duplicate plugin id: shell-core" \
    "$TEST_ROOT/bin/dotfiles" plugins validate

test_summary
