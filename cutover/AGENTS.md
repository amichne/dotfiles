# Cutover source

`standalone.py` owns inventory admission, source identity, and the apply sequence.
`recovery.py` owns filesystem images, receipts, directory locks, status, and recovery.
Keep recovery compatible with the standard library. It must work without the checkout or uv.

`recovery.PATHS` owns the complete replacement inventory.
Use the normal installer to render the entrypoint.
Use `ai.install.links_for` for the AI link targets.
The configuration parser and plugin manifest remain their existing owners.

Run `uv run --locked --project cutover python cutover/check.py` from the repository root.
Run `uv run --locked --script cutover/standalone.py --self-test` for script isolation.
The repository gate is `./scripts/check.sh`.

Keep dependency locks with their source. Never commit inventories, plans, archives, or host state.
Tests use disposable HOME directories and source checkouts with local Git identities.
