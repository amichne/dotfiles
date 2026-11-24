# Repository Guidelines

## Project structure

The repository mirrors a home directory. Zsh reads its startup files at the root and its functions from `.config/zsh/functions/`. Tool settings live under `.config/`, and user commands live under `.local/bin/`.

The `.dotfiles/` directory holds repository support. Put maintenance scripts in `scripts/`, tests in `tests/`, and documentation pages in `docs/` within that directory. The Dockerfile in `containers/` defines the disposable test environment.

## Development commands

Run these commands from `.dotfiles/` in a source checkout.

- `./scripts/check.sh` runs the repository checks, including Ruff, strict Pyright, pytest, Node tests, shell checks, and the documentation build.
- `uv run --locked pytest -q tests/test_df.py` runs the focused tests for the dotfiles command.
- `uv run --locked zensical serve` starts a local preview of the documentation.

## Code style and tests

Use four spaces for Python indentation and snake_case for functions. Ruff formats Python with a 100-character line target. Keep each portable Python script beside its uv lockfile.

Name pytest modules `test_*.py` and Node test files `*.test.mjs`. Use the disposable HOME fixture in `tests/conftest.py` for shell and installer tests. Cover the expected result and the failure cases that your change affects.

## Commits and pull requests

For the installed HOME, use `dotfiles status` to inspect tracked changes. Add each new public path to the root `.gitignore` allowlist. Stage each intended path explicitly with `dotfiles add <path>`.

Use a short imperative commit subject with a prefix such as `fix:` or `docs:`. In the pull request, describe the behavior or guidance that changed and report the checks you ran.
