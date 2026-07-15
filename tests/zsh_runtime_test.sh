#!/usr/bin/env bash

set -euo pipefail

TEST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
TEST_TMP="$(mktemp -d)"
trap 'rm -rf "$TEST_TMP"' EXIT

# shellcheck source=tests/testlib.sh
. "$TEST_ROOT/tests/testlib.sh"

export HOME="$TEST_TMP/home"
export XDG_CONFIG_HOME="$HOME/.config"
export DOTFILES_SCHEMA_FILE="$TEST_TMP/schema.tsv"
export DOTFILES_CONFIG_FILE="$TEST_TMP/config.conf"
export DOTFILES_PLUGIN_MANIFEST_FILE="$TEST_TMP/plugins.tsv"
export DOTFILES_DEPENDENCIES_FILE="$TEST_TMP/dependencies.tsv"
export DOTFILES_PATH_PREPEND="$TEST_TMP/pre-one:$TEST_TMP/pre-two"
export DOTFILES_PATH_APPEND="$TEST_TMP/append-one:$TEST_TMP/pre-one"
unset DOTFILES_PROFILES DOTFILES_PROFILE_FILES

mkdir -p \
    "$HOME" \
    "$XDG_CONFIG_HOME" \
    "$TEST_TMP/pre-one" \
    "$TEST_TMP/pre-two" \
    "$TEST_TMP/append-one"

cat >"$DOTFILES_SCHEMA_FILE" <<'EOF'
# key	type	default	runtime_var	override_var	description
path.append	path-list		DOTFILES_CFG_PATH_APPEND	DOTFILES_PATH_APPEND	Paths appended to PATH.
path.prepend	path-list		DOTFILES_CFG_PATH_PREPEND	DOTFILES_PATH_PREPEND	Paths prepended to PATH.
shell.editor	command	vim	DOTFILES_CFG_SHELL_EDITOR	DOTFILES_EDITOR	Interactive editor.
shell.history-file	path	${HOME}/.zsh_history	DOTFILES_CFG_SHELL_HISTORY_FILE	DOTFILES_HISTORY_FILE	Zsh history file.
shell.history-size	uint	50000	DOTFILES_CFG_SHELL_HISTORY_SIZE	DOTFILES_HISTORY_SIZE	In-memory history size.
shell.save-history	uint	10000	DOTFILES_CFG_SHELL_SAVE_HISTORY	DOTFILES_SAVE_HISTORY	Saved history size.
EOF

: >"$DOTFILES_CONFIG_FILE"
: >"$DOTFILES_DEPENDENCIES_FILE"
cat >"$DOTFILES_PLUGIN_MANIFEST_FILE" <<'EOF'
runtime-fixture	tests/fixtures/runtime.plugin.zsh	-	zsh	-	Runtime fixture.
EOF

runtime_status=0
runtime_output="$({ \
    PATH="/usr/bin:/bin:$TEST_TMP/pre-one" \
    DOTFILES_ROOT="$TEST_ROOT" \
    zsh -fc '
        source "$DOTFILES_ROOT/shell/zsh/entrypoint.zsh" || exit 1
        source "$DOTFILES_ROOT/shell/zsh/entrypoint.zsh" || exit 1
        print -r -- "EDITOR=$EDITOR"
        print -r -- "PATH=$PATH"
        print -r -- "LOADS=$DOTFILES_RUNTIME_FIXTURE_LOAD_COUNT"
        print -r -- "HISTFILE=$HISTFILE"
    '
} 2>"$TEST_TMP/runtime.stderr")" || runtime_status=$?

if [ "$runtime_status" -eq 0 ]; then
    test_pass "valid startup exits successfully"
else
    test_fail "valid startup exits successfully" "entrypoint exited $runtime_status"
fi

if [ ! -s "$TEST_TMP/runtime.stderr" ]; then
    test_pass "valid startup is silent on stderr"
else
    test_fail "valid startup is silent on stderr" "unexpected startup diagnostics"
fi

if printf '%s\n' "$runtime_output" | grep -qF "EDITOR=vim"; then
    test_pass "validated config reaches the shell"
else
    test_fail "validated config reaches the shell" "EDITOR was not applied"
fi

expected_path="PATH=$TEST_TMP/pre-one:$TEST_TMP/pre-two:/usr/bin:/bin:$TEST_TMP/append-one"
if printf '%s\n' "$runtime_output" | grep -qFx "$expected_path"; then
    test_pass "PATH order is stable and duplicate-free"
else
    test_fail "PATH order is stable and duplicate-free" "unexpected PATH"
fi

if printf '%s\n' "$runtime_output" | grep -qFx "LOADS=1"; then
    test_pass "entrypoint and plugin loading are idempotent"
else
    test_fail "entrypoint and plugin loading are idempotent" "plugin loaded more than once"
fi

cat >"$DOTFILES_CONFIG_FILE" <<'EOF'
shell.history-size=not-a-number
EOF

assert_failure_contains \
    "invalid configuration stops startup before plugin code" \
    "invalid uint for shell.history-size: not-a-number" \
    env PATH="/usr/bin:/bin" DOTFILES_ROOT="$TEST_ROOT" \
    zsh -fc 'source "$DOTFILES_ROOT/shell/zsh/entrypoint.zsh"'

test_summary
