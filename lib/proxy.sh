#!/usr/bin/env bash

dotfiles_url_encode() {
    local dotfiles_raw_value="$1"
    local dotfiles_encoded_value=""
    local dotfiles_character
    local dotfiles_encoded_character
    local dotfiles_position
    local LC_ALL=C

    dotfiles_position=0
    while [ "$dotfiles_position" -lt "${#dotfiles_raw_value}" ]; do
        dotfiles_character="${dotfiles_raw_value:$dotfiles_position:1}"
        case "$dotfiles_character" in
            [A-Za-z0-9.~_-]) dotfiles_encoded_character="$dotfiles_character" ;;
            *) printf -v dotfiles_encoded_character '%%%02X' "'$dotfiles_character" ;;
        esac
        dotfiles_encoded_value="$dotfiles_encoded_value$dotfiles_encoded_character"
        dotfiles_position=$((dotfiles_position + 1))
    done
    printf '%s' "$dotfiles_encoded_value"
}

dotfiles_proxy_authenticated_url() {
    local dotfiles_proxy_url="$1"
    local dotfiles_proxy_username="$2"
    local dotfiles_proxy_provider="$3"
    local dotfiles_proxy_reference="$4"
    local dotfiles_proxy_secret
    local dotfiles_proxy_scheme
    local dotfiles_proxy_remainder
    local dotfiles_proxy_encoded_username
    local dotfiles_proxy_encoded_secret

    [ -n "$dotfiles_proxy_username" ] || {
        dotfiles_error "authenticated proxy requires proxy.username"
        return 65
    }
    case "$dotfiles_proxy_url" in
        *'@'*)
            dotfiles_error "proxy.url must not contain embedded credentials"
            return 65
            ;;
    esac

    dotfiles_proxy_secret="$(dotfiles_credential_resolve "$dotfiles_proxy_provider" "$dotfiles_proxy_reference")" || return
    dotfiles_proxy_scheme="${dotfiles_proxy_url%%://*}"
    dotfiles_proxy_remainder="${dotfiles_proxy_url#*://}"
    dotfiles_proxy_encoded_username="$(dotfiles_url_encode "$dotfiles_proxy_username")" || return
    dotfiles_proxy_encoded_secret="$(dotfiles_url_encode "$dotfiles_proxy_secret")" || return
    printf '%s://%s:%s@%s' \
        "$dotfiles_proxy_scheme" \
        "$dotfiles_proxy_encoded_username" \
        "$dotfiles_proxy_encoded_secret" \
        "$dotfiles_proxy_remainder"
}

dotfiles_proxy_exec() {
    local dotfiles_proxy_mode
    local dotfiles_proxy_url
    local dotfiles_proxy_no_proxy
    local dotfiles_proxy_provider
    local dotfiles_proxy_reference
    local dotfiles_proxy_username
    local dotfiles_proxy_effective_url
    local dotfiles_proxy_inherited_no_proxy
    local dotfiles_proxy_ca_bundle
    local dotfiles_ssl_cert_file
    local dotfiles_requests_ca_bundle
    local dotfiles_curl_ca_bundle
    local dotfiles_node_extra_ca_certs
    local dotfiles_git_ssl_cainfo

    dotfiles_proxy_mode="$(dotfiles_config_get_value proxy.mode)" || return
    dotfiles_proxy_url="$(dotfiles_config_get_value proxy.url)" || return
    dotfiles_proxy_no_proxy="$(dotfiles_config_get_value proxy.no-proxy)" || return
    dotfiles_proxy_provider="$(dotfiles_config_get_value proxy.credential-provider)" || return
    dotfiles_proxy_reference="$(dotfiles_config_get_value proxy.credential-reference)" || return
    dotfiles_proxy_username="$(dotfiles_config_get_value proxy.username)" || return
    dotfiles_proxy_ca_bundle="$(dotfiles_config_get_value enterprise.ca-bundle)" || return
    if [ -n "$dotfiles_proxy_ca_bundle" ] && [ ! -f "$dotfiles_proxy_ca_bundle" ]; then
        dotfiles_error "enterprise CA bundle is missing: $dotfiles_proxy_ca_bundle"
        return 66
    fi
    dotfiles_ssl_cert_file="${dotfiles_proxy_ca_bundle:-${SSL_CERT_FILE:-}}"
    dotfiles_requests_ca_bundle="${dotfiles_proxy_ca_bundle:-${REQUESTS_CA_BUNDLE:-}}"
    dotfiles_curl_ca_bundle="${dotfiles_proxy_ca_bundle:-${CURL_CA_BUNDLE:-}}"
    dotfiles_node_extra_ca_certs="${dotfiles_proxy_ca_bundle:-${NODE_EXTRA_CA_CERTS:-}}"
    dotfiles_git_ssl_cainfo="${dotfiles_proxy_ca_bundle:-${GIT_SSL_CAINFO:-}}"

    case "$dotfiles_proxy_mode" in
        off)
            HTTP_PROXY='' HTTPS_PROXY='' ALL_PROXY='' \
                http_proxy='' https_proxy='' all_proxy='' \
                NO_PROXY="$dotfiles_proxy_no_proxy" no_proxy="$dotfiles_proxy_no_proxy" \
                SSL_CERT_FILE="$dotfiles_ssl_cert_file" \
                REQUESTS_CA_BUNDLE="$dotfiles_requests_ca_bundle" \
                CURL_CA_BUNDLE="$dotfiles_curl_ca_bundle" \
                NODE_EXTRA_CA_CERTS="$dotfiles_node_extra_ca_certs" \
                GIT_SSL_CAINFO="$dotfiles_git_ssl_cainfo" \
                "$@"
            ;;
        inherit)
            dotfiles_proxy_inherited_no_proxy="${NO_PROXY:-${no_proxy:-$dotfiles_proxy_no_proxy}}"
            NO_PROXY="$dotfiles_proxy_inherited_no_proxy" \
                no_proxy="$dotfiles_proxy_inherited_no_proxy" \
                SSL_CERT_FILE="$dotfiles_ssl_cert_file" \
                REQUESTS_CA_BUNDLE="$dotfiles_requests_ca_bundle" \
                CURL_CA_BUNDLE="$dotfiles_curl_ca_bundle" \
                NODE_EXTRA_CA_CERTS="$dotfiles_node_extra_ca_certs" \
                GIT_SSL_CAINFO="$dotfiles_git_ssl_cainfo" \
                "$@"
            ;;
        explicit)
            [ -n "$dotfiles_proxy_url" ] || {
                dotfiles_error "proxy.mode=explicit requires proxy.url"
                return 65
            }
            dotfiles_proxy_effective_url="$dotfiles_proxy_url"
            if [ "$dotfiles_proxy_provider" != "none" ]; then
                dotfiles_proxy_effective_url="$(dotfiles_proxy_authenticated_url \
                    "$dotfiles_proxy_url" \
                    "$dotfiles_proxy_username" \
                    "$dotfiles_proxy_provider" \
                    "$dotfiles_proxy_reference")" || return
            fi
            HTTP_PROXY="$dotfiles_proxy_effective_url" \
                HTTPS_PROXY="$dotfiles_proxy_effective_url" \
                http_proxy="$dotfiles_proxy_effective_url" \
                https_proxy="$dotfiles_proxy_effective_url" \
                NO_PROXY="$dotfiles_proxy_no_proxy" \
                no_proxy="$dotfiles_proxy_no_proxy" \
                SSL_CERT_FILE="$dotfiles_ssl_cert_file" \
                REQUESTS_CA_BUNDLE="$dotfiles_requests_ca_bundle" \
                CURL_CA_BUNDLE="$dotfiles_curl_ca_bundle" \
                NODE_EXTRA_CA_CERTS="$dotfiles_node_extra_ca_certs" \
                GIT_SSL_CAINFO="$dotfiles_git_ssl_cainfo" \
                "$@"
            ;;
    esac
}

dotfiles_proxy_command() {
    if [ "$#" -lt 3 ] || [ "${1:-}" != "exec" ] || [ "${2:-}" != "--" ]; then
        dotfiles_error "usage: dotfiles proxy exec -- <command> [args]"
        return 64
    fi
    shift 2
    dotfiles_proxy_exec "$@"
}
