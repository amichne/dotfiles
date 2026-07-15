#!/bin/sh

set -eu

IFS= read -r github_token
if [ -z "$github_token" ]; then
    printf 'validation: GitHub credential provider returned an empty token\n' >&2
    exit 69
fi

if [ -n "${DOTFILES_CONTAINER_CA_BUNDLE:-}" ]; then
    test -f "$DOTFILES_CONTAINER_CA_BUNDLE"
    mkdir -p /etc/ssl/certs
    cat "$DOTFILES_CONTAINER_CA_BUNDLE" >>/etc/ssl/certs/ca-certificates.crt
fi

apk add --no-cache bash ca-certificates git zsh >/dev/null

export GITHUB_TOKEN="$github_token"
git -c credential.helper='!f() { printf "username=x-access-token\npassword=%s\n" "$GITHUB_TOKEN"; }; f' \
    clone --depth 1 "$APOLLO_REMOTE_URL" /tmp/apollo >/dev/null 2>&1
unset GITHUB_TOKEN github_token

actual_head="$(git -C /tmp/apollo rev-parse HEAD)"
if [ -n "${APOLLO_EXPECTED_HEAD:-}" ] && [ "$actual_head" != "$APOLLO_EXPECTED_HEAD" ]; then
    printf 'validation: Apollo HEAD mismatch: expected %s, got %s\n' \
        "$APOLLO_EXPECTED_HEAD" "$actual_head" >&2
    exit 65
fi

mkdir -p /tmp/home/.config
/dotfiles/bin/dotfiles migrate apollo render --source /tmp/apollo >/tmp/converted.conf

for expected_row in \
    'feature.sdkman=off' \
    'feature.warp=off' \
    'path.prepend=/opt/homebrew/bin:/opt/homebrew/sbin' \
    'path.append=${HOME}/.docker/bin:${HOME}/.bin:${HOME}/.local/bin:${HOME}/.jetbrains' \
    'shell.history-file=${HOME}/.zsh_history' \
    'shell.locale=en_US.UTF-8' \
    'tools.codex-home=${HOME}/.codex' \
    'tools.java-home=${HOME}/.sdkman/candidates/java/current'; do
    grep -qFx "$expected_row" /tmp/converted.conf || {
        printf 'validation: expected converted row is missing: %s\n' "$expected_row" >&2
        exit 65
    }
done

if grep -Eq 'APOLLO_PROFILE|hosts\.yml|oauth_token|github\.com' /tmp/converted.conf; then
    printf 'validation: excluded provider or credential material reached converted config\n' >&2
    exit 65
fi

HOME=/tmp/home \
XDG_CONFIG_HOME=/tmp/home/.config \
DOTFILES_PROFILES=portable \
DOTFILES_CONFIG_FILE=/tmp/converted.conf \
    /dotfiles/bin/dotfiles config validate

HOME=/tmp/home \
XDG_CONFIG_HOME=/tmp/home/.config \
DOTFILES_PROFILES=portable \
DOTFILES_CONFIG_FILE=/tmp/converted.conf \
    zsh -fc '
        source /dotfiles/shell/zsh/entrypoint.zsh
        alias l >/dev/null
        whence -w zs rr f main push commit >/dev/null
    '

printf 'Apollo remote HEAD: %s\n' "$actual_head"
printf 'Converted configuration:\n'
sed 's/^/  /' /tmp/converted.conf
printf 'Schema validation: passed\n'
printf 'Zsh compatibility surface: passed\n'
