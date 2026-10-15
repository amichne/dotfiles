#!/usr/bin/env bash

set -euo pipefail

CHECK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$CHECK_ROOT"

command -v zsh >/dev/null 2>&1 || {
    printf 'check: required command missing: zsh\n' >&2
    exit 69
}
command -v shellcheck >/dev/null 2>&1 || {
    printf 'check: required command missing: shellcheck\n' >&2
    exit 69
}

for check_test in tests/*_test.sh; do
    printf '==> %s\n' "$check_test"
    bash "$check_test"
done

printf '==> Bash syntax\n'
while IFS= read -r check_file; do
    bash -n "$check_file"
done < <(find bin lib scripts tests -type f \( -name '*.sh' -o -path 'bin/dotfiles' \) | sort)

printf '==> Zsh syntax\n'
while IFS= read -r check_file; do
    zsh -n "$check_file"
done < <(find shell plugins tests/fixtures -type f -name '*.zsh' | sort)

printf '==> ShellCheck\n'
shellcheck -S warning -x -s bash bin/dotfiles bin/ai ai/tasks/ci ai/tasks/review lib/*.sh scripts/*.sh tests/*.sh

printf '==> AI command contracts\n'
uv run --locked --project ai python ai/check.py

printf '==> Consolidated integration proofs\n'
uv run --locked --project tests/upstream-plan ruff format --check tests/upstream-plan
uv run --locked --project tests/upstream-plan ruff check tests/upstream-plan
uv run --locked --project tests/upstream-plan pyright --project tests/upstream-plan/pyproject.toml
uv run --locked --project tests/upstream-plan pytest tests/upstream-plan -q -p no:cacheprovider
uv run --locked --script tests/upstream-plan/standalone.py --self-test

printf '==> Whitespace and secret-shaped source scan\n'
if rg -n '[[:blank:]]+$' . \
    -g '!**/.git/**' \
    -g '!config/*.tsv'; then
    printf 'check: trailing whitespace found\n' >&2
    exit 65
fi
if rg -n '(gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)' \
    config home lib plugins profiles shell; then
    printf 'check: secret-shaped source content found\n' >&2
    exit 65
fi

printf '==> Production registries\n'
check_home="$(mktemp -d)"
trap 'rm -rf "$check_home"' EXIT
HOME="$check_home" \
    XDG_CONFIG_HOME="$check_home/.config" \
    DOTFILES_CONFIG_FILE="$check_home/config.conf" \
    sh -c ': >"$DOTFILES_CONFIG_FILE"; "$1/bin/dotfiles" config validate; "$1/bin/dotfiles" plugins validate' sh "$CHECK_ROOT"

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git diff --check
fi

printf 'All checks passed.\n'
