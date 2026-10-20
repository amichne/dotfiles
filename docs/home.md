# HOME setup

`amichne/dotfiles` uses HOME as its worktree and `~/.dotfiles.git` for Git metadata.
The tracked files are the live files.

| Path | Purpose |
| --- | --- |
| `~/.dotfiles.git` | Bare Git metadata and the HOME index |
| `~/.zshrc`, `~/.zprofile` | Zsh startup |
| `~/.config` | Tool configuration and the shell helpers |
| `~/.local/bin` | Small command entry points |
| `~/scripts/df.py` | Locked Python manager for the bare repository |
| `~/.pi/agent` | Pi configuration and public resources |

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

## Install or update HOME

Install Git, uv 0.12.9 or later, and Python 3.12 or 3.13 first.
Use a reviewed, clean checkout of `amichne/dotfiles` as the source.
The installer uses that checkout's committed `HEAD`.
It applies the full revision, including public Pi resources.

From the reviewed checkout, get the JSON plan:

```sh
uv run --locked --script scripts/install.py
```

The plan lists the commit, changed paths, private files to keep, and a `planId`.
It reads HOME without an index change, fetch, or file replacement.
Examine the plan before application.
Then copy its `planId` into this command:

```sh
uv run --locked --script scripts/install.py --apply --expected-plan PLAN_ID
```

A changed commit, index, branch, or file invalidates the plan.
The installer creates `~/.dotfiles.git` for a new HOME.
For an existing installation, it accepts only a fast-forward update.
It keeps the existing branch and origin.
The HOME files remain the runtime files.

Dirty source files, dirty HOME files, divergent history, conflicting untracked files, and symlinks stop the plan.
Ignored files receive the same protection as other untracked files.
An untracked file with identical bytes and executable permission can become tracked without a conflict.
Resolve each conflict in a separate reviewed change.
The installer does not force a checkout or merge divergent commits.

Before a Git write, the installer copies changed preimages under `~/.local/state/dotfiles-install`.
Its private receipt records the source revision, previous revision, and recovery directory.
Each recovery directory contains a `files` tree with the original bytes and modes.
Formerly tracked native instructions, including Pi's `APPEND_SYSTEM.md`, remain as private files after their removal from the public inventory.
An interrupted update can leave partial state.
Use its receipt and preimages to examine that state before another application.
Git failures preserve their exit status and name the failed command stage.

To include the pinned delegation package, add `--with-pi-subagents` to both commands:

```sh
uv run --locked --script scripts/install.py --with-pi-subagents
uv run --locked --script scripts/install.py --with-pi-subagents --apply --expected-plan PLAN_ID
```

This option needs an installed `pi` command.
After the file update, it runs `pi install npm:pi-subagents@0.79.0` for `~/.pi/agent`.
The package command can access the network.
A package failure preserves its exit status and reports `package-failed`.
The file update remains in place.

After installation, run `df setup plan`.
Use `/reload` or start a fresh Pi session to load changed extensions.
The [B0 installer](engineering-baseline.md) separately manages private native instructions and hooks.
Its existing tool selections remain in place until an explicit B0 installation.

Review `.config/mise/config.toml` before explicit tool installation.
Read [configuration](configuration.md) for shell dependencies.
Use [Pi setup](pi.md) to register Kast at `~/.pi/agent`.
Read [Ayi commands](ayi-commands.md) for optional links.
Ayi commands live in a separate [Ayi checkout](https://github.com/amichne/ayi).
Generated commands use that checkout's Git index.

Keep credentials, Pi authentication, sessions, caches, and machine overrides outside the public inventory.
The default-deny `.gitignore` lists the public source paths.
The repository supplies no Git identity or SSH signing key.
