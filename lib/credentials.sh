#!/usr/bin/env bash

dotfiles_credential_resolve() {
    local dotfiles_credential_provider="$1"
    local dotfiles_credential_reference="$2"
    local dotfiles_credential_value

    case "$dotfiles_credential_provider" in
        env)
            case "$dotfiles_credential_reference" in
                ''|*[!A-Za-z0-9_]*)
                    dotfiles_error "invalid credential environment variable: $dotfiles_credential_reference"
                    return 65
                    ;;
            esac
            dotfiles_credential_value="$(printenv "$dotfiles_credential_reference" 2>/dev/null)" || {
                dotfiles_error "credential environment variable is unset: $dotfiles_credential_reference"
                return 69
            }
            ;;
        gh)
            command -v gh >/dev/null 2>&1 || {
                dotfiles_error "credential provider is unavailable: gh"
                return 69
            }
            dotfiles_credential_value="$(command gh auth token 2>/dev/null)" || {
                dotfiles_error "GitHub CLI did not provide a credential"
                return 69
            }
            ;;
        security)
            [ -n "$dotfiles_credential_reference" ] || {
                dotfiles_error "security credential provider requires a reference"
                return 65
            }
            command -v security >/dev/null 2>&1 || {
                dotfiles_error "credential provider is unavailable: security"
                return 69
            }
            dotfiles_credential_value="$(command security find-generic-password -s "$dotfiles_credential_reference" -w 2>/dev/null)" || {
                dotfiles_error "security credential reference was not found"
                return 69
            }
            ;;
        op)
            [ -n "$dotfiles_credential_reference" ] || {
                dotfiles_error "op credential provider requires a reference"
                return 65
            }
            command -v op >/dev/null 2>&1 || {
                dotfiles_error "credential provider is unavailable: op"
                return 69
            }
            dotfiles_credential_value="$(command op read "$dotfiles_credential_reference" 2>/dev/null)" || {
                dotfiles_error "op credential reference was not found"
                return 69
            }
            ;;
        pass)
            [ -n "$dotfiles_credential_reference" ] || {
                dotfiles_error "pass credential provider requires a reference"
                return 65
            }
            command -v pass >/dev/null 2>&1 || {
                dotfiles_error "credential provider is unavailable: pass"
                return 69
            }
            dotfiles_credential_value="$(command pass show "$dotfiles_credential_reference" 2>/dev/null | head -n 1)" || {
                dotfiles_error "pass credential reference was not found"
                return 69
            }
            ;;
        none)
            dotfiles_error "credential provider is disabled"
            return 69
            ;;
        *)
            dotfiles_error "unsupported credential provider: $dotfiles_credential_provider"
            return 65
            ;;
    esac

    if [ -z "$dotfiles_credential_value" ]; then
        dotfiles_error "credential provider returned an empty value"
        return 69
    fi
    printf '%s' "$dotfiles_credential_value"
}

dotfiles_credential_exec_github() {
    local dotfiles_github_provider
    local dotfiles_github_reference
    local dotfiles_github_secret
    dotfiles_github_provider="$(dotfiles_config_get_value credential.github-provider)" || return
    dotfiles_github_reference="$(dotfiles_config_get_value credential.github-reference)" || return
    dotfiles_github_secret="$(dotfiles_credential_resolve "$dotfiles_github_provider" "$dotfiles_github_reference")" || return

    GITHUB_TOKEN="$dotfiles_github_secret" \
        GH_TOKEN="$dotfiles_github_secret" \
        "$@"
}

dotfiles_credential_command() {
    local dotfiles_credential_action="${1:-}"
    local dotfiles_credential_id="${2:-}"
    if [ "$#" -lt 4 ] || [ "$dotfiles_credential_action" != "exec" ] || [ "${3:-}" != "--" ]; then
        dotfiles_error "usage: dotfiles credential exec <id> -- <command> [args]"
        return 64
    fi
    shift 3

    case "$dotfiles_credential_id" in
        github) dotfiles_credential_exec_github "$@" ;;
        *)
            dotfiles_error "unknown credential id: $dotfiles_credential_id"
            return 64
            ;;
    esac
}
