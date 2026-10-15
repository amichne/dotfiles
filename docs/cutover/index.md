# Dotfiles consolidation and clean-slate cutover

The amichne/dotfiles repository owns both the AI shell MVP and the replacement work.
The replacement change now uses the same repository and sits after the AI change.
Config PR #16 supplies historical source. It no longer owns the active cutover plan.

## Source identities

| Source | Revision | Role |
| --- | --- | --- |
| Dotfiles AI MVP | 259c8da0f7be839f05b684a5dcc8449152d2e233 | Parent change |
| Dotfiles main baseline | 6765d34a572b94f76592ef9dd0b0cdb5c9baac2b | Fixture baseline that survives a squash merge |
| Config cutover change | 1cbcb524a2a1723e3de9ed57635874b6b4a781ed | Imported plan and proof source |
| Config baseline | 2dd7998b973735353b9099ea23d9098c5a6ce239 | Original proof baseline |
| Installed HOME authority | e26318c5ce4be2d0b3f0895cf8150688282370cf | Existing installation, separate from either source checkout |

The [source record](source/provenance.json) records the complete original path list and archive hashes.
The [compressed patch](source/config-pr16.patch.gz) keeps all 17 original changed paths.
It includes the old documents, reports, locked proof, ignore admissions, and Python-helper fixture repair.
To inspect the original change without applying it, use:

~~~sh
gzip -dc docs/cutover/source/config-pr16.patch.gz
~~~

The legacy fixture repair remains historical because dotfiles has no matching configure.py fixture.
The active proof uses the dotfiles tree and its existing public paths.
The imported ignore admissions do not enter this repository's ignore policy.

## Current ownership

The root config/schema.tsv remains the shell configuration authority.
The existing installer owns its marked Zsh entrypoint.
The AI dispatcher, mise registry, prompts, and workflow implementation remain under their existing owners.
No Config runtime, management dispatcher, or alternate configuration parser enters this change.

The current host still selects ~/.cfg/repo.git with HOME as its worktree.
Its launcher uses ~/.cfg/shell. Older metadata also exists at ~/.local/share/config/repo.git.
Both native Pi and Codex directories stay in HOME.
These facts describe the inspected host. They do not grant a fixture access to that host.

## Cutover contract

The final result has one selected dotfiles source and one active shell entrypoint.
Old startup files and replaced command targets belong in a recovery archive.
They must stop acting as active owners after cutover.
Credentials, sessions, history, machine overrides, and unrelated files stay outside the source and replacement inventory.

A clean slate does not delete Git history or private application state.
The [cutover procedure](procedure.md) separates source consolidation, a disposable rehearsal, and the live transition.
Repository publication does not prove that the host transition occurred.

## Executable evidence

From the repository root, run:

~~~sh
uv run --locked --project tests/upstream-plan ruff format --check tests/upstream-plan
uv run --locked --project tests/upstream-plan ruff check tests/upstream-plan
uv run --locked --project tests/upstream-plan pyright --project tests/upstream-plan/pyproject.toml
uv run --locked --project tests/upstream-plan pytest tests/upstream-plan -q -s -p no:cacheprovider
uv run --locked --script tests/upstream-plan/standalone.py --self-test
~~~

The proof supplies a clean public addition and a conflict with exact base, enterprise, and public blobs.
It also compares HEAD, refs, index bytes, modes, symlinks, and unrelated staged and unstaged files.
Private sentinels belong to the disposable fixture.
Git metadata can change through fetch and object creation. The proof does not call that a read-only filesystem operation.

The archive case examines hashes and the original path inventory without applying the patch.
These cases prove Git behavior and source preservation.
They do not prove profile precedence, a production upstream planner, runtime replacement, or installed-host parity.

## Remaining implementation

The [upstream proposal](upstream.md) keeps enterprise decisions separate from portable source.
The current dotfiles schema and trusted plugin roots remain the composition owners.
New work must extend those owners instead of importing Config's independent runtime.

Live cutover needs a reviewed replacement inventory, exact preimages, guarded recovery, and fresh-shell acceptance.
The existing installer refuses the conflicting AI targets on this host.
It does not yet archive those targets or retire the unmarked .cfg startup files.
The marked-block installer alone cannot establish a clean-slate cutover.
