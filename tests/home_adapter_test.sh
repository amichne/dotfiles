#!/usr/bin/env bash

set -euo pipefail

TEST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
TEST_TMP="$(mktemp -d)"
trap 'rm -rf "$TEST_TMP"' EXIT

# shellcheck source=tests/testlib.sh
. "$TEST_ROOT/tests/testlib.sh"

export HOME="$TEST_TMP/home"
export XDG_CONFIG_HOME="$HOME/.config"
export PATH="/opt/homebrew/bin:/usr/bin:/bin"
mkdir -p "$HOME"

home_plan_output="$TEST_TMP/home-plan"
if "$TEST_ROOT/bin/dotfiles" home plan >"$home_plan_output"; then
    test_pass "home plan renders the static deployment diff"
else
    test_fail "home plan renders the static deployment diff" "plan exited non-zero"
fi
if [ ! -e "$HOME/.gitconfig" ] && [ ! -e "$HOME/.vimrc" ]; then
    test_pass "home plan does not write managed targets"
else
    test_fail "home plan does not write managed targets" "target files were created"
fi

assert_success \
    "home apply installs the safe public set" \
    "$TEST_ROOT/bin/dotfiles" home apply
if [ -f "$HOME/.gitconfig" ] \
    && [ -f "$HOME/.config/git/ignore" ] \
    && [ -f "$HOME/.config/atuin/config.toml" ] \
    && [ -f "$HOME/.vimrc" ] \
    && [ -f "$HOME/.ideavimrc" ]; then
    test_pass "home apply writes every declared public target"
else
    test_fail "home apply writes every declared public target" "one or more targets are missing"
fi

if [ -f "$HOME/.codex/config.toml" ] \
    && [ -f "$HOME/.codex/AGENTS.md" ] \
    && [ -f "$HOME/.codex/keybindings.json" ] \
    && [ -f "$HOME/.codex/browser/config.toml" ] \
    && [ -f "$HOME/.codex/computer-use/config.json" ] \
    && [ -f "$HOME/.codex/automations/daily-bug-scan/automation.toml" ] \
    && [ -f "$HOME/.codex/automations/skill-progression-map/automation.toml" ] \
    && [ -f "$HOME/.codex/automations/slopsentral-plugin-consolidation/automation.toml" ] \
    && [ -f "$HOME/.codex/automations/update-agents-md-2/automation.toml" ] \
    && [ -f "$HOME/.codex/automations/update-agents-md-6a4ea9ab6172/automation.toml" ] \
    && [ -f "$HOME/.codex/automations/update-agents-md/automation.toml" ]; then
    test_pass "home apply writes the credential-free Codex configuration set"
else
    test_fail "home apply writes the credential-free Codex configuration set" "one or more Codex config targets are missing"
fi

if [ ! -e "$HOME/.codex/auth.json" ] \
    && [ ! -e "$HOME/.codex/history.jsonl" ] \
    && [ ! -e "$HOME/.codex/browser/sessions" ] \
    && [ ! -e "$HOME/.codex/automations/.run-jitter-salt" ]; then
    test_pass "home apply excludes Codex credentials and runtime state"
else
    test_fail "home apply excludes Codex credentials and runtime state" "a credential or runtime-state target was installed"
fi

if grep -qF '[marketplaces.ponytail]' "$HOME/.codex/config.toml" \
    && grep -qF 'source = "https://github.com/DietrichGebert/ponytail.git"' "$HOME/.codex/config.toml" \
    && grep -qF '[plugins."ponytail@ponytail"]' "$HOME/.codex/config.toml" \
    && ! grep -Eq 'CONTEXT7_API_KEY[[:space:]]*=' "$HOME/.codex/config.toml"; then
    test_pass "managed Codex config preserves Ponytail without the local Context7 credential"
else
    test_fail "managed Codex config preserves Ponytail without the local Context7 credential" "plugin state or credential sanitization is incorrect"
fi

assert_success \
    "home apply is idempotent" \
    "$TEST_ROOT/bin/dotfiles" home apply
home_status="$TEST_TMP/home-status"
home_status_code=0
"$TEST_ROOT/bin/dotfiles" home status >"$home_status" || home_status_code=$?
if [ "$home_status_code" -eq 0 ] && [ ! -s "$home_status" ]; then
    test_pass "home status is clean after apply"
else
    test_fail "home status is clean after apply" "chezmoi reports drift"
fi

assert_failure_contains \
    "missing chezmoi fails with an install hint" \
    "optional dependency is unavailable: chezmoi" \
    env PATH="/usr/bin:/bin" "$TEST_ROOT/bin/dotfiles" home plan

test_summary
