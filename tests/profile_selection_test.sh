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
unset DOTFILES_PROFILES DOTFILES_PROFILE_FILES DOTFILES_SCHEMA_FILE
mkdir -p "$(dirname "$DOTFILES_CONFIG_FILE")"
: >"$DOTFILES_CONFIG_FILE"

assert_success \
    "profile set persists a checked-in profile selection" \
    "$TEST_ROOT/bin/dotfiles" profile set personal

assert_output_contains \
    "profile get reports the persisted selection" \
    "personal" \
    "$TEST_ROOT/bin/dotfiles" profile get

assert_output_contains \
    "persisted personal profile changes effective configuration" \
    $'git.commit-stage\tall' \
    "$TEST_ROOT/bin/dotfiles" config list --format tsv

assert_output_contains \
    "process profile selection overrides persisted selection" \
    $'git.commit-stage\tnone' \
    env DOTFILES_PROFILES=portable "$TEST_ROOT/bin/dotfiles" config list --format tsv

assert_failure_contains \
    "unknown profile cannot be persisted" \
    "profile does not exist: missing" \
    "$TEST_ROOT/bin/dotfiles" profile set missing

assert_failure_contains \
    "invalid profile syntax is rejected" \
    "invalid profile name" \
    "$TEST_ROOT/bin/dotfiles" profile set '../personal'

test_summary
