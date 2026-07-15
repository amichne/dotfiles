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
export DOTFILES_PROFILE_FILES="$TEST_TMP/profile.conf"
export DOTFILES_CONFIG_FILE="$TEST_TMP/local.conf"

mkdir -p "$HOME" "$XDG_CONFIG_HOME"

cat >"$DOTFILES_SCHEMA_FILE" <<'EOF'
# key	type	default	runtime_var	override_var	description
feature.atuin	toggle	auto	DOTFILES_CFG_FEATURE_ATUIN	DOTFILES_FEATURE_ATUIN	Atuin integration state.
git.commit-stage	enum:none,tracked,all	none	DOTFILES_CFG_GIT_COMMIT_STAGE	DOTFILES_GIT_COMMIT_STAGE	Files staged by commit helper.
shell.editor	command	vim	DOTFILES_CFG_SHELL_EDITOR	DOTFILES_EDITOR	Interactive editor command.
shell.history-size	uint	50000	DOTFILES_CFG_SHELL_HISTORY_SIZE	DOTFILES_HISTORY_SIZE	Zsh history size.
EOF

cat >"$DOTFILES_PROFILE_FILES" <<'EOF'
feature.atuin=on
shell.editor=nvim
EOF

cat >"$DOTFILES_CONFIG_FILE" <<'EOF'
shell.history-size=75000
EOF

assert_success \
    "valid typed configuration is accepted" \
    "$TEST_ROOT/bin/dotfiles" config validate

cat >"$DOTFILES_CONFIG_FILE" <<'EOF'
unknown.setting=value
EOF
assert_failure_contains \
    "unknown configuration key is rejected" \
    "unknown configuration key: unknown.setting" \
    "$TEST_ROOT/bin/dotfiles" config validate

cat >"$DOTFILES_CONFIG_FILE" <<'EOF'
shell.editor=vim
shell.editor=nvim
EOF
assert_failure_contains \
    "duplicate key in one layer is rejected" \
    "duplicate configuration key: shell.editor" \
    "$TEST_ROOT/bin/dotfiles" config validate

cat >"$DOTFILES_CONFIG_FILE" <<'EOF'
feature.atuin=maybe
EOF
assert_failure_contains \
    "invalid toggle is rejected" \
    "invalid toggle for feature.atuin: maybe" \
    "$TEST_ROOT/bin/dotfiles" config validate

cat >"$DOTFILES_CONFIG_FILE" <<'EOF'
shell.history-size=-1
EOF
assert_failure_contains \
    "invalid unsigned integer is rejected" \
    "invalid uint for shell.history-size: -1" \
    "$TEST_ROOT/bin/dotfiles" config validate

test_summary
