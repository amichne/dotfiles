# Public source and enterprise integration

Dotfiles owns the current portable source.
An enterprise repository can use shared public ancestry and explicit private-owned files.
Unrelated history stops integration until a separately reviewed import supplies the missing ancestry.

The current dotfiles parser owns typed profile resolution through config/schema.tsv.
Trusted external roots own declared enterprise plugins.
An integration planner must preserve these owners and per-value provenance.
Private credentials remain references to command-scoped providers.

## Retained proof and proposed product

The [Git proof](../../tests/upstream-plan/standalone.py) starts public and enterprise fixtures from one pinned dotfiles commit.
It proves a public addition, exact conflict blobs, and destination preservation.
Its private profile is inert data. Byte preservation does not prove effective configuration precedence.

No production upstream planner or apply command enters this change.
The earlier Config proposal remains in the source archive.
Its proposed outcomes remain design requirements, separate from executed proof.

The next planner needs these facts before it can return an executable plan:

- One selected authority with a known worktree, Git identity, and index digest.
- Exact public and enterprise commits with one shared merge base.
- An admitted path inventory with explicit ownership and supported file kinds.
- A schema-backed profile result with its source provenance.
- Bound preimages and source identities for later drift rejection.

Expected failures must distinguish missing or competing authority, unrelated or ambiguous history, private-path conflicts, index drift, stale source, and unsafe paths.
Missing composition or failed effects cannot become an empty successful plan.
The supported update interface must not contain a publication operation.

## Effect limits

Fetch can change object and ref metadata.
The Git merge probe can create objects without changing the index or HOME files.
The planner must state those effects.
An offline mode must use existing objects and perform no network request.

A later apply operation needs interruption, drift, collision, and guarded recovery cases before live use.
Public export must use an isolated public revision and an explicit portable-path inventory.
It must not derive a public artifact by filtering a private enterprise checkout.
