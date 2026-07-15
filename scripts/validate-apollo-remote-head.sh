#!/usr/bin/env bash

set -euo pipefail

VALIDATION_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
apollo_remote_url="${APOLLO_REMOTE_URL:-https://github.com/amichne/apollo.git}"
apollo_expected_head="${APOLLO_EXPECTED_HEAD:-}"
apollo_docker_image="${APOLLO_DOCKER_IMAGE:-alpine:3.20}"
apollo_ca_bundle=""
docker_arguments=(run --rm -i)

command -v docker >/dev/null 2>&1 || {
    printf 'validation: required command missing: docker\n' >&2
    exit 69
}

apollo_ca_bundle="$(
    "$VALIDATION_ROOT/bin/dotfiles" config export --format tsv \
        | awk -F '\t' '$1 == "DOTFILES_CFG_ENTERPRISE_CA_BUNDLE" { print $2 }'
)"

docker_arguments+=(
    -v "$VALIDATION_ROOT:/dotfiles:ro"
    -e "APOLLO_REMOTE_URL=$apollo_remote_url"
    -e "APOLLO_EXPECTED_HEAD=$apollo_expected_head"
    -e HTTP_PROXY
    -e HTTPS_PROXY
    -e NO_PROXY
    -e http_proxy
    -e https_proxy
    -e no_proxy
)

if [ -n "$apollo_ca_bundle" ]; then
    if [ ! -f "$apollo_ca_bundle" ]; then
        printf 'validation: configured enterprise CA bundle is missing: %s\n' "$apollo_ca_bundle" >&2
        exit 66
    fi
    docker_arguments+=(
        -v "$apollo_ca_bundle:/tmp/dotfiles-enterprise-ca.pem:ro"
        -e DOTFILES_CONTAINER_CA_BUNDLE=/tmp/dotfiles-enterprise-ca.pem
    )
fi

docker_arguments+=("$apollo_docker_image" sh /dotfiles/scripts/validate-apollo-remote-head-container.sh)

"$VALIDATION_ROOT/bin/dotfiles" credential exec github -- \
    sh -c 'printf "%s\n" "$GH_TOKEN"' \
    | "$VALIDATION_ROOT/bin/dotfiles" proxy exec -- docker "${docker_arguments[@]}"
