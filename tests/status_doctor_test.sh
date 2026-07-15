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
export DOTFILES_GITHUB_CREDENTIAL_REFERENCE='private-provider-reference'
unset DOTFILES_SCHEMA_FILE DOTFILES_PROFILE_FILES DOTFILES_PLUGIN_MANIFEST_FILE DOTFILES_DEPENDENCIES_FILE

mkdir -p "$(dirname "$DOTFILES_CONFIG_FILE")"
: >"$DOTFILES_CONFIG_FILE"

doctor_output_file="$TEST_TMP/doctor-output"
if PATH="/usr/bin:/bin" "$TEST_ROOT/bin/dotfiles" doctor >"$doctor_output_file"; then
    test_pass "doctor accepts unavailable automatic integrations"
else
    test_fail "doctor accepts unavailable automatic integrations" "doctor exited non-zero"
fi
if grep -qF "config: ok" "$doctor_output_file" \
    && grep -qF "plugins: ok" "$doctor_output_file" \
    && grep -qF "zoxide: unavailable (auto)" "$doctor_output_file"; then
    test_pass "doctor explains automatic dependency skips"
else
    test_fail "doctor explains automatic dependency skips" "missing dependency explanation"
fi

export DOTFILES_FEATURE_ZOXIDE=on
assert_failure_contains \
    "doctor rejects an explicitly enabled missing dependency" \
    "zoxide: missing required dependency zoxide" \
    env PATH="/usr/bin:/bin" "$TEST_ROOT/bin/dotfiles" doctor
unset DOTFILES_FEATURE_ZOXIDE

assert_failure_contains \
    "strict doctor rejects unavailable automatic integrations" \
    "strict doctor found unavailable automatic integrations" \
    env PATH="/usr/bin:/bin" "$TEST_ROOT/bin/dotfiles" doctor --strict

status_output_file="$TEST_TMP/status-output"
if "$TEST_ROOT/bin/dotfiles" status >"$status_output_file"; then
    test_pass "status exits successfully"
else
    test_fail "status exits successfully" "status exited non-zero"
fi
if grep -qF "root: $TEST_ROOT" "$status_output_file" \
    && grep -qF "profiles: portable" "$status_output_file" \
    && grep -qF "local config: $DOTFILES_CONFIG_FILE" "$status_output_file"; then
    test_pass "status identifies configuration ownership"
else
    test_fail "status identifies configuration ownership" "ownership fields missing"
fi

config_output_file="$TEST_TMP/config-output"
"$TEST_ROOT/bin/dotfiles" config list --format tsv >"$config_output_file"
if ! grep -qF "$DOTFILES_GITHUB_CREDENTIAL_REFERENCE" "$config_output_file" \
    && ! grep -qF "$DOTFILES_GITHUB_CREDENTIAL_REFERENCE" "$status_output_file"; then
    test_pass "credential references are redacted from diagnostics"
else
    test_fail "credential references are redacted from diagnostics" "credential reference was printed"
fi

plugin_output_file="$TEST_TMP/plugin-output"
PATH="/usr/bin:/bin" "$TEST_ROOT/bin/dotfiles" plugins list >"$plugin_output_file"
if grep -qF $'zoxide\tunavailable-auto\tfeature.zoxide\tzoxide' "$plugin_output_file"; then
    test_pass "plugin list exposes effective feature and dependency state"
else
    test_fail "plugin list exposes effective feature and dependency state" "zoxide state missing"
fi

test_summary
