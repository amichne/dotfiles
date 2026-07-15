#!/usr/bin/env zsh

typeset _dotfiles_atuin_init
_dotfiles_atuin_init="$(command atuin init zsh)" || {
    print -u2 -- "dotfiles: Atuin initialization failed"
    return 69
}
eval "$_dotfiles_atuin_init"
unset _dotfiles_atuin_init
