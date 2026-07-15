#!/usr/bin/env bash

set -euo pipefail

TEST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
TEST_TMP="$(mktemp -d)"
trap 'rm -rf "$TEST_TMP"' EXIT

# shellcheck source=tests/testlib.sh
. "$TEST_ROOT/tests/testlib.sh"

export HOME="$TEST_TMP/home"
export XDG_CONFIG_HOME="$HOME/config"
export DOTFILES_SCHEMA_FILE="$TEST_TMP/schema.tsv"
export DOTFILES_PROFILE_FILES="$TEST_TMP/first.conf:$TEST_TMP/second.conf"
export DOTFILES_CONFIG_FILE="$TEST_TMP/local.conf"
export DOTFILES_EDITOR="helix"

mkdir -p "$HOME" "$XDG_CONFIG_HOME"

cat >"$DOTFILES_SCHEMA_FILE" <<'EOF'
# key	type	default	runtime_var	override_var	description
feature.atuin	toggle	auto	DOTFILES_CFG_FEATURE_ATUIN	DOTFILES_FEATURE_ATUIN	Atuin integration state.
path.append	path-list	${HOME}/.local/bin:${XDG_CONFIG_HOME}/tools	DOTFILES_CFG_PATH_APPEND	DOTFILES_PATH_APPEND	Optional path entries.
shell.editor	command	vim	DOTFILES_CFG_SHELL_EDITOR	DOTFILES_EDITOR	Interactive editor command.
EOF

cat >"$TEST_TMP/first.conf" <<'EOF'
feature.atuin=off
shell.editor=nvim
EOF

cat >"$TEST_TMP/second.conf" <<'EOF'
feature.atuin=on
shell.editor=emacs
EOF

cat >"$DOTFILES_CONFIG_FILE" <<'EOF'
shell.editor=nano
EOF

assert_output_contains \
    "later profile overrides earlier profile" \
    $'feature.atuin\ton' \
    "$TEST_ROOT/bin/dotfiles" config list --format tsv

assert_output_contains \
    "declared process override wins over local config" \
    $'shell.editor\thelix\tenv:DOTFILES_EDITOR' \
    "$TEST_ROOT/bin/dotfiles" config list --format tsv

assert_output_contains \
    "runtime export contains only runtime variable and expanded data" \
    $'DOTFILES_CFG_PATH_APPEND\t'"$HOME/.local/bin:$XDG_CONFIG_HOME/tools" \
    "$TEST_ROOT/bin/dotfiles" config export --format tsv

cat >"$DOTFILES_CONFIG_FILE" <<'EOF'
path.append=${UNDECLARED}/bin
EOF
assert_failure_contains \
    "undeclared placeholder is rejected" \
    'unsupported placeholder for path.append: ${UNDECLARED}' \
    "$TEST_ROOT/bin/dotfiles" config validate

test_summary
