# Migration from Apollo and Artemis

The live machine currently sources Apollo through direct, unmarked lines and
Artemis through a managed block. Do not source this runtime beside them
permanently: all three define overlapping shell names.

## 1. Validate without changing the home directory

```sh
cd "$HOME/code/dotfiles"
./scripts/check.sh
./bin/dotfiles profile set personal
./bin/dotfiles doctor
./bin/dotfiles install plan
```

Normal doctor should pass on the current machine while explaining optional
missing tools. Strict doctor intentionally fails until every `auto` integration
is installed or changed to `off`.

To inspect or render the checked-in Apollo/Artemis profile without sourcing it:

```sh
./bin/dotfiles migrate apollo plan --source /path/to/apollo
./bin/dotfiles migrate apollo render --source /path/to/apollo >candidate.conf
DOTFILES_CONFIG_FILE="$PWD/candidate.conf" ./bin/dotfiles config validate
```

The converter accepts only static assignments, normalizes `$HOME` to the typed
`${HOME}` placeholder, and rejects command substitutions and other shell
expressions. It maps Artemis feature, path, locale, history, Java, and Codex
settings. Apollo provider selection, GPG terminal mutation, `gh/hosts.yml`, and
Jira host/auth configuration remain explicitly outside the shell config.

The end-to-end Docker proof clones the configured Apollo remote at its current
HEAD, renders and validates the candidate, and loads the compatibility surface
in clean Zsh:

```sh
APOLLO_EXPECTED_HEAD=5fa67491d6c1f204bd42dda4946a74268db95e11 \
  ./scripts/validate-apollo-remote-head.sh
```

The validation uses `credential.github-provider`, command-scoped proxy
configuration, and `enterprise.ca-bundle`. `APOLLO_REMOTE_URL` and
`APOLLO_DOCKER_IMAGE` allow an enterprise Git host or approved image mirror;
`APOLLO_EXPECTED_HEAD` is optional but makes the proof reproducible. The token
is streamed to the disposable container and is never written to the output or
repository.

## 2. Back up the live entrypoint

Migration removes the Apollo and Artemis managed blocks. Uninstall does not
recreate them, so retain a backup until the new shell has soaked:

```sh
cp -p ~/.zshrc ~/.zshrc.pre-dotfiles
```

The old Apollo checkout itself remains untouched and can still be used for
comparison.

## 3. Review machine-local configuration

Edit `~/.config/dotfiles/config.conf`. For the current behavior, the persisted
`personal` profile preserves `git.commit-stage=all`, personal local paths, and
the current locale. Prefer narrower machine overrides over editing tracked
profiles.

Before applying static Git config, put identity and OS-specific credential
policy in `~/.config/git/local.ini`; see the configuration guide.

## 4. Transfer shell ownership

```sh
./bin/dotfiles install apply --migrate
exec zsh -l
```

The installer atomically removes the recognized direct Apollo export/source
lines and both legacy managed-block forms, preserves all surrounding user
content, installs exactly one dotfiles block, and never overwrites the local
config or selected profile.

Verify the interactive surface:

```sh
dotfiles status
dotfiles doctor
type l zs rr f main push commit
printf '%s\n' "$PATH" | tr ':' '\n' | awk '!seen[$0]++'
```

`zs` now replaces the current process with a fresh login Zsh. This avoids the
partial unload and duplicate-hook problems caused by repeatedly sourcing a
large runtime into the same namespace.

## 5. Adopt static files separately

```sh
dotfiles home plan
dotfiles home apply
dotfiles home status
```

Review the diff carefully: the adapter owns `.gitconfig`, `.vimrc`,
`.ideavimrc`, `.config/git/ignore`, and `.config/atuin/config.toml`. It does not
own application auth state. If a target has local changes, chezmoi runs with no
TTY and fails instead of silently overwriting it.

## Rollback

Remove the new managed block without touching machine config:

```sh
dotfiles install uninstall
```

To restore the exact pre-migration dual runtime, restore the backup explicitly:

```sh
cp -p ~/.zshrc.pre-dotfiles ~/.zshrc
exec zsh -l
```

Use `chezmoi -S "${HOME}/code/dotfiles/home" diff` to inspect static
file drift before reversing any home-managed file. No automated rollback should
guess which preexisting application file is authoritative.

## Behavior changes worth keeping

- `rr` now changes directory to the worktree root.
- `main` follows the remote default and uses fast-forward-only pull.
- `commit` staging is typed; `personal` keeps legacy `all`, while portable and
  enterprise defaults can use `none` or `tracked`.
- `rebase --no-verify`, reset-based `squash`, global `git`, and global `rmdir`
  overrides are not carried forward.
- Tokens and authenticated proxy URLs are never exported during startup.
- SDKMAN is loaded on first use rather than every shell.
- Apollo agent/provider asset synchronization is outside this shell runtime.
