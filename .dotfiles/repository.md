# Repository instructions

For the installed configuration, HOME is the worktree and `~/.dotfiles.git`
holds its sole Git index. Verify the actual Git directory, worktree, origin,
revision, and tracked-only status before editing; the expected origin is
`amichne/dotfiles`. Keep configuration at its HOME-relative path and do not
create another runtime copy. For source review or patch preparation, use the
verified source checkout; a missing installed HOME does not block that work.

## Owners

- `AGENTS.md` owns the user-scoped instructions. `~/.codex/AGENTS.md` and
  `~/.claude/CLAUDE.md` are private symlinks to `~/AGENTS.md`; keep its home
  dotfiles section self-gating so it stays inert for unrelated work.
- `.dotfiles/` owns support files: this guide, `writing.md`, the documentation
  site, scripts, tests, the container, and the Python project. Keep repository
  support out of the HOME root so tools and agents never walk HOME to find it.
- `.gitignore` owns the default-deny public inventory.
- `.zshenv`, `.zshrc`, and `.zprofile` own shell exports and startup;
  `.config/zsh/functions` owns the autoloaded functions.
- `.config/mise/config.toml` owns tool pins, the Brew inventory, and setup tasks;
  `.local/bin/setup-tools` owns preview and per-item installation.
- `.local/bin/keys` owns the shortcut browser; `.config/shell-prompt` owns Git
  prompt context.
- `.dotfiles/scripts/df.py` owns bare Git selection and read-only inspection;
  `.local/bin/dotfiles` is its launcher.
- Root `install.sh` starts the ordinary-checkout setup. The manifest in
  `.dotfiles/scripts/layered.py` owns the three Zsh hooks, Git include, and Starship link.
- `.dotfiles/scripts/install.py` owns reviewed HOME installation, fast-forward
  updates, and the latest Slopsentral setup. Keep its plans read-only and its
  recovery copies private.
- `.pi` contains public Pi resources. `amichne/ayi` owns the AI commands.
  Slopsentral owns development standards, validators, and skills.
- Private instructions, hooks, credentials, sessions, and
  `.dotfiles/controlled-english.md` stay outside the tracked inventory.

## Change workflow

1. Run tracked-only status (`dotfiles status`) and examine unmerged paths.
   Do not scan HOME for untracked files; examine one only by its exact path.
2. Preserve unrelated changes. Never stage all of HOME or unrelated edits in
   `~/.zshrc`.
3. Stage tracked changes with `dotfiles add <path>` and each new path explicitly;
   a new path also needs its `.gitignore` allowlist entry.
4. Examine the staged paths and the staged diff before committing.

## Rules

Keep configuration data inert. Parse external values once into constrained
values. Keep expected failures finite and preserve native command failures. Do
not bypass type analysis, data parsing, dependency errors, or shell lint. Shell
startup must not access the network, install software, prompt, or export
credentials; a missing dependency produces a named failure. Load only the two
named system Zsh packages from reviewed physical package roots.

## Checks

Tests use disposable HOME and XDG directories without host credentials; never
replace live HOME files from a test. Run `.dotfiles/scripts/check.sh` for Ruff,
strict Pyright, pytest, shell syntax, ShellCheck, Node tests, data parsing, and
the documentation build. Each portable Python command needs its adjacent uv lock.

Do not install, publish, or change remotes without explicit authorization.
