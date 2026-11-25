# HOME setup

## Install from an ordinary checkout

This installer needs Git, uv 0.12.9 or later, and Python 3.12 or 3.13.
The interactive shell also uses the tools and Zsh plugins listed in [configuration](configuration.md).
Install those dependencies separately.

From a checkout, run `./install.sh` to see the destination paths and exact blocks.
For a new machine, download the bootstrap into an empty working directory.

```sh
curl -fsSLo install-dotfiles.sh https://raw.githubusercontent.com/amichne/dotfiles/main/install.sh
/bin/sh install-dotfiles.sh --bootstrap
```

The remote bootstrap creates an ordinary checkout at `~/dotfiles` before it previews changes to startup files.
An existing checkout must be clean, have the expected origin, and match the requested commit.
For a pinned install, use the same full commit ID in the download URL and after `--bootstrap --commit`.
Read the plan, then apply it with the printed ID.

```sh
~/dotfiles/install.sh --apply --expected-plan PLAN_ID
```

| Destination | What the installer adds |
| --- | --- |
| `.zshenv`, `.zprofile`, `.zshrc` in `${ZDOTDIR:-$HOME}` | One marked source block per file. Zsh selects the environment, login, and interactive phases. |
| `git/config` in `${XDG_CONFIG_HOME:-$HOME/.config}` | A marked include for the shared aliases. Personal settings after the include take precedence. |
| `starship.toml` in the same configuration directory | One link to the checkout. An occupied path stops installation before the installer writes a hook. |
| `ghostty/themes/Neon Arcade` in the same configuration directory | A link makes the checkout palette available by name in Ghostty. |
| `ghostty/config.ghostty` in the same configuration directory | A marked block selects Neon Arcade and loads the cursor trail shader from the checkout. |
| `nvim/init.lua` in the same configuration directory | A link loads the editor setup and colorscheme from the checkout. |

Ghostty reads the palette from `.config/ghostty/themes/Neon Arcade` in the checkout.
The trail follows the terminal cursor and fades in 160 milliseconds. It uses the active cursor color.
Later personal theme or color settings can override it, including those in the macOS Application Support directory.
For Rex on another Mac, choose **Import Theme File** and select the same file. Import it again after you edit the palette.
Rex also includes Neon Arcade in its dark theme picker.

Shared blocks precede personal settings. The installer preserves an initial interpreter line in a startup file.
Interactive Zsh reads `.zshrc.local` before it initializes tools. It searches personal functions before checkout functions.
Use the same `ZDOTDIR` and `XDG_CONFIG_HOME` for preview, apply, and removal.
Symlinked destination parents require a manual decision. For a bare HOME, use [the migration procedure](#migrate-a-bare-home).

Keep the checkout at its installed path. Edit the public files there and use ordinary Git to review changes.
Fresh shells and Git commands read checkout edits directly. An update to the checkout takes effect on the next read.
Review incoming changes before advancing the checkout. The bootstrap never advances an existing checkout.

To remove the layer, preview removal and apply its plan ID.

```sh
~/dotfiles/install.sh --uninstall
~/dotfiles/install.sh --uninstall --apply --expected-plan PLAN_ID
```

Removal keeps personal text outside each block, preexisting empty files, and directories.
An edited marker or replaced Starship link stops removal and identifies the conflicting path.
Before a change, the installer saves original bytes and modes in a private recovery directory under `~/.local/state/dotfiles-install`.
Its receipt maps each changed path to a numbered backup or its former link target.
If an apply stops partway, inspect the receipt and run a fresh preview before retrying.

## Migrate a bare HOME

Migration accepts a clean bare installation on `main` at commit `cbe207a2585b05ebc9b738cb0574a98e3269fab8`.
It needs the original layout with Zsh startup files in `$HOME` and tool configuration in `$HOME/.config`.
Staged or unstaged changes to tracked HOME files and registered linked worktrees stop the migration.

From an ordinary checkout that contains the migration command, preview the change.

```sh
./install.sh --migrate
```

To obtain the checkout at `~/dotfiles`, run the bootstrap with the migration flag.

```sh
curl -fsSLo install-dotfiles.sh https://raw.githubusercontent.com/amichne/dotfiles/main/install.sh
/bin/sh install-dotfiles.sh --bootstrap --migrate
```

For a pinned installer, put `--commit INSTALLER_COMMIT` before `--migrate` and use that commit in the download URL.
The installer commit selects the new checkout. The old bare HOME must still match `cbe207a`.
Review the five destinations and archive path in the plan.
If you used the bootstrap, change to `~/dotfiles`. From the checkout, apply the printed ID.

```sh
./install.sh --migrate --apply --expected-plan PLAN_ID
```

The recovery directory is `~/.local/state/dotfiles-install/bare-main`. Its `files/` tree holds the five originals at their HOME-relative paths.
The installer replaces the three startup files with source blocks, the Git configuration with an include, and the Starship configuration with a link.
It moves the bare metadata to `repository.git` in the recovery directory last.
The remaining HOME files stay in place outside the layer. Manage checkout edits with ordinary Git.

If migration stops partway, run `./install.sh --migrate` from the same checkout.
The installer accepts each original file or its exact replacement. Inspect other changes at the reported paths.
Review the new plan and apply its printed ID.

After migration or an update from an older installer, run `./install.sh` to preview the new destinations.
If you want the checkout editor setup, move an existing personal `nvim/init.lua` or `nvim/init.vim` aside before installation.
Layered uninstall preserves the migration archive.

## Worktree location

`~/.zshenv` owns `WORKTREE_ROOT`, which defaults to `$HOME/.worktrees`.
It derives `WORKTRUNK_WORKTREE_PATH` as
`$WORKTREE_ROOT/{{ remote_repo }}/{{ branch | sanitize }}`.
Override `WORKTREE_ROOT` before starting Zsh to choose another root.
The remote repository name avoids local clone names such as `gradle-build-diff` for `drift`.
Branch slashes become hyphens. Existing migrated task suffixes can differ from branch names.

Use Worktrunk for CLI-owned worktrees from Pi, Codex, Amp, or an IDE terminal:

```sh
wt switch --create feature/example
```

Worktrunk 0.81.0 reads `WORKTRUNK_WORKTREE_PATH` from the environment.
`tests/test_home_source.py` checks default and overridden roots in a fresh Zsh process.
Raw `git worktree add` still requires an explicit destination; Git has no shared root setting.
`gh` does not apply this environment variable to arbitrary extensions.

Shell-launched tools inherit these exports. Already running agents and IDEs do not.
GUI launchers do not normally read `.zshenv`.
For newly launched apps in the current macOS login session, export the derived values:

```sh
launchctl setenv WORKTREE_ROOT "$WORKTREE_ROOT"
launchctl setenv WORKTRUNK_WORKTREE_PATH "$WORKTRUNK_WORKTREE_PATH"
```

Run these commands from a fresh Zsh shell after changing the root.
These login-session values do not persist across logout and do not update running processes.
An app must still use Worktrunk for this path template to apply.
Codex Desktop, native Codex `--worktree`, and JetBrains-managed worktrees are separate owners;
this setting does not establish their native layout or migrate their session records.
Do not replace their managed directories with symlinks or move them behind the host's back.
Use Worktrunk-created worktrees as existing projects when a native root setting is unavailable.

## Inspect worktrees

Use `wt list` in a repository to see its worktrees. For scripts, use `wt -C /path/to/project list --format=json`.
From a Git checkout, run `wt reclaim --repo /path/to/project` to preview cleanup.
Zsh registers this Worktrunk user alias for the checkout's `dotfiles reclaim` command.
It forwards arguments, including repeated `--repo` paths and an explicit `--apply`.
