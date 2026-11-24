# Dotfiles

Install the Zsh setup, Git aliases, and Starship theme from an ordinary checkout.
Git, uv 0.12.9 or later, and Python 3.12 or 3.13 are needed.

```sh
curl -fsSLo install-dotfiles.sh https://raw.githubusercontent.com/amichne/dotfiles/main/install.sh
/bin/sh install-dotfiles.sh --bootstrap
```

The bootstrap obtains the source in `~/dotfiles` and prints a plan.
Review its five destinations. Apply the plan with its printed ID.

```sh
~/dotfiles/install.sh --apply --expected-plan PLAN_ID
```

For an existing development checkout, run `./install.sh` to preview the same installation.
Read [layered setup](../.dotfiles/docs/home.md#install-from-an-ordinary-checkout) for local overrides, prerequisites, recovery, and removal.
Existing bare HOME installations use the [full HOME installer](../.dotfiles/docs/home.md#install-or-update-home).

The source contains:

- `.zshrc` and `.zprofile` for Zsh startup.
- `.config/` for Atuin, mise, Neovim, Starship, Yazi, and the shell helpers.
- `.local/bin/keys` and `.local/bin/shell-prompt` for shortcuts and Git prompt context.
- `.pi/agent/` for public Pi resources and the `/deepen` prompt rewrite command.
- `.dotfiles/scripts/df.py` and `.local/bin/dotfiles` for selected HOME files in Git.
- `.dotfiles/scripts/install.py` for reviewed installation and updates with private recovery copies.

Use `dotfiles` for the bare repository:

```sh
dotfiles status
dotfiles diff
dotfiles add .config/starship.toml
dotfiles diff --cached
dotfiles commit -m "Adjust prompt"
dotfiles git log --oneline
dotfiles setup plan
```

`dotfiles add` needs named paths. It rejects HOME itself, Git metadata, and paths outside HOME.
`dotfiles git` passes explicit arguments to native Git.
Git controls commit identity, hooks, and signatures.
Ordinary `git` keeps its normal behavior in project directories.

The separate public repository [Ayi](https://github.com/amichne/ayi) owns the `ayi` commands and their installer.

Use the [HOME installer](../.dotfiles/docs/home.md#install-or-update-home) to apply a reviewed revision.
It includes the latest stable Slopsentral release for Pi by default.
Preview core tool and Brew installs with `mise run setup:plan`; use `mise run setup`
for best-effort installation or `mise run setup:strict` to require completeness.
Read [configuration](../.dotfiles/docs/configuration.md#install-tools), [Pi setup](../.dotfiles/docs/pi.md), and [Ayi commands](../.dotfiles/docs/ayi-commands.md).
Read [disposable containers](../.dotfiles/docs/testing.md) for the same isolated gate on local and cloud Docker workers.
The [repository instructions](../.dotfiles/repository.md) define ownership and the local gate:

```sh
./.dotfiles/scripts/check.sh
```

Credentials, sessions, caches, and machine overrides stay outside the public inventory.
The source does not contain a Git identity or SSH signing key.

[`AGENTS.md`](../AGENTS.md) is the user-scoped agent guidance; `~/.codex/AGENTS.md`
and `~/.claude/CLAUDE.md` link to it. It routes prose to
[writing preferences](../.dotfiles/writing.md) and software work to
[Slopsentral](https://github.com/amichne/slopsentral), which owns development
standards, detailed procedures, and validators. Repository support lives under
`.dotfiles/` so nothing besides configuration sits at the HOME root.
