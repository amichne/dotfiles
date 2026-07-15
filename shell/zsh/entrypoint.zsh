#!/usr/bin/env zsh

if [[ -z "${ZSH_VERSION:-}" ]]; then
    return 64 2>/dev/null || exit 64
fi

typeset _dotfiles_entrypoint_file="${(%):-%x}"
typeset -gx DOTFILES_ROOT="${_dotfiles_entrypoint_file:A:h:h:h}"

if [[ "${DOTFILES_RUNTIME_LOADED:-0}" == "1" && "${DOTFILES_RUNTIME_ROOT:-}" == "$DOTFILES_ROOT" ]]; then
    unset _dotfiles_entrypoint_file
    return 0
fi

typeset _dotfiles_config_records
_dotfiles_config_records="$("$DOTFILES_ROOT/bin/dotfiles" config export --format tsv)" || {
    unset _dotfiles_entrypoint_file _dotfiles_config_records
    return 1
}

typeset _dotfiles_config_name _dotfiles_config_value
while IFS=$'\t' read -r _dotfiles_config_name _dotfiles_config_value; do
    [[ -n "$_dotfiles_config_name" ]] || continue
    if [[ ! "$_dotfiles_config_name" =~ '^DOTFILES_CFG_[A-Z0-9_]+$' ]]; then
        print -u2 -- "dotfiles: invalid runtime configuration variable: $_dotfiles_config_name"
        unset _dotfiles_entrypoint_file _dotfiles_config_records \
            _dotfiles_config_name _dotfiles_config_value
        return 65
    fi
    export "$_dotfiles_config_name=$_dotfiles_config_value"
done <<<"$_dotfiles_config_records"

typeset -gx EDITOR="$DOTFILES_CFG_SHELL_EDITOR"
typeset -gx HISTFILE="$DOTFILES_CFG_SHELL_HISTORY_FILE"
typeset -gi HISTSIZE="$DOTFILES_CFG_SHELL_HISTORY_SIZE"
typeset -gi SAVEHIST="$DOTFILES_CFG_SHELL_SAVE_HISTORY"

setopt append_history
setopt extended_history
setopt hist_ignore_dups
setopt hist_ignore_space
setopt hist_verify
setopt share_history

typeset -a _dotfiles_prepend_entries _dotfiles_initial_entries _dotfiles_append_entries
typeset -a _dotfiles_ordered_entries _dotfiles_unique_entries
typeset -A _dotfiles_seen_entries
typeset _dotfiles_path_entry

if [[ -n "$DOTFILES_CFG_PATH_PREPEND" ]]; then
    _dotfiles_prepend_entries=("${(@s.:.)DOTFILES_CFG_PATH_PREPEND}")
fi
_dotfiles_initial_entries=("${(@s.:.)PATH}")
if [[ -n "$DOTFILES_CFG_PATH_APPEND" ]]; then
    _dotfiles_append_entries=("${(@s.:.)DOTFILES_CFG_PATH_APPEND}")
fi

_dotfiles_ordered_entries=(
    "${_dotfiles_prepend_entries[@]}"
    "${_dotfiles_initial_entries[@]}"
    "${_dotfiles_append_entries[@]}"
)

for _dotfiles_path_entry in "${_dotfiles_ordered_entries[@]}"; do
    [[ -n "$_dotfiles_path_entry" ]] || continue
    [[ -z "${_dotfiles_seen_entries[$_dotfiles_path_entry]:-}" ]] || continue
    _dotfiles_seen_entries[$_dotfiles_path_entry]=1
    _dotfiles_unique_entries+=("$_dotfiles_path_entry")
done
typeset -gx PATH="${(j.:.)_dotfiles_unique_entries}"

typeset _dotfiles_plugin_paths _dotfiles_plugin_file
_dotfiles_plugin_paths="$("$DOTFILES_ROOT/bin/dotfiles" plugins paths)" || {
    unset _dotfiles_entrypoint_file _dotfiles_config_records \
        _dotfiles_config_name _dotfiles_config_value _dotfiles_prepend_entries \
        _dotfiles_initial_entries _dotfiles_append_entries _dotfiles_ordered_entries \
        _dotfiles_unique_entries _dotfiles_seen_entries _dotfiles_path_entry \
        _dotfiles_plugin_paths _dotfiles_plugin_file
    return 1
}

for _dotfiles_plugin_file in "${(@f)_dotfiles_plugin_paths}"; do
    [[ -n "$_dotfiles_plugin_file" ]] || continue
    source "$_dotfiles_plugin_file" || {
        print -u2 -- "dotfiles: plugin failed to load: $_dotfiles_plugin_file"
        return 1
    }
done

typeset -gx DOTFILES_RUNTIME_ROOT="$DOTFILES_ROOT"
typeset -gx DOTFILES_RUNTIME_LOADED=1

unset _dotfiles_entrypoint_file _dotfiles_config_records \
    _dotfiles_config_name _dotfiles_config_value _dotfiles_prepend_entries \
    _dotfiles_initial_entries _dotfiles_append_entries _dotfiles_ordered_entries \
    _dotfiles_unique_entries _dotfiles_seen_entries _dotfiles_path_entry \
    _dotfiles_plugin_paths _dotfiles_plugin_file

return 0
