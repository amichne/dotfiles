# Dotfiles

Personal shell, editor, prompt, and Pi configuration for `amichne/dotfiles`.
Each file uses its HOME-relative path.
A bare repository at `~/.dotfiles.git` tracks HOME directly.

The source contains:

- `.zshrc` and `.zprofile` for Zsh startup.
- `.config/` for Atuin, mise, Neovim, Starship, Yazi, and the shell helpers.
- `.local/bin/keys` and `.local/bin/shell-prompt` for shortcuts and Git prompt context.
- `.pi/agent/` for public Pi instructions, agents, prompts, and LSP settings.
- `scripts/df.py` and `.local/bin/df` for selected HOME files in Git.

Use `df` for the bare repository:

```sh
df status
df diff
df add .config/starship.toml
df diff --cached
df commit -m "Adjust prompt"
df git log --oneline
df setup plan
```

`df add` needs named paths. It rejects HOME itself, Git metadata, and paths outside HOME.
`df git` passes explicit arguments to native Git.
Git controls commit identity, hooks, and signatures.
Ordinary `git` keeps its normal behavior in project directories.

The separate public repository [Ayi](https://github.com/amichne/ayi) owns the `ayi` commands and their installer.

Read [HOME setup](docs/home.md), [configuration](docs/configuration.md), [Pi setup](docs/pi.md), and [Ayi commands](docs/ayi-commands.md).
Read [disposable containers](docs/testing.md) for the same isolated gate on local and cloud Docker workers.
The [source instructions](AGENTS.md) define ownership and the local gate:

```sh
./scripts/check.sh
```

Credentials, sessions, caches, and machine overrides stay outside the public inventory.
The source does not contain a Git identity or SSH signing key.

The [engineering baseline B0](.config/agent-engineering/B0.md) owns the short global
engineering instructions. `scripts/sync_agent_baseline.py` projects it into native
Codex and Pi instruction files. Detailed skills remain in
[Slopsentral](https://slopsentral.michne.com/guides/pi).
