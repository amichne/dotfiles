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

The shell loads `f`, `rr`, and `y` from `.config/zsh/functions`.
They search with ripgrep, enter the Git root, and return the selected Yazi directory.
`zs` starts a fresh login shell. Ctrl-W deletes identifier parts and path parts.
Ctrl-X ? opens `keys`. Ctrl-R uses Atuin history.

`keys --list` prints shell and Yazi shortcuts.
`keys nvim --list` reads mappings from Neovim and can start its configured plugins.
Neovim needs version 0.12 or later.
Its health report names missing language servers and editor dependencies.

Starship uses `.config/starship.toml` and `shell-prompt` for local Git context.
`shell-prompt context --json` reports repository facts without a network request.
`shell-prompt refresh-pr` explicitly refreshes PR data through GitHub CLI.
The helper needs Node and Git. The refresh operation also needs authenticated `gh`.

`.pi` keeps public instructions, agent definitions, a prompt, and LSP settings.
Pi authentication and session data remain private.
The current AI registry lives in `ai/`.
Its optional `.config/ai` link points to that source without another copy.
