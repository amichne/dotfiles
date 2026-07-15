#!/usr/bin/env zsh

typeset _dotfiles_starship_init
_dotfiles_starship_init="$(command starship init zsh)" || {
    print -u2 -- "dotfiles: Starship initialization failed"
    return 69
}
eval "$_dotfiles_starship_init"
unset _dotfiles_starship_init
