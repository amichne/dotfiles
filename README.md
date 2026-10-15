# Dotfiles

Personal shell, editor, prompt, and Pi configuration for `amichne/dotfiles`.
Each file uses its HOME-relative path.
A bare repository at `~/.dotfiles.git` tracks HOME directly.
No second configuration tree or runtime copy exists.

The source contains:

- `.zshrc` and `.zprofile` for Zsh startup.
- `.config/` for Atuin, mise, Neovim, Starship, Yazi, and the shell helpers.
- `.local/bin/keys` and `.local/bin/shell-prompt` for shortcuts and Git prompt context.
- `.pi/` for public Pi instructions, agents, prompts, and LSP settings.
- `ai/` and `bin/ai` for the current AI commands.
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

The shell manager exposes one operation:

```sh
dotfiles ai plan
dotfiles ai apply
dotfiles ai uninstall
```

Use `ai list`, `ai inspect ci`, `ai run review <pr>`, and `ai run ci <pr>` for AI workflows.
Use `ai create "<description>"` to draft and review a new command before local registration.

Read [HOME setup](docs/home.md), [configuration](docs/configuration.md), and [AI commands](docs/ai-commands.md).
The [source instructions](AGENTS.md) define ownership and the local gate:

```sh
./scripts/check.sh
```

Credentials, sessions, caches, and machine overrides stay outside the public inventory.
The source does not contain a Git identity or SSH signing key.
