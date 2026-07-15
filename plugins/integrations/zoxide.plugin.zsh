#!/usr/bin/env zsh

typeset _dotfiles_zoxide_init
_dotfiles_zoxide_init="$(command zoxide init zsh)" || {
    print -u2 -- "dotfiles: zoxide initialization failed"
    return 69
}
eval "$_dotfiles_zoxide_init"
unset _dotfiles_zoxide_init
