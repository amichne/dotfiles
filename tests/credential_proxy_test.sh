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

export DOTFILES_GITHUB_CREDENTIAL_PROVIDER=env
export DOTFILES_GITHUB_CREDENTIAL_REFERENCE=TEST_GITHUB_SECRET
export TEST_GITHUB_SECRET='github-test-value'
unset GITHUB_TOKEN GH_TOKEN

assert_success \
    "GitHub credential is visible only to the child command" \
    "$TEST_ROOT/bin/dotfiles" credential exec github -- \
    sh -c '[ "$GITHUB_TOKEN" = "$TEST_GITHUB_SECRET" ] && [ "$GH_TOKEN" = "$TEST_GITHUB_SECRET" ]'

if [ -z "${GITHUB_TOKEN:-}" ] && [ -z "${GH_TOKEN:-}" ]; then
    test_pass "credential command does not mutate the parent environment"
else
    test_fail "credential command does not mutate the parent environment" "token leaked to parent"
fi

export DOTFILES_GITHUB_CREDENTIAL_REFERENCE=MISSING_GITHUB_SECRET
assert_failure_contains \
    "missing credential reference fails without prompting" \
    "credential environment variable is unset: MISSING_GITHUB_SECRET" \
    "$TEST_ROOT/bin/dotfiles" credential exec github -- sh -c true

export DOTFILES_PROXY_MODE=explicit
export DOTFILES_PROXY_SCOPE=command
export DOTFILES_PROXY_URL='https://proxy.example.test:8443'
export DOTFILES_PROXY_NO_PROXY='localhost,127.0.0.1,.internal.example.test'
export DOTFILES_PROXY_CREDENTIAL_PROVIDER=none
ca_bundle="$TEST_TMP/enterprise-ca.pem"
printf '%s\n' 'test-ca-bundle' >"$ca_bundle"
export DOTFILES_CA_BUNDLE="$ca_bundle"
export HTTP_PROXY=parent-http
export HTTPS_PROXY=parent-https

assert_success \
    "explicit proxy is scoped to the child command" \
    "$TEST_ROOT/bin/dotfiles" proxy exec -- sh -c \
    '[ "$HTTP_PROXY" = "https://proxy.example.test:8443" ] && [ "$HTTPS_PROXY" = "$HTTP_PROXY" ] && [ "$NO_PROXY" = "localhost,127.0.0.1,.internal.example.test" ] && [ "$SSL_CERT_FILE" = "$DOTFILES_CA_BUNDLE" ] && [ "$GIT_SSL_CAINFO" = "$DOTFILES_CA_BUNDLE" ]'

if [ "$HTTP_PROXY" = "parent-http" ] && [ "$HTTPS_PROXY" = "parent-https" ]; then
    test_pass "proxy command does not mutate the parent environment"
else
    test_fail "proxy command does not mutate the parent environment" "proxy leaked to parent"
fi

export DOTFILES_PROXY_CREDENTIAL_PROVIDER=env
export DOTFILES_PROXY_CREDENTIAL_REFERENCE=TEST_PROXY_SECRET
export DOTFILES_PROXY_USERNAME='enterprise user'
export TEST_PROXY_SECRET='p@ss word/with:symbols'
export EXPECTED_PROXY='https://enterprise%20user:p%40ss%20word%2Fwith%3Asymbols@proxy.example.test:8443'

assert_success \
    "authenticated proxy credentials are encoded and child scoped" \
    "$TEST_ROOT/bin/dotfiles" proxy exec -- sh -c \
    '[ "$HTTPS_PROXY" = "$EXPECTED_PROXY" ] && [ "$HTTP_PROXY" = "$EXPECTED_PROXY" ]'

export DOTFILES_PROXY_CREDENTIAL_REFERENCE=MISSING_PROXY_SECRET
credential_error="$TEST_TMP/credential-error"
if "$TEST_ROOT/bin/dotfiles" proxy exec -- sh -c true >"$credential_error" 2>&1; then
    test_fail "proxy credential failure is non-zero" "command unexpectedly succeeded"
else
    test_pass "proxy credential failure is non-zero"
fi
if ! grep -qF "$TEST_PROXY_SECRET" "$credential_error"; then
    test_pass "proxy diagnostics never reveal secret values"
else
    test_fail "proxy diagnostics never reveal secret values" "secret appeared in output"
fi

test_summary
