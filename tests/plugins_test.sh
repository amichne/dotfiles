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
unset DOTFILES_PROFILES DOTFILES_PROFILE_FILES DOTFILES_FEATURE_DEMO

mkdir -p "$HOME" "$XDG_CONFIG_HOME"

cat >"$DOTFILES_SCHEMA_FILE" <<'EOF'
# key	type	default	runtime_var	override_var	description
feature.demo	toggle	auto	DOTFILES_CFG_FEATURE_DEMO	DOTFILES_FEATURE_DEMO	Demo plugin state.
EOF

: >"$DOTFILES_CONFIG_FILE"

cat >"$DOTFILES_DEPENDENCIES_FILE" <<'EOF'
# id	kind	probe	platforms	install_hint
present	command	sh	any	Install a POSIX shell.
missing	command	dotfiles-command-that-does-not-exist	any	Install the missing test command.
EOF

cat >"$DOTFILES_PLUGIN_MANIFEST_FILE" <<'EOF'
# id	path	feature	shell	dependencies	description
demo	tests/fixtures/demo.plugin.zsh	-	zsh	present	Demo fixture.
EOF
assert_success \
    "valid trusted plugin manifest is accepted" \
    "$TEST_ROOT/bin/dotfiles" plugins validate

cat >"$DOTFILES_PLUGIN_MANIFEST_FILE" <<'EOF'
demo	../outside.plugin.zsh	-	zsh	-	Traversal fixture.
EOF
assert_failure_contains \
    "plugin traversal is rejected" \
    "plugin path must remain relative to the trusted root" \
    "$TEST_ROOT/bin/dotfiles" plugins validate

cat >"$DOTFILES_PLUGIN_MANIFEST_FILE" <<'EOF'
demo	tests/fixtures/demo.plugin.zsh	feature.unknown	zsh	-	Unknown feature fixture.
EOF
assert_failure_contains \
    "unknown plugin feature is rejected" \
    "plugin demo references unknown feature: feature.unknown" \
    "$TEST_ROOT/bin/dotfiles" plugins validate

cat >"$DOTFILES_PLUGIN_MANIFEST_FILE" <<'EOF'
demo	tests/fixtures/demo.plugin.zsh	-	zsh	-	First fixture.
demo	tests/fixtures/demo.plugin.zsh	-	zsh	-	Duplicate fixture.
EOF
assert_failure_contains \
    "duplicate plugin id is rejected" \
    "duplicate plugin id: demo" \
    "$TEST_ROOT/bin/dotfiles" plugins validate

cat >"$DOTFILES_PLUGIN_MANIFEST_FILE" <<'EOF'
demo	tests/fixtures/demo.plugin.zsh	feature.demo	zsh	missing	Missing dependency fixture.
EOF
export DOTFILES_FEATURE_DEMO=on
assert_failure_contains \
    "enabled plugin requires its dependency" \
    "enabled plugin demo is missing dependency: missing" \
    "$TEST_ROOT/bin/dotfiles" plugins paths

export DOTFILES_FEATURE_DEMO=auto
assert_output_empty \
    "automatic plugin skips an unavailable dependency" \
    "$TEST_ROOT/bin/dotfiles" plugins paths

export DOTFILES_FEATURE_DEMO=off
assert_success \
    "disabled plugin does not require its dependency" \
    "$TEST_ROOT/bin/dotfiles" plugins paths

test_summary
