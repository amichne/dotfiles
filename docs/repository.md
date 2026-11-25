# Repository instructions

Edit the ordinary checkout of `amichne/dotfiles` with Git. The checkout installer connects HOME destinations to the source. Run tests from the checkout with disposable HOME directories.

## Owners

- `AGENTS.md` owns the user-scoped instructions. `~/.codex/AGENTS.md` and
  `~/.claude/CLAUDE.md` are private symlinks to `~/AGENTS.md`.
- `docs/` holds the guides. Put maintenance commands in `scripts/` and their tests in `tests/`.
  The root `Dockerfile` defines the disposable test environment.
- `.gitignore` owns the default-deny public inventory.
- `.zshenv`, `.zshrc`, and `.zprofile` own shell exports and startup;
  `.config/zsh/functions` owns the autoloaded functions.
- `Brewfile` owns the core Homebrew tools. `Brewfile.development` lists optional developer tools.
  `.config/mise/config.toml` pins the JDK and Kotlin compiler. `.local/bin/setup-tools` previews and installs the core inventory.
- `.local/bin/keys` owns the shortcut browser; `.config/shell-prompt` owns Git
  prompt context.
- `.local/bin/dotfiles` runs worktree reclaim from the checkout.
- Root `install.sh` starts the ordinary-checkout setup. The manifest in
  `scripts/layered.py` owns the three Zsh hooks, Git include, Starship and Neovim links, and Ghostty theme selection.
- `scripts/install.py` previews and applies the layer and its removal.
  `migration.py` converts the supported legacy HOME revision.
- `.pi` contains public Pi resources. `amichne/ayi` owns the AI commands.
  Slopsentral owns development standards, validators, and skills.
- Private instructions, hooks, credentials, sessions, and
  `.dotfiles/controlled-english.md` stay outside the tracked inventory.

## Change workflow

1. Examine `git status` and preserve unrelated changes.
2. Stage each intended path. A new public path must match the inventory in `.gitignore`.
3. Review the staged diff before committing.

## Rules

Keep configuration data inert. Parse external values once into constrained
values. Keep expected failures finite and preserve native command failures. Do
not bypass type analysis, data parsing, dependency errors, or shell lint. Shell
startup must not access the network, install software, prompt, or export
credentials; a missing dependency produces a named failure. Load only the two
named system Zsh packages from reviewed physical package roots.

## Checks

Tests use disposable HOME and XDG directories without host credentials; never
replace live HOME files from a test. Run `scripts/check.sh` for Ruff,
strict Pyright, pytest, shell syntax, ShellCheck, Node tests, data parsing, and
the documentation build. Each portable Python command needs its adjacent uv lock.

Do not install, publish, or change remotes without explicit authorization.
