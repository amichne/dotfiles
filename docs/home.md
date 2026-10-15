# HOME setup

`amichne/dotfiles` uses HOME as its worktree and `~/.dotfiles.git` for Git metadata.
The tracked files are the live files. No extra runtime directory exists.

| Path | Purpose |
| --- | --- |
| `~/.dotfiles.git` | Bare Git metadata and the HOME index |
| `~/.zshrc`, `~/.zprofile` | Zsh startup |
| `~/.config` | Tool configuration and the shell helpers |
| `~/.local/bin` | Small command entry points |
| `~/scripts/df.py` | Locked Python manager for the bare repository |
| `~/.pi` | Public Pi resources |

## Daily use

```sh
df status
df diff
df add .config/starship.toml
df diff --cached
df commit -m "Adjust prompt"
df git log --oneline
df setup plan --json
```

`df add` stages only its named paths with literal Git path handling.
It rejects HOME itself, the Git metadata directory, and paths outside HOME.
`df commit` does not add files. Git keeps its configured identity, hooks, and signing behavior.
Use `df git` for explicit native Git operations.
Those arguments keep their native effects.
Use `/bin/df` for the system disk-space command.

`df setup plan` reads the repository identity, necessary files, and tracked changes.
It reports missing files and dirty paths without a file replacement or index change.
Its JSON form contains `repository`, `worktree`, `origin`, `missing`, and `status`.
A missing file or unexpected repository causes a nonzero exit status.

## Start in a new HOME

Install Git, uv, and Python 3.12 before these steps.
Use a reviewed revision of `amichne/dotfiles`.
Before checkout, compare its tracked paths with existing HOME files.
Keep each conflict for explicit review.

```sh
git clone --bare git@github.com:amichne/dotfiles.git "$HOME/.dotfiles.git"
git --git-dir="$HOME/.dotfiles.git" ls-tree -r --name-only HEAD
git --git-dir="$HOME/.dotfiles.git" --work-tree="$HOME" checkout --no-overwrite-ignore
```

The checkout command rejects conflicting untracked files, including ignored files.
Do not use a forced checkout to replace them.

After checkout, use:

```sh
df setup plan
```

Review `.config/mise/config.toml` before explicit tool installation.
Read [configuration](configuration.md) for shell dependencies and [AI commands](ai-commands.md) for optional links.
AI commands live in a separate [Ayi checkout](https://github.com/amichne/ayi).
Generated commands use that checkout's Git index.

Keep credentials, Pi authentication, sessions, caches, and machine overrides outside the public inventory.
The default-deny `.gitignore` lists the public source paths.
The repository supplies no Git identity or SSH signing key.
