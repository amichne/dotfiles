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
