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

if [ -f "$HOME/.codex/AGENTS.md" ] \
    && grep -qF 'Commit and push each validated RED and passing GREEN checkpoint before continuing.' "$HOME/.codex/AGENTS.md" \
    && grep -qF 'When a task, ticket, subtask, or direct message defines a deliverable or links a file containing the deliverable, raise or update a pull request and follow its latest head until green.' "$HOME/.codex/AGENTS.md"; then
    test_pass "home apply installs the personal delivery policy"
else
    test_fail "home apply installs the personal delivery policy" "personal instructions are missing or stale"
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
