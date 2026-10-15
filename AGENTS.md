# Repository instructions

HOME is the installed worktree. `~/.dotfiles.git` holds its sole Git index.
The origin is `amichne/dotfiles`.
Keep configuration at its HOME-relative path. Do not create another runtime copy.

- `.gitignore` owns the default-deny public inventory.
- `.zshrc` and `.zprofile` own shell startup.
- `.config/zsh/functions` owns the autoloaded shell functions.
- `.local/bin/keys` owns the shortcut browser.
- `.config/shell-prompt` owns Git prompt context and its pure model.
- `scripts/df.py` owns bare Git selection and read-only setup inspection.
- `amichne/ayi` owns the separate AI commands and their installer.
- `.pi` contains public Pi resources. Keep authentication and sessions private.

Keep configuration data inert. Parse external values once into constrained values.
Keep expected failures finite. Preserve native command failures.
Do not bypass type analysis, data parsing, dependency errors, or shell lint.
Shell startup must not access the network, install software, prompt, or export credentials.
Missing shell dependencies must produce a named failure.
Load only the two named system Zsh packages from reviewed physical package roots.
Keep private settings outside the public inventory.

Tests use disposable HOME and XDG directories without host credentials.
Never replace live HOME files from a test.
Use `./scripts/check.sh` for Ruff, strict Pyright, pytest, shell syntax, ShellCheck,
Node tests, data parsing, and the documentation build.
Each portable Python command needs its adjacent uv lock.

Do not install, publish, or change remotes without explicit authorization.
