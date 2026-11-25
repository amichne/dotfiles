# export KAST_OUTPUT_TOON="${KAST_OUTPUT_TOON-1}"

# Shared worktree layout for shell-launched tools; raw Git needs an explicit path.
export WORKTREE_ROOT="${WORKTREE_ROOT:-$HOME/.worktrees}"
export WORKTRUNK_WORKTREE_PATH="$WORKTREE_ROOT/{{ remote_repo }}/{{ branch | sanitize }}"
# Bind the Worktrunk user alias to this checkout, including in non-interactive shells.
export DOTFILES_COMMAND=${${(%):-%x}:A:h}/.local/bin/dotfiles
export MISE_GLOBAL_CONFIG_FILE="${MISE_GLOBAL_CONFIG_FILE:-${${(%):-%x}:A:h}/.config/mise/config.toml}"
export WORKTRUNK_ALIASES__RECLAIM='"$DOTFILES_COMMAND" reclaim {{ args }}'
export FFF_ENABLE_HOME_SCAN=0

# Non-interactive shells (agent commands) pass an unmatched glob through, as
# bash does, instead of failing with "no matches found".
[[ -o interactive ]] || setopt NO_NOMATCH
