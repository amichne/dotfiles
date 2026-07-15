#!/usr/bin/env zsh

typeset -gx SDKMAN_DIR="$DOTFILES_CFG_TOOLS_SDKMAN_DIR"
typeset -gi DOTFILES_SDKMAN_LOADED=0

_dotfiles_sdkman_load() {
    if (( DOTFILES_SDKMAN_LOADED == 1 )); then
        return 0
    fi

    local dotfiles_sdkman_init="$SDKMAN_DIR/bin/sdkman-init.sh"
    if [[ ! -r "$dotfiles_sdkman_init" ]]; then
        print -u2 -- "dotfiles: SDKMAN init file is missing: $dotfiles_sdkman_init"
        return 69
    fi
    source "$dotfiles_sdkman_init" || return
    typeset -gi DOTFILES_SDKMAN_LOADED=1
    if [[ -d "$DOTFILES_CFG_TOOLS_JAVA_HOME" ]]; then
        typeset -gx JAVA_HOME="$DOTFILES_CFG_TOOLS_JAVA_HOME"
    fi
    rehash
}

_dotfiles_sdkman_dispatch() {
    local dotfiles_sdkman_command="$1"
    shift
    _dotfiles_sdkman_load || return

    if [[ "$dotfiles_sdkman_command" == "sdk" ]]; then
        if [[ "${functions[sdk]:-}" == *'_dotfiles_sdkman_dispatch sdk'* ]]; then
            print -u2 -- "dotfiles: SDKMAN did not define the sdk function"
            return 69
        fi
        sdk "$@"
        return
    fi
    command "$dotfiles_sdkman_command" "$@"
}

sdk() { _dotfiles_sdkman_dispatch sdk "$@"; }
java() { _dotfiles_sdkman_dispatch java "$@"; }
javac() { _dotfiles_sdkman_dispatch javac "$@"; }
kotlin() { _dotfiles_sdkman_dispatch kotlin "$@"; }
kotlinc() { _dotfiles_sdkman_dispatch kotlinc "$@"; }
gradle() { _dotfiles_sdkman_dispatch gradle "$@"; }
mvn() { _dotfiles_sdkman_dispatch mvn "$@"; }
