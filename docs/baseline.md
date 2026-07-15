# Baseline evidence

This repository starts from the checked-in Apollo and Artemis implementations
at `/Users/amichne/code/apollo`, their Git history, the live shell wiring, and a
sanitized aggregate of actual CLI history. The Apollo checkout is evidence
only: it has unrelated user changes and is not modified by this project.

## Current state

- The live Zsh session sources Apollo and Artemis in sequence. Both own parts
  of the same namespace.
- Login-shell startup is approximately 0.9 seconds on the current machine.
- `PATH` contains 39 entries, including 10 duplicates.
- The loaded shell has 289 aliases and 1,570 functions. Source order and name
  collisions are therefore part of the compatibility risk.
- The live startup exports a GitHub token to every child process, hard-codes
  Homebrew and SDKMAN paths, and repeats some tool initialization across startup
  files.
- Apollo's setup copies broad configuration trees into active locations.
  Artemis has the safer atomic, marker-owned installer, but running it does not
  remove Apollo's startup block.

## Actual CLI shape

The sanitized usage sample contains 1,288 Atuin records and 1,056 Zsh history
records over roughly five weeks. It intentionally excludes arguments, raw
directories, hosts, identities, URLs, and credential values.

- Usage is overwhelmingly direct: 1,273 of 1,288 Atuin records contain one
  command stage.
- The dominant tools are `kast`, `codex`, `brew`, `intelligence`, Git/Gradle,
  GitHub CLI, editors, and shell discovery commands.
- `--help` appears 113 times. Discoverable help, completions, and useful typo
  errors are product behavior, not decoration.
- Established short commands include `l`, `main`, `push`, `commit`, and `zs`.
- Atuin owns interactive history search, while native Zsh history settings
  remain meaningful fallback behavior.
- Work is concentrated in a small set of code workspaces; directory navigation
  and repository-root helpers matter more than elaborate pipelines.

## Historical signal

Apollo's shell behavior persisted while its management layer churned:

1. managed Zsh entrypoint and proxy-aware setup;
2. a large profile/config/menu CLI;
3. a one-day adoption of chezmoi;
4. return to copied configuration;
5. removal of much of the profile UI;
6. Artemis added beside Apollo as a strict replacement kernel.

The lesson is to stabilize behavior, ownership, and configuration contracts
before selecting or expanding a dotfile deployment engine.

## Verified strengths

From Apollo:

- familiar interactive helpers;
- process overrides above machine-profile defaults;
- asset/provider dry-runs and managed ownership;
- extension channels, allowlisted manifests, and trusted-root checks.

From Artemis:

- registry-backed flags;
- fail-fast checks for explicitly enabled behavior;
- atomic same-directory writes;
- an idempotent managed startup block;
- `status` and `doctor` surfaces;
- tests using disposable homes.

The checked-in Apollo asset, extension, parity, and Artemis suites pass from a
clean archive on the current machine. The parity harness depends on login-shell
path behavior and needs replacement with stricter controlled fixtures before it
is used as proof for the new implementation.

## Verified risks to remove

- Apollo setup can overwrite the machine profile while claiming to preserve it.
- A fresh Artemis profile enables paths that need not exist, so `doctor` can
  fail immediately after setup.
- Artemis profile values override explicit process values.
- Proxy startup can prompt and can place credentials in globally inherited
  environment variables.
- Active GitHub host state, Jira configuration, identities, and enterprise
  metadata are mixed with portable tracked config.
- Startup performs work that belongs in explicit sync or doctor commands.
- Several familiar helpers override broad commands with unsafe behavior:
  `commit` stages everything, `rebase` bypasses hooks, `squash` resets, and
  skip-worktree helpers are easy to misuse.
- Remote installers are unpinned and one failure is ignored.
