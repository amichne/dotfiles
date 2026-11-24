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
For a clean bare HOME on `main` at `cbe207a`, preview the [migration](../.dotfiles/docs/home.md#migrate-a-bare-home) with `./install.sh --migrate`.

The source contains:

- `.zshrc` and `.zprofile` for Zsh startup.
- `.config/` for Atuin, mise, Neovim, Starship, Yazi, and the shell helpers.
- `.local/bin/keys` and `.local/bin/shell-prompt` for shortcuts and Git prompt context.
- `.pi/agent/` for public Pi resources and the `/deepen` prompt rewrite command.
- `.local/bin/dotfiles` to reclaim worktrees in explicitly named repositories.

Use ordinary Git in the checkout to review, stage, and commit changes.

The separate public repository [Ayi](https://github.com/amichne/ayi) owns the `ayi` commands and their installer.

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
