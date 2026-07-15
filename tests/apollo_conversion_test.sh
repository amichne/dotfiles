#!/usr/bin/env bash

set -euo pipefail

TEST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
TEST_TMP="$(mktemp -d)"
trap 'rm -rf "$TEST_TMP"' EXIT

# shellcheck source=tests/testlib.sh
. "$TEST_ROOT/tests/testlib.sh"

apollo_source="$TEST_TMP/apollo"
converted_config="$TEST_TMP/converted.conf"
mkdir -p \
    "$apollo_source/config/apollo" \
    "$apollo_source/config/gh" \
    "$apollo_source/artemis/config" \
    "$TEST_TMP/home"

cat >"$apollo_source/config/apollo/profile.env" <<'EOF'
export APOLLO_PROFILE='copilot'
EOF

cat >"$apollo_source/artemis/config/profile.env.example" <<'EOF'
ART_ENABLE_TERMINAL_PATHS=1
ART_ENABLE_LOCALE=1
ART_ENABLE_GPG_TTY=1
ART_ENABLE_SDKMAN=0
ART_ENABLE_WARP_INTEGRATION=0
ARTEMIS_PREPEND_PATHS="/opt/homebrew/bin:/opt/homebrew/sbin"
ARTEMIS_APPEND_PATHS="$HOME/.docker/bin:$HOME/.bin:$HOME/.local/bin:$HOME/.jetbrains"
ARTEMIS_JAVA_HOME="$HOME/.sdkman/candidates/java/current"
ARTEMIS_CODEX_HOME="$HOME/.codex"
ARTEMIS_HISTFILE="$HOME/.zsh_history"
ARTEMIS_LANG="en_US.UTF-8"
EOF

cat >"$apollo_source/config/gh/hosts.yml" <<'EOF'
github.example.invalid:
  user: must-not-be-converted
EOF

assert_success \
    "Apollo configuration renders as typed dotfiles data" \
    sh -c '"$1/bin/dotfiles" migrate apollo render --source "$2" >"$3"' \
    sh "$TEST_ROOT" "$apollo_source" "$converted_config"

for expected_row in \
    'feature.sdkman=off' \
    'feature.warp=off' \
    'path.prepend=/opt/homebrew/bin:/opt/homebrew/sbin' \
    'path.append=${HOME}/.docker/bin:${HOME}/.bin:${HOME}/.local/bin:${HOME}/.jetbrains' \
    'shell.history-file=${HOME}/.zsh_history' \
    'shell.locale=en_US.UTF-8' \
    'tools.codex-home=${HOME}/.codex' \
    'tools.java-home=${HOME}/.sdkman/candidates/java/current'; do
    if grep -qFx "$expected_row" "$converted_config"; then
        test_pass "converted row: $expected_row"
    else
        test_fail "converted row: $expected_row" "row missing"
    fi
done

if grep -Eq 'APOLLO_PROFILE|must-not-be-converted|github\.example\.invalid' "$converted_config"; then
    test_fail "provider and credential material is excluded" "unsafe source data reached output"
else
    test_pass "provider and credential material is excluded"
fi

assert_success \
    "converted output passes the production schema" \
    env \
        HOME="$TEST_TMP/home" \
        XDG_CONFIG_HOME="$TEST_TMP/home/.config" \
        DOTFILES_PROFILES=portable \
        DOTFILES_CONFIG_FILE="$converted_config" \
        "$TEST_ROOT/bin/dotfiles" config validate

assert_output_contains \
    "conversion plan calls out provider ownership" \
    "APOLLO_PROFILE: external agent/provider concern" \
    "$TEST_ROOT/bin/dotfiles" migrate apollo plan --source "$apollo_source"

assert_output_contains \
    "conversion plan calls out retired GPG behavior" \
    "ART_ENABLE_GPG_TTY: retired from shell startup" \
    "$TEST_ROOT/bin/dotfiles" migrate apollo plan --source "$apollo_source"

malicious_source="$TEST_TMP/malicious-apollo"
mkdir -p "$malicious_source/artemis/config"
cat >"$malicious_source/artemis/config/profile.env.example" <<'EOF'
ARTEMIS_LANG="$(touch /tmp/dotfiles-apollo-conversion-must-not-run)"
EOF
rm -f /tmp/dotfiles-apollo-conversion-must-not-run

assert_failure_contains \
    "shell expressions are rejected rather than evaluated" \
    "unsupported shell expression" \
    "$TEST_ROOT/bin/dotfiles" migrate apollo render --source "$malicious_source"

if [ -e /tmp/dotfiles-apollo-conversion-must-not-run ]; then
    test_fail "rejected source is never executed" "malicious command ran"
else
    test_pass "rejected source is never executed"
fi

test_summary
