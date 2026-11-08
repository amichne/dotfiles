# Configuration

`.zprofile` adds `~/.local/bin` and the mise shims to `PATH`.
`.zshrc` adds interactive history, completion, key bindings, and tool integrations.
It reads an optional `.zshrc.local` before tool initialization.
That file remains private.

Install the tools declared in `.config/mise/config.toml` before shell use.
Review that file before an explicit `mise trust` or `mise install` command.
Shell startup uses offline mise initialization and does not install missing tools.
The system package provider must supply `zsh-autosuggestions` and `zsh-syntax-highlighting`.
`ZSH_PLUGIN_ROOT` can select their reviewed physical package directory.

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
Ctrl-X ? opens `keys`. Ctrl-R uses Atuin history.
Ctrl-T selects files with a bat preview.
Set `FZF_CTRL_T_OPTS` in `.zshrc.local` to customize the file preview.

`keys --list` prints shell and Yazi shortcuts.
`keys nvim --list` reads mappings from Neovim and can start its configured plugins.
Neovim needs version 0.12 or later.
Its health report names missing language servers and editor dependencies.

Starship uses `.config/starship.toml` and `shell-prompt` for local Git context.
`shell-prompt context --json` reports repository facts without a network request.
`shell-prompt refresh-pr` explicitly refreshes PR data through GitHub CLI.
The helper needs Node and Git. The refresh operation also needs authenticated `gh`.

`~/.pi/agent` holds Pi configuration, public instructions, agents, prompts, and LSP settings.
Use [Pi setup](pi.md) for the public inventory and Kast registration.
The separate [Ayi repository](https://github.com/amichne/ayi) owns the AI registry and its optional installed links.
