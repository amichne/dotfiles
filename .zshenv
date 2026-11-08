export KAST_OUTPUT_TOON="${KAST_OUTPUT_TOON-1}"

# Shared worktree layout for shell-launched tools; raw Git needs an explicit path.
export WORKTREE_ROOT="${WORKTREE_ROOT:-$HOME/.worktrees}"
export WORKTRUNK_WORKTREE_PATH="$WORKTREE_ROOT/{{ remote_repo }}/{{ branch | sanitize }}"
export FFF_ENABLE_HOME_SCAN=0
