#!/usr/bin/env zsh

typeset _dotfiles_warp_init
_dotfiles_warp_init="$(command wt config shell init zsh 2>/dev/null)" || {
    print -u2 -- "dotfiles: Warp initialization failed"
    return 69
}
if [[ -z "$_dotfiles_warp_init" ]]; then
    print -u2 -- "dotfiles: Warp returned an empty initialization script"
    return 69
fi
eval "$_dotfiles_warp_init"
unset _dotfiles_warp_init
