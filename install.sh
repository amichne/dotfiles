#!/bin/sh
# Local entrypoint and remote bootstrap for the layered installation.
set -eu

fail() {
    printf 'dotfiles: %s\n' "$*" >&2
    exit 1
}

command -v uv >/dev/null 2>&1 || fail 'install uv 0.12.9 or newer first'

installer=scripts/install.py
if [ "${1:-}" = --bootstrap ]; then
    shift
    origin=https://github.com/amichne/dotfiles.git
    commit=
    if [ "${1:-}" = --commit ]; then
        commit=${2:-}
        case "$commit" in
            ''|*[!0123456789abcdef]*) fail '--commit requires a full lowercase Git commit ID' ;;
        esac
        [ "${#commit}" -eq 40 ] || fail '--commit requires a full lowercase Git commit ID'
        shift 2
    fi

    command -v git >/dev/null 2>&1 || fail 'install Git first'
    case "${HOME:-}" in
        /*) ;;
        *) fail 'HOME must be an absolute path' ;;
    esac
    unset GIT_DIR GIT_COMMON_DIR GIT_WORK_TREE GIT_INDEX_FILE
    if [ "${1:-}" != --migrate ] && { [ -e "$HOME/.dotfiles.git" ] || [ -L "$HOME/.dotfiles.git" ]; }; then
        fail "bare installation at $HOME/.dotfiles.git; migration required (use --bootstrap [--commit SHA] --migrate)"
    fi
    root=$(CDPATH='' cd -- "$HOME" && pwd -P)/dotfiles
    [ ! -L "$root" ] || fail "$root is a symbolic link"
    if [ ! -e "$root" ]; then
        # Claim an absent path. Git normally also accepts an existing empty directory.
        mkdir -- "$root" || fail "cannot create $root"
        if git -c core.hooksPath=/dev/null clone --branch main -- "$origin" "$root"; then
            if [ -n "$commit" ]; then
                git -C "$root" -c core.hooksPath=/dev/null checkout --detach "$commit"
            else
                commit=$(git -C "$root" rev-parse --verify refs/remotes/origin/main)
            fi
        else
            status=$?
            rmdir -- "$root" 2>/dev/null || :
            exit "$status"
        fi
    fi

    [ -d "$root/.git" ] && [ ! -L "$root/.git" ] || fail "$root is not an ordinary checkout"
    top=$(git -C "$root" rev-parse --show-toplevel)
    [ "$top" = "$root" ] || fail "unexpected Git worktree at $root"
    remote=$(git -C "$root" config --local --get-all remote.origin.url)
    case "$remote" in
        "$origin"|https://github.com/amichne/dotfiles|git@github.com:amichne/dotfiles.git|ssh://git@github.com/amichne/dotfiles.git) ;;
        *) fail "unexpected origin at $root" ;;
    esac
    if [ -z "$commit" ]; then
        ref=$(git ls-remote --exit-code "$origin" refs/heads/main)
        commit=${ref%%[[:space:]]*}
    fi
    head=$(git -C "$root" rev-parse --verify HEAD)
    [ "$head" = "$commit" ] || fail "$root is at $head, requested $commit; review the checkout before updating it"
    changes=$(git -C "$root" -c core.fsmonitor=false status --porcelain --untracked-files=normal)
    [ -z "$changes" ] || fail "$root contains local changes"
    # A pinned checkout can predate the move to top-level scripts.
    if ! git -C "$root" ls-files --error-unmatch -- "$installer" >/dev/null 2>&1; then
        installer=.dotfiles/scripts/install.py
    fi
    git -C "$root" ls-files --error-unmatch -- install.sh "$installer" "$installer.lock" >/dev/null ||
        fail "$commit does not contain the layered installer"
else
    root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
fi

exec uv run --locked --script "$root/$installer" --layered "$@"
