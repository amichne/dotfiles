#!/usr/bin/env bash

set -euo pipefail

TEST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
TEST_TMP="$(mktemp -d)"
trap 'rm -rf "$TEST_TMP"' EXIT

# shellcheck source=tests/testlib.sh
. "$TEST_ROOT/tests/testlib.sh"

export HOME="$TEST_TMP/home"
export XDG_CONFIG_HOME="$HOME/.config"
unset ZDOTDIR DOTFILES_CONFIG_FILE
mkdir -p "$HOME"

cat >"$HOME/.zshrc" <<'EOF'
export USER_OWNED_LINE=preserve-me
# >>> apollo shell entrypoint >>>
export APOLLO="$HOME/code/apollo"
source "$APOLLO/zsh-entrypoint.sh"
# <<< apollo shell entrypoint <<<
export APOLLO="$HOME/code/apollo"
source $APOLLO/zsh-entrypoint.sh
# >>> artemis shell entrypoint >>>
export ARTEMIS_ROOT="$HOME/code/apollo/artemis"
source "$ARTEMIS_ROOT/zsh-entrypoint.sh"
# <<< artemis shell entrypoint <<<
EOF

before_plan="$(cksum "$HOME/.zshrc")"
assert_output_contains \
    "install plan reports legacy ownership" \
    "legacy blocks: apollo,apollo-unmanaged,artemis" \
    "$TEST_ROOT/bin/dotfiles" install plan
after_plan="$(cksum "$HOME/.zshrc")"
if [ "$before_plan" = "$after_plan" ]; then
    test_pass "install plan is read-only"
else
    test_fail "install plan is read-only" "zshrc changed during plan"
fi

assert_failure_contains \
    "apply refuses dual legacy ownership" \
    "legacy shell blocks detected; rerun with --migrate" \
    "$TEST_ROOT/bin/dotfiles" install apply

assert_success \
    "explicit migration installs the new owner" \
    "$TEST_ROOT/bin/dotfiles" install apply --migrate

if grep -qF "export USER_OWNED_LINE=preserve-me" "$HOME/.zshrc" \
    && ! grep -qF "apollo shell entrypoint" "$HOME/.zshrc" \
    && ! grep -qF 'source $APOLLO/zsh-entrypoint.sh' "$HOME/.zshrc" \
    && ! grep -qF "artemis shell entrypoint" "$HOME/.zshrc" \
    && [ "$(grep -cF '# >>> dotfiles shell entrypoint >>>' "$HOME/.zshrc")" -eq 1 ]; then
    test_pass "migration preserves user content and leaves one owner"
else
    test_fail "migration preserves user content and leaves one owner" "managed blocks are incorrect"
fi

local_config="$XDG_CONFIG_HOME/dotfiles/config.conf"
if [ -f "$local_config" ]; then
    test_pass "apply creates a machine-local config file"
else
    test_fail "apply creates a machine-local config file" "missing local config"
fi

mkdir -p "$(dirname "$local_config")"
printf '%s\n' 'shell.editor=nvim' >"$local_config"
assert_success \
    "repeated apply is idempotent" \
    "$TEST_ROOT/bin/dotfiles" install apply
if grep -qFx "shell.editor=nvim" "$local_config" \
    && [ "$(grep -cF '# >>> dotfiles shell entrypoint >>>' "$HOME/.zshrc")" -eq 1 ]; then
    test_pass "repeated apply preserves machine-local data"
else
    test_fail "repeated apply preserves machine-local data" "local state was overwritten"
fi

assert_success \
    "uninstall removes the managed shell block" \
    "$TEST_ROOT/bin/dotfiles" install uninstall
if grep -qF "export USER_OWNED_LINE=preserve-me" "$HOME/.zshrc" \
    && ! grep -qF "dotfiles shell entrypoint" "$HOME/.zshrc"; then
    test_pass "uninstall preserves surrounding user content"
else
    test_fail "uninstall preserves surrounding user content" "uninstall removed user content"
fi

test_summary
