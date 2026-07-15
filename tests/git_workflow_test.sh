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
export DOTFILES_PROFILES=portable
unset DOTFILES_SCHEMA_FILE DOTFILES_PROFILE_FILES DOTFILES_PLUGIN_MANIFEST_FILE DOTFILES_DEPENDENCIES_FILE
mkdir -p "$(dirname "$DOTFILES_CONFIG_FILE")"
: >"$DOTFILES_CONFIG_FILE"

remote_repo="$TEST_TMP/remote.git"
work_repo="$TEST_TMP/work"
git init --bare -b main "$remote_repo" >/dev/null
git init -b main "$work_repo" >/dev/null
git -C "$work_repo" config user.name "Dotfiles Test"
git -C "$work_repo" config user.email "dotfiles@example.test"
printf 'base\n' >"$work_repo/tracked.txt"
git -C "$work_repo" add tracked.txt
git -C "$work_repo" commit -m "base" >/dev/null
git -C "$work_repo" remote add origin "$remote_repo"
git -C "$work_repo" push -u origin main >/dev/null
git --git-dir="$remote_repo" symbolic-ref HEAD refs/heads/main
git -C "$work_repo" remote set-head origin main
git -C "$work_repo" switch -c feature/TEST-123-work >/dev/null

mkdir -p "$work_repo/nested/child"
rr_output="$(
    cd "$work_repo/nested/child"
    PATH="/usr/bin:/bin" DOTFILES_ROOT="$TEST_ROOT" zsh -fc '
        source "$DOTFILES_ROOT/shell/zsh/entrypoint.zsh" || exit 1
        rr || exit 1
        pwd -P
    '
)"
physical_work_repo="$(cd "$work_repo" && pwd -P)"
if [ "$rr_output" = "$physical_work_repo" ]; then
    test_pass "rr changes to the repository root"
else
    test_fail "rr changes to the repository root" "unexpected directory: $rr_output"
fi

printf 'untracked\n' >"$work_repo/unstaged.txt"
before_commit="$(git -C "$work_repo" rev-parse HEAD)"
if (
    cd "$work_repo"
    PATH="/usr/bin:/bin" DOTFILES_ROOT="$TEST_ROOT" DOTFILES_GIT_COMMIT_STAGE=none \
        zsh -fc 'source "$DOTFILES_ROOT/shell/zsh/entrypoint.zsh" && commit no-stage' \
        >/dev/null 2>&1
); then
    test_fail "none staging policy does not stage untracked files" "commit unexpectedly succeeded"
else
    after_commit="$(git -C "$work_repo" rev-parse HEAD)"
    if [ "$before_commit" = "$after_commit" ] && [ -f "$work_repo/unstaged.txt" ]; then
        test_pass "none staging policy does not stage untracked files"
    else
        test_fail "none staging policy does not stage untracked files" "repository changed"
    fi
fi

printf 'tracked update\n' >>"$work_repo/tracked.txt"
if (
    cd "$work_repo"
    PATH="/usr/bin:/bin" DOTFILES_ROOT="$TEST_ROOT" DOTFILES_GIT_COMMIT_STAGE=tracked \
        zsh -fc 'source "$DOTFILES_ROOT/shell/zsh/entrypoint.zsh" && commit tracked-change' \
        >/dev/null
); then
    if [ "$(git -C "$work_repo" log -1 --pretty=%s)" = "TEST-123: tracked-change" ] \
        && [ "$(git -C "$work_repo" status --short -- unstaged.txt)" = "?? unstaged.txt" ]; then
        test_pass "tracked staging policy preserves untracked files and prefixes ticket"
    else
        test_fail "tracked staging policy preserves untracked files and prefixes ticket" "unexpected commit state"
    fi
else
    test_fail "tracked staging policy preserves untracked files and prefixes ticket" "commit failed"
fi

if (
    cd "$work_repo"
    PATH="/usr/bin:/bin" DOTFILES_ROOT="$TEST_ROOT" DOTFILES_GIT_COMMIT_STAGE=all \
        zsh -fc 'source "$DOTFILES_ROOT/shell/zsh/entrypoint.zsh" && commit all-change' \
        >/dev/null
); then
    if git -C "$work_repo" ls-files --error-unmatch unstaged.txt >/dev/null 2>&1; then
        test_pass "all staging policy preserves legacy stage-everything behavior"
    else
        test_fail "all staging policy preserves legacy stage-everything behavior" "untracked file was not committed"
    fi
else
    test_fail "all staging policy preserves legacy stage-everything behavior" "commit failed"
fi

if (
    cd "$work_repo"
    PATH="/usr/bin:/bin" DOTFILES_ROOT="$TEST_ROOT" \
        zsh -fc 'source "$DOTFILES_ROOT/shell/zsh/entrypoint.zsh" && push' \
        >/dev/null
); then
    if [ "$(git -C "$work_repo" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}')" = "origin/feature/TEST-123-work" ]; then
        test_pass "push sets upstream for the current branch"
    else
        test_fail "push sets upstream for the current branch" "upstream was not set"
    fi
else
    test_fail "push sets upstream for the current branch" "push failed"
fi

if (
    cd "$work_repo"
    PATH="/usr/bin:/bin" DOTFILES_ROOT="$TEST_ROOT" \
        zsh -fc 'source "$DOTFILES_ROOT/shell/zsh/entrypoint.zsh" && main' \
        >/dev/null
); then
    if [ "$(git -C "$work_repo" branch --show-current)" = "main" ]; then
        test_pass "main follows the remote default branch"
    else
        test_fail "main follows the remote default branch" "main branch was not selected"
    fi
else
    test_fail "main follows the remote default branch" "main command failed"
fi

test_summary
