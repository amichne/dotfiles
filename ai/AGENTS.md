# AI command source

`mise.toml` owns task discovery. `tasks/` contains ordinary executables.
`create.py` owns draft review, verification, and local Git registration.
When the registry lives in HOME, `create.py` uses `df git` and the bare index.
A normal development checkout uses project-local Git.
`workflows.py` owns GitHub data and local reports. Pi receives evidence with its tools disabled.
`install.py` owns the two installed links. Keep shell startup outside this installer.

From the repository root, run `uv run --locked --project ai python ai/check.py`.
The repository gate is `./scripts/check.sh`.

Keep prompts in `prompts/`. Keep generated task verification in `verification/`.
Keep generated command requirements in `requirements/`. Drafts and reports remain outside Git.
