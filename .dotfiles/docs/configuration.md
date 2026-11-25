# Configuration

`.zprofile` adds `~/.local/bin` and the mise shims to `PATH`.
`.zshrc` adds interactive history, completion, key bindings, and tool integrations.
It reads an optional `.zshrc.local` before tool initialization.
That file remains private.

## Install tools

`.config/mise/config.toml` owns exact mise tool pins, the Brew inventory, and setup tasks.
Review it before trusting or running it. Setup needs mise and uv on `PATH`.
On a new machine, install mise and Homebrew using their official instructions,
then run `mise install uv` to bootstrap the pinned script runner.
The script uses an existing Python 3.12 or 3.13 through uv; it has no third-party
dependencies. If neither interpreter is available, explicitly bootstrap one with
`mise exec -- uv python install 3.12`. The runner uses `--offline` so even a first
preview cannot silently download an interpreter. Missing bootstrap prerequisites
are hard failures before the per-item setup starts.

```sh
mise run setup:plan    # Offline inventory preview; no provider commands
mise run setup         # Attempt every item; report issues without blocking setup
mise run setup:strict  # Same attempts; exit 1 if any item remains incomplete
```

Setup installs the Brew formulae and casks first, then mise tools, one at a time.
The `setup_brew_formulae` and `setup_brew_casks` strings under `[vars]` are
whitespace-separated package names. The initial Brew list supplies Git, Neovim,
ShellCheck, Zsh, and its completion/highlighting packages. No casks are selected.
Keep version-managed tools in `[tools]` rather than adding duplicate Brew owners.
Brew versions follow the configured taps; only the mise versions are pinned.
Setup does not manage tap registration, GUI permissions, credentials, services,
Ayi/Pi installers, or editor plugins.

Existing Brew packages are left alone. Mise ensures each exact requested version
is installed without changing its pin. Setup does not run upgrades, cleanup,
uninstalls, automatic Homebrew updates, or automatic trust changes.
It disables mise task pre-installation so an unavailable pin cannot prevent the
per-item installer from starting. No setup step runs at shell startup.

A failed install, missing provider, or timeout produces an explicit item outcome
and retry command. Other items still run. The final report says `partial`, not
`complete`, when any item has an issue. Best-effort mode returns 0 for that partial
result so a larger setup can continue; use strict mode when completeness must
block the caller. Invalid configuration returns 2 before any install.
Cancellation stops immediately and returns nonzero. Each provider command has a
15-minute timeout; timed-out process groups are stopped before continuing.
A partial package-manager change is not rolled back.

The installer is also available directly, from any directory:

```sh
setup-tools --json                         # One JSON inventory report on stdout
setup-tools --apply --provider brew        # Brew only; rerun safely after repair
setup-tools --apply --strict --timeout 1800 # Allow 30 minutes per provider command
```

`--config` selects an inventory explicitly. Otherwise the script uses
`MISE_GLOBAL_CONFIG_FILE`, then `${XDG_CONFIG_HOME:-$HOME/.config}/mise/config.toml`.
Provider diagnostics go to stderr; failed commands show at most their last 2,000
output bytes. JSON reports contain `status`, `config`, `remaining`,
`missingProviders`, and `items` with target, outcome, command, retry command, and
native failure code when available. For example, an unavailable Brew executable
produces `outcome: "missing-provider"` and an overall `status: "partial"`.
Argument parsing errors use standard argparse stderr and exit 2.

Shell startup uses offline mise initialization and does not install missing tools.
On systems without Homebrew, supply `zsh-autosuggestions` and
`zsh-syntax-highlighting` through the system package manager and select
`--provider mise`. `ZSH_PLUGIN_ROOT` can select their reviewed physical package directory.

## Walk through a review

Try the handoff example in a terminal:

```sh
review walk --demo
```

Pick `handoff.sh`, then **Try the handoff with a disposable file**. Write what you expect to happen when you decline. At **Return the note?**, choose **No**. The next screen shows the file contents before and after the command. Press **q** to return. Choose **Leave a note** to keep your observation or **Come back later** to revisit the question.

For a GitHub review, use the current branch, a pull request number, or a URL:

```sh
review walk
review walk 42 --output my-review.md
review walk https://github.com/amichne/slopsentral/pull/166
```

Search the file list by name. Open a patch, check added lines for conflict markers, or record a note. The handoff trial uses a built-in example in a temporary directory. The patch check reads the diff that GitHub supplied.

Choose **Finish and preview draft** to see your notes, expectations, results, and files left for later. Press **q** to leave the preview. Choose **Yes** to save a new local Markdown file. The draft includes the PR URL and head commit. By default it is named `review-<short-sha>.md` or `review-demo.md` in the current directory. Posting the draft is a separate step.

The demo needs uv and Gum. Pull request mode also needs an authenticated GitHub CLI.

## Managed Zsh completions

`austincomplete` saves a completion and remembers how to regenerate it:

```zsh
austincomplete add -- atuin gen-completions --shell zsh
austincomplete update atuin
austincomplete update --all
austincomplete list
```

`add` infers the caller from the generator executable's basename.
For a different caller, use `austincomplete add <caller> -- <generator> <args>...`.
Arguments stay separate; updates run the executable directly without shell evaluation.
Use a bare executable name to follow the version currently selected by `PATH`.
Use absolute paths for file arguments that must work from other directories.
Generators must be executables, not shell aliases or functions.

Piped input needs an explicit caller. To retain an update recipe without running
its generator twice, include `--stdin` and the generator arguments:

```zsh
atuin gen-completions --shell zsh |
  austincomplete add atuin --stdin -- atuin gen-completions --shell zsh
```

Without generator arguments, `austincomplete add atuin` reads stdin and saves a
static completion. `update atuin` rejects static entries; `update --all` reports
and skips them. A pipe cannot tell the receiver its producer's invocation or
exit status. Prefer direct `add -- <generator> ...` when that status matters.

Recipes live in `${XDG_CONFIG_HOME:-$HOME/.config}/austincomplete/recipes/*.json`.
The default directory is in the public Git inventory, but registration never
stages or commits files. Review recipes before sharing; arguments must not contain
secrets. Recipes are executable authority: `update --all` runs every saved generator.
Generated files live in `${XDG_CACHE_HOME:-$HOME/.cache}/austincomplete/zsh/_<caller>`.
They stay out of Git. After clearing that cache or setting up another machine,
run `austincomplete update --all`; static entries require their original input again.

Only trust completion sources you would execute in your shell. Registration
requires a UTF-8 Zsh function file with a matching first-line `#compdef` command
registration and valid `zsh -n` syntax. It rejects empty output and files above
4 MiB. Syntax checks do not sandbox shell code. Generators have a 30-second timeout.
Failed generation or validation leaves previous recipes and completions untouched.
Each file replacement is atomic, but recipe and completion are not one filesystem
transaction; an I/O error between replacements is reported without claiming rollback.
Updates are serialized; `--all` continues after generator failures and returns nonzero
if any update fails. A malformed recipe stops the batch before any generator runs.
Generator exit codes are preserved; missing executables return 127 and timeouts 124.
Other validation failures return 2; filesystem failures return 1.

The autoloaded Zsh adapter refreshes the current shell after `add` or `update`,
including at the end of a pipeline. New shells discover saved files before
`compinit`; startup never runs this manager or refreshes its cache. Saved Atuin
and mise completions replace their startup generation. Other tool initialization
still runs normally. After adding this command to an already-running shell, use
`zs` once to load the adapter. An external invocation without the adapter updates
files only; existing shells need `zs` to pick them up.

`.local/bin/austincomplete` owns persistence and generator execution;
`.config/zsh/functions/austincomplete` owns current-shell refresh.
`.dotfiles/tests/test_austincomplete.py` covers replay, rejection, and Zsh registration.
`austincomplete list --json` emits an array of `{command, kind, argv}` records
(`argv` is absent for static entries). Human diagnostics go to stderr.

## Shell and editor

The shell loads `f`, `rr`, and `y` from `.config/zsh/functions`.
They search with ripgrep, enter the Git root, and return the selected Yazi directory.
`zs` starts a fresh login shell. Ctrl-W deletes identifier parts and path parts.
Ctrl-X ? opens `keys`. Ctrl-R uses Atuin history.
Ctrl-G opens the current repository's `origin` in a browser.
Ctrl-Shift-G opens the current branch's open GitHub pull request through the authenticated `gh` CLI.
If both shortcuts open the repository, map Ctrl-Shift-G in your terminal to send Escape followed by `[103;6u`.
Ctrl-T selects files with a bat preview.
Set `FZF_CTRL_T_OPTS` in `.zshrc.local` to customize the file preview.

`keys --list` prints shell and Yazi shortcuts.
`keys nvim --list` reads mappings from Neovim and can start its configured plugins.
Neovim needs version 0.12 or later.
Its health report names missing language servers and editor dependencies.

Starship shows the branch, upstream, sync state, file counts, worktree, and cached PR using local Git reads. If Git status is slow, it falls back to the branch or detached commit and marks the status unavailable. An incomplete untracked scan shows `?unknown`.

`→ origin//` means the upstream on `origin` has the same name as the local branch. Other upstreams display their full name.

The first prompt starts a background `wt list statusline --format=json` refresh. Later prompts can add working line counts, divergence and changed lines against the default branch, and the latest reported CI state. For example, `synced` describes the upstream, while `vs origin/main: ↑1 ↓61` describes a separate comparison. A bare `#` from Worktrunk only becomes a PR label if Worktrunk supplies a PR number.

Worktrunk gets four seconds in the background. The prompt reuses a snapshot for the same checkout, branch, and commit across the current and previous 30-second intervals. Missing, invalid, or expired data leaves the local Git labels visible.

The standalone `shell-prompt` command remains available for explicit queries.
Starship and Worktrunk use the terminal's ANSI palette. In Rex, both follow the selected Rex theme.
`shell-prompt context --json` reports repository facts without a network request.
`shell-prompt refresh-pr` explicitly refreshes PR data through GitHub CLI.
The helper needs Node and Git. The refresh operation also needs authenticated `gh`.

`~/.pi/agent` holds Pi configuration, public instructions, agents, prompts, and LSP settings.
Use [Pi setup](pi.md) for the public inventory and Kast registration.
The separate [Ayi repository](https://github.com/amichne/ayi) owns the AI registry and its optional installed links.

Use `nvim '+checkhealth editor'` for editor diagnostics.

Setup accepts exact version strings and tables with `version`, `asset_pattern`, and `bin_path`.
Table values must be nonempty strings, and `version` must contain an exact pin.
Unsupported table options fail before provider commands.
The selected mise configuration keeps the table options during installation.
