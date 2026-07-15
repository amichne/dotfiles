#!/usr/bin/env zsh

alias l='ls -lah'

zs() {
    local dotfiles_reload_shell="${DOTFILES_RELOAD_SHELL:-${SHELL:-}}"
    if [[ -z "$dotfiles_reload_shell" ]]; then
        dotfiles_reload_shell="$(command -v zsh)" || return 69
    fi
    if [[ ! -x "$dotfiles_reload_shell" ]]; then
        print -u2 -- "dotfiles: reload shell is not executable: $dotfiles_reload_shell"
        return 69
    fi
    exec "$dotfiles_reload_shell" -l
}

if [[ -n "$DOTFILES_CFG_SHELL_LOCALE" ]]; then
    export LANG="$DOTFILES_CFG_SHELL_LOCALE"
fi

if [[ -d "$DOTFILES_CFG_TOOLS_CODEX_HOME" ]]; then
    export CODEX_HOME="$DOTFILES_CFG_TOOLS_CODEX_HOME"
fi
