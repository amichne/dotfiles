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

## Worktree inventory

`df worktrees` reads registered worktrees from explicitly named repositories.
It needs Git, uv, and Python, but it does not need the bare HOME repository.

```sh
df worktrees --repo /path/to/project --repo "/path/with spaces" --json
```

The command reports each path, HEAD, branch, lock, pruning marker, and working-tree state.
It keeps every worktree, including clean worktrees.
It does not prove that a worktree is inactive or that its changes reached another branch.
A pruning marker does not authorize removal.
The command does not fetch, prune, remove files, refresh indexes, or inspect process lists.
It does not measure ignored output sizes.

`.config/worktree-inventory.toml` limits one invocation to 128 worktrees and 30 seconds across all named repositories.
The command accepts at most eight repositories.
Use `--config FILE` for explicit limits from another TOML file.
That file must contain only `max_worktrees` and `timeout_seconds`.
The accepted ranges are 1–512 worktrees and 1–120 seconds.

JSON output has `version`, `status`, `policy`, and `repositories`.
Each repository keeps its known worktrees and reports its failure codes.
A missing registered worktree has an unavailable working-tree state and stays in the inventory.
A failed Git read or exhausted limit returns `incomplete` with exit status 1.
Invalid arguments return exit status 64.
Invalid configuration returns exit status 1 before Git runs, without a `policy` field.
A complete report returns exit status 0.
Without `--json`, the command prints the same fields as indented JSON.

A report describes the state at inspection time.
Concurrent edits can change that state after a read.
Review ownership, source changes, delivery, and active use before a separate cleanup operation.

## Install or update HOME

Install Git, uv 0.12.9 or later, and Python 3.12 or 3.13 first.
The default setup also needs Pi 1.3.0, Node.js 22.19 or later, curl, and system tar.
Use a reviewed, clean checkout of `amichne/dotfiles` as the source.
The installer uses that checkout's committed `HEAD`.
It applies the full revision, including public Pi resources.
After the file update, it installs the latest stable Slopsentral release for Pi.
The plan lists `slopsentral@latest` without a network request.
The application resolves the release through Slopsentral's published installer.
Each application selects the current release, including applications without file changes.

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
The retired root `AGENTS.md` is removed, with its original bytes in the recovery directory.
[Repository instructions](repository-instructions.md) remain documentation and do not apply to projects beneath HOME.
An interrupted update can leave partial state.
Use its receipt and preimages to examine that state before another application.
Git failures preserve their exit status and name the failed command stage.

To skip Slopsentral, add `--without-slopsentral` to both the plan and application commands.
This option also removes the Pi, Node.js, curl, and tar prerequisites when no other package option needs them.

Slopsentral owns its native resources, release admission, and private recovery records.
The installer uses the [latest release launcher](https://github.com/amichne/slopsentral/releases/latest/download/install-pi.sh).
It uses `~/.local/state/dotfiles-install/slopsentral` as a stable scope for native recovery.
HOME does not become a project scope.
A download or setup failure preserves its exit status and reports `package-failed` with the failed stage.
The file update remains in place.
Use a fresh plan before another application.

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

Review `.config/mise/config.toml` before explicit tool installation.
Read [configuration](configuration.md) for shell dependencies.
Use [Pi setup](pi.md) to register Kast at `~/.pi/agent`.
Read [Ayi commands](ayi-commands.md) for optional links.
Ayi commands live in a separate [Ayi checkout](https://github.com/amichne/ayi).
Generated commands use that checkout's Git index.

Keep credentials, Pi authentication, sessions, caches, and machine overrides outside the public inventory.
The default-deny `.gitignore` lists the public source paths.
The repository supplies no Git identity or SSH signing key.
