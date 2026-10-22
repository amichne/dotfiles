# Dotfiles

Shell, editor, prompt, and Pi setup for `amichne/dotfiles`.
Each file uses its HOME-relative path.
A bare repository at `~/.dotfiles.git` tracks HOME directly.

The source contains:

- `.zshrc` and `.zprofile` for Zsh startup.
- `.config/` for Atuin, mise, Neovim, Starship, Yazi, and the shell helpers.
- `.local/bin/keys` and `.local/bin/shell-prompt` for shortcuts and Git prompt context.
- `.pi/agent/` for public Pi resources and the `/deepen` prompt rewrite command.
- `scripts/df.py` and `.local/bin/df` for selected HOME files in Git.
- `scripts/install.py` for reviewed installation and updates with private recovery copies.

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

Use the [HOME installer](docs/home.md#install-or-update-home) to apply a reviewed revision.
It includes the latest stable Slopsentral release for Pi by default.
Read [configuration](docs/configuration.md), [Pi setup](docs/pi.md), and [Ayi commands](docs/ayi-commands.md).
Read [disposable containers](docs/testing.md) for the same isolated gate on local and cloud Docker workers.
The [source instructions](docs/repository-instructions.md) define ownership and the local gate:

```sh
./scripts/check.sh
```

Credentials, sessions, caches, and machine overrides stay outside the public inventory.
The source does not contain a Git identity or SSH signing key.

The short global [engineering baseline B0](.config/agent-engineering/B0.md) defines
common rules. Read the [baseline guide](docs/engineering-baseline.md) for its scope.
[Slopsentral](https://github.com/amichne/slopsentral) owns the detailed skills and validators.
