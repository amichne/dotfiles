# Configuration

`.zprofile` puts Homebrew before old mise shims and their links in `~/.local/bin`.
`.zshrc` adds interactive history, completion, key bindings, and tool integrations.
It reads an optional `.zshrc.local` before tool initialization.
That file remains private.

## Install tools

The checkout's `Brewfile` supplies the interactive shell, Git helpers, prompt, and setup tools.
It includes Gum, DiffNav, and its Delta renderer. The explicit Delta entry permits independent updates.
Mise manages the Temurin JDK and Kotlin compiler pins in `.config/mise/config.toml`.
Homebrew tools follow their formula versions.

From a fresh checkout with Homebrew on `PATH`, install the core formulae.

```sh
brew bundle install --file Brewfile --no-upgrade
```

For a later update, run `brew update` and then `brew bundle install --file Brewfile`.
Use `brew bundle check --file Brewfile` to see whether every selected formula is current.

If uv needs a Python interpreter, run `uv python install 3.12`.
With uv and Python 3.12 or 3.13 available, preview or apply setup from the checkout.

```sh
./.local/bin/setup-tools                  # Offline preview
./.local/bin/setup-tools --apply --strict # Install missing tools, then report failures
```

The script accepts literal `brew "name"` and `cask "name"` declarations in the core Brewfile.
It skips installed Brew packages and installs the two pinned toolchains through mise.
The existing `mise run setup:plan`, `setup`, and `setup:strict` tasks call the same script.
The shell uses the checkout as its global mise configuration. Projects can still select their own versions.
To use a personal global config, set `MISE_GLOBAL_CONFIG_FILE` before the checkout's Zsh environment hook.

For the optional editor language servers, jq, and Atlassian CLI, run
`brew bundle install --file Brewfile.development --no-upgrade`.
Atlassian supplies ACLI through its own tap. Homebrew can request trust for that formula.
On macOS this bundle includes the Kotlin language server for Neovim.

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
`MISE_GLOBAL_CONFIG_FILE`, then the config in the checkout that contains the script.
An installation directly under HOME uses `${XDG_CONFIG_HOME:-$HOME/.config}/mise/config.toml` as its fallback.
Provider diagnostics go to stderr; failed commands show at most their last 2,000
output bytes. JSON reports contain `status`, `config`, `remaining`,
`missingProviders`, and `items` with target, outcome, command, retry command, and
native failure code when available. For example, an unavailable Brew executable
produces `outcome: "missing-provider"` and an overall `status: "partial"`.
Argument parsing errors use standard argparse stderr and exit 2.

Shell startup initializes mise offline. On systems without Homebrew, install the shell tools through the system package manager.
Use `--provider mise` for the JDK and Kotlin compiler.
`ZSH_PLUGIN_ROOT` can select the system directory for the two Zsh plugins.

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
`tests/test_austincomplete.py` covers replay, rejection, and Zsh registration.
`austincomplete list --json` emits an array of `{command, kind, argv}` records
(`argv` is absent for static entries). Human diagnostics go to stderr.

## Shell and editor

The shell loads `f`, `rr`, and `y` from `.config/zsh/functions`.
They search with ripgrep, enter the Git root, and return the selected Yazi directory.
`zs` starts a fresh login shell. Ctrl-W deletes identifier parts and path parts.
Ctrl-X ? opens `keys`. Type in the Gum filter to find a shortcut. Press Enter to print it or Ctrl-C to cancel.
Ctrl-R uses Atuin history.
Ctrl-G opens the current repository's `origin` in a browser.
Ctrl-Shift-G opens the current branch's open GitHub pull request through the authenticated `gh` CLI.
If both shortcuts open the repository, map Ctrl-Shift-G in your terminal to send Escape followed by `[103;6u`.
Ctrl-T selects files with a bat preview.
Set `FZF_CTRL_T_OPTS` in `.zshrc.local` to customize the file preview.

Use `git diff --no-ext-diff | diffnav` for a file tree and colored diff, including when Git has an external diff driver.
Interactive Zsh selects DiffNav's built-in Neon theme to complement Ghostty's Neon Arcade.
DiffNav 0.13.1 accepts preset themes. It cannot import Ghostty's custom palette.
Set `DIFFNAV_THEME` in `.zshrc.local` to select a different preset.

`worktrunk-commit-message` opens a Gum input prompt when the generator returns an empty message or `null`.

`keys --list` prints shell and Yazi shortcuts.
`keys nvim --list` reads mappings from Neovim and can start its configured plugins.
Neovim needs version 0.12 or later.
Its health report names missing language servers and editor dependencies.

Interactive Zsh maps `vim` to Neovim when `nvim` is on your path.
The editor uses the Neon Arcade colors from Rex and Ghostty. Space is the leader in Normal mode.

| Shortcut | Action |
| --- | --- |
| `Space 1` | Show or hide the file tree on the left. |
| `Space 2` | Show or hide the ACP chat. Reopen it to continue the conversation. |
| `Space c p` | Choose an installed ACP provider for a new conversation. |
| `Space a` | Ask AI a one-shot question. |
| `Space g i` / `Space g p` | Browse GitHub issues or pull requests with Octo. |
| `Space t` | Show or hide the agent terminal. |
| `Space f` | Find a file by fuzzy name. |
| `Space /` | Search file contents. |
| `Space p` | Search editor actions by name or shortcut. Each row shows both. |
| `Space ?` | Browse key bindings. |

In the action palette, type `sidebar` or `rename` to filter the list. Use the arrow keys to move one row.
Use Page Up and Page Down to browse a page at a time. Enter runs the selected action. Esc returns to the editor.

The ACP chat uses agentic.nvim with the GitHub Copilot CLI by default. Install the CLI and sign in with `copilot login`.
In the prompt, press `Ctrl-s` to send. The chat renders Markdown and displays tool permission requests.
To use another ACP backend, install its adapter and select **Choose ACP chat provider** in the action palette.
For Codex, install the separate adapter with `brew install codex-acp`. Press `Space c p` and select `codex-acp`.

The separate agent terminal defaults to `codex`. Set `NVIM_AGENT` to another interactive executable, such as `pi`, to change it.
In the terminal, press `Ctrl-\` then `Ctrl-n` to return to Normal mode before a leader shortcut.

Octo uses your authenticated GitHub CLI account. Open an issue or pull request from the list,
or use `:Octo <GitHub URL>`. Press `Space a` in the Octo buffer to ask about it.
Submitting sends the buffer name and text, including unsaved edits, with your question.
The answer opens in the AI pane. Use Octo’s own editing commands to post to GitHub.

For a single question, choose **Ask AI (one-shot)** from the action palette. It uses `ai` on your path.
Ctrl-J adds a line. Enter sends the question and displays the Markdown answer.
The pane shows the provider and request status. In Normal mode, `Space a` hides or reopens it, and `q` dismisses it.
`AI_PROVIDER` selects `codex`, `claude`, or `copilot` for `ai`.
To use another backend, set `NVIM_ASK_COMMAND` to an executable name or path.
It receives one question on stdin. On success it writes Markdown to stdout. On failure it returns a nonzero exit code and writes to stderr.

Starship shows the branch, upstream, sync state, file counts, worktree, and cached PR using local Git reads. If Git status is slow, it falls back to the branch or detached commit and marks the status unavailable. An incomplete untracked scan shows `?unknown`.

In a linked worktree, a visible directory such as `feature-search` stands for the branch `feature/search`. If Starship truncates that directory, the branch appears again. The worktree count and lock state stay visible. The prompt shows PR status when the cache or Worktrunk supplies it.

`→ origin//` means the upstream on `origin` has the same name as the local branch. Other upstreams display their full name.

The first prompt starts a background `wt list statusline --format=json` refresh. Later prompts can add working line counts, divergence and changed lines against the default branch, and the latest reported CI state. For example, `synced` describes the upstream, while `vs origin/main: ↑1 ↓61` describes a separate comparison. A bare `#` from Worktrunk only becomes a PR label if Worktrunk supplies a PR number.

Worktrunk gets four seconds in the background. The prompt reuses a snapshot for the same checkout, branch, and commit across the current and previous 30-second intervals. Missing, invalid, or expired data leaves the local Git labels visible.

The standalone `shell-prompt` command remains available for explicit queries.
Starship and Worktrunk use the terminal's ANSI palette. In Rex, both follow the selected Rex theme.
`shell-prompt context --json` reports repository facts without a network request.
`shell-prompt refresh-pr` explicitly refreshes PR data through GitHub CLI.
The helper needs Node and Git. The refresh operation also needs authenticated `gh`.

### Customize the Git status line

Run `shell-prompt customize` to see the active segments in display order.
To preview a layout, describe the change. The customizer sends your description, active layout, and available segments to `ai`.

```sh
shell-prompt customize --ask 'Show the branch first, then file changes, then the pull request'
# Example response: ["branch","changes","pr"]
shell-prompt customize --apply '["branch","changes","pr"]'
```

The next Starship prompt uses the saved order. Omit a segment to hide it.
`working` shows changed line counts. `details` shows the default-branch comparison and CI status.
Use `shell-prompt customize --help` for the full list in default order.
The customizer saves the layout under `${XDG_CONFIG_HOME:-$HOME/.config}/shell-prompt/statusline.json`. Remove that file to restore the default.
Only `--ask` calls an AI provider. To use Claude for one suggestion, prefix the command with `AI_PROVIDER=claude`.

### Call an AI provider from a CLI

`ai` reads a quoted prompt or reads standard input when you omit the argument.
It runs `codex exec` by default. Install and authenticate the native CLI for each provider you use.
Set `AI_PROVIDER` to `codex`, `copilot`, or `claude` to select a default. The `--provider` flag takes precedence.

```sh
ai 'Suggest a short label for untracked files'
printf '%s\n' 'Suggest a short label for staged changes' | ai --provider copilot
```

Plain `ai` requests start in a temporary directory. A successful request prints the answer to stdout.
A provider failure reports its exit status on stderr. A missing executable exits with 127, and a 120-second timeout exits with 124.

#### Choose the provider, model, effort, and flags

Set defaults for both `ai` and `$A` in
`${XDG_CONFIG_HOME:-$HOME/.config}/dotfiles/config.toml`. Use a separate
table for each provider so switching providers selects its model and flags.
The installer starts with Codex, three recent commands, and empty flags for each provider.
Model and effort default to the native CLI. The following example customizes those settings.

```toml
[ai]
provider = "codex"
recent = 3

[ai.codex]
effort = "low"
flags = ["-c", "model_verbosity='low'"]

[ai.claude]
model = "sonnet"
effort = "medium"

[ai.copilot]
model = "auto"
```

`AI_PROVIDER`, `AI_MODEL`, `AI_EFFORT`, `AI_FLAGS`, and `AI_ASK_RECENT`
override the corresponding file settings. An explicit `ai --provider`
takes precedence over `AI_PROVIDER`. Omit model or effort to use the native
CLI's default. Use model names and effort levels supported by that provider.
With Copilot's `auto` model, leave effort unset.

```zsh
git diff | AI_PROVIDER=claude AI_MODEL=sonnet AI_EFFORT=low $A 'summarize'
AI_FLAGS='["-c","model_verbosity=\"low\""]' AI_PROVIDER=codex ai 'Suggest a label'
```

`AI_FLAGS` replaces the selected provider's entire `flags` array. Each string
is one native CLI argument. Use `[]` to clear the file's flags for one call.
For bare `$A` inside another command's arguments, export the overrides
before running that command.

### Use AI in an interactive Zsh command

Use bare `$A` wherever you want a generated argument or a text filter. At the
start of a command or pipeline stage, it accepts an optional instruction and
reads piped text. Each stage writes its answer to the next stage.

```zsh
git diff | $A 'isolate changes to Kotlin interfaces under src' | $A 'render the diff'
git status --short | $A
$A 'what does the last error mean?'
git commit -m $A
```

In argument position, Zsh passes the answer as one literal value, including
spaces and newlines. For `git commit -m $A`, the request includes the staged
diff. Use `git commit -e -m $A` to edit the generated subject before committing.
To give an argument its own instruction, use ordinary command substitution,
such as `git commit -m "$($A 'write a subject for the staged changes')"`.
Write `'$A'` to pass the token literally.

`$A` starts the provider in the working directory and supplies the original
command line. By default it sends up to three completed commands from the
current Atuin session, their exit codes, and the last 40 lines of available
output (up to 4,096 characters per command). Set `AI_ASK_RECENT` to a number
from 0 to 20 to change the count. Zero skips history access. Missing history
or captured output leaves the other context available.

Atuin records output when its daemon, PTY proxy, and output capture are enabled.
To opt in on a machine with shell history enabled, run
`atuin setup --only --output-capture --daemon` and start a new shell.
See [Atuin output capture](https://docs.atuin.sh/main/guide/output-capture/) for
storage, retention, and exclusion settings.

`~/.pi/agent` holds Pi configuration, public instructions, agents, prompts, and LSP settings.
Use [Pi setup](pi.md) for the public inventory and Kast registration.

Use `nvim '+checkhealth editor'` for editor diagnostics.

Setup accepts exact version strings and tables with `version`, `asset_pattern`, and `bin_path`.
Table values must be nonempty strings, and `version` must contain an exact pin.
Unsupported table options fail before provider commands.
The selected mise configuration keeps the table options during installation.
