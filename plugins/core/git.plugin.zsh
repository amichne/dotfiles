#!/usr/bin/env zsh

_dotfiles_git_repository_root() {
    command git rev-parse --show-toplevel 2>/dev/null
}

_dotfiles_git_current_branch() {
    command git symbolic-ref --quiet --short HEAD 2>/dev/null
}

_dotfiles_git_switch() {
    if command git switch --help >/dev/null 2>&1; then
        command git switch "$@"
    else
        command git checkout "$@"
    fi
}

rr() {
    local dotfiles_repository_root
    dotfiles_repository_root="$(_dotfiles_git_repository_root)" || {
        print -u2 -- "dotfiles: not inside a Git worktree"
        return 69
    }
    builtin cd -- "$dotfiles_repository_root"
}

main() {
    local dotfiles_remote="$DOTFILES_CFG_GIT_REMOTE"
    local dotfiles_default_branch="$DOTFILES_CFG_GIT_DEFAULT_BRANCH"
    local dotfiles_remote_head

    _dotfiles_git_repository_root >/dev/null || {
        print -u2 -- "dotfiles: not inside a Git worktree"
        return 69
    }

    command git fetch "$dotfiles_remote" || return
    dotfiles_remote_head="$(command git symbolic-ref --quiet --short "refs/remotes/$dotfiles_remote/HEAD" 2>/dev/null || true)"
    if [[ -n "$dotfiles_remote_head" ]]; then
        dotfiles_default_branch="${dotfiles_remote_head#"$dotfiles_remote"/}"
    fi

    _dotfiles_git_switch "$dotfiles_default_branch" || return
    command git pull --ff-only "$dotfiles_remote" "$dotfiles_default_branch"
}

push() {
    local dotfiles_current_branch
    dotfiles_current_branch="$(_dotfiles_git_current_branch)" || {
        print -u2 -- "dotfiles: cannot push a detached HEAD"
        return 69
    }
    command git push --set-upstream "$DOTFILES_CFG_GIT_REMOTE" "$dotfiles_current_branch"
}

commit() {
    local dotfiles_message="${*:-"(no message)"}"
    local dotfiles_current_branch
    local dotfiles_origin_url
    local dotfiles_ticket

    _dotfiles_git_repository_root >/dev/null || {
        print -u2 -- "dotfiles: not inside a Git worktree"
        return 69
    }
    dotfiles_current_branch="$(_dotfiles_git_current_branch)" || {
        print -u2 -- "dotfiles: cannot commit on a detached HEAD"
        return 69
    }

    case "$DOTFILES_CFG_GIT_COMMIT_STAGE" in
        none) ;;
        tracked) command git add -u -- || return ;;
        all) command git add -A -- || return ;;
        *)
            print -u2 -- "dotfiles: invalid commit staging policy: $DOTFILES_CFG_GIT_COMMIT_STAGE"
            return 65
            ;;
    esac

    dotfiles_ticket="$(print -r -- "$dotfiles_current_branch" | grep -Eo "$DOTFILES_CFG_GIT_TICKET_REGEX" | head -n 1 || true)"
    dotfiles_origin_url="$(command git remote get-url "$DOTFILES_CFG_GIT_REMOTE" 2>/dev/null || true)"

    if [[ -n "$DOTFILES_CFG_GIT_ENFORCE_TICKET_REMOTE" \
        && "$dotfiles_origin_url" == "$DOTFILES_CFG_GIT_ENFORCE_TICKET_REMOTE" \
        && -z "$dotfiles_ticket" ]]; then
        print -u2 -- "dotfiles: configured remote requires a ticket-bearing branch"
        return 65
    fi
    if [[ -n "$dotfiles_ticket" ]]; then
        dotfiles_message="$dotfiles_ticket: $dotfiles_message"
    fi

    command git commit -m "$dotfiles_message"
}
