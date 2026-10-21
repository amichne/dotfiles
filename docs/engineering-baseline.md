# Install the engineering baseline

Dotfiles owns the short B0 source under `.config/agent-engineering`.
Slopsentral owns the selected validators and optional skills.
The installer adds a visible B0 block to native instruction files.
It keeps all text outside that block and leaves Pi append instructions intact.

## Review the local source update

HOME is the live dotfiles worktree. Run `df setup plan --json` first.
Keep dirty files and existing feature commits.
Prepare and test any merge conflicts in an isolated checkout.
Use a fast-forward update only after the integration commit includes the live branch.
Do not force checkout private files or replace an existing branch.

Native consumer files are private, outside the public Git inventory:

- `~/.codex/AGENTS.md`
- `~/.codex/hooks.json`
- `~/.pi/agent/AGENTS.md`
- `~/.pi/agent/extensions/engineering-checks.ts`

Their public sources are B0 and the two templates in `.config/agent-engineering`.
`scripts/sync_agent_baseline.py --check` checks those public sources.
It no longer replaces private instruction files.

## Plan and apply

Select existing local validators. Installed plugin resources are valid inputs.
The current restored Slopsentral schema and policy must match their selected owner.
The command never enrolls plugins or downloads a Pi distribution.

```sh
agent-check install \
  --kotlin /path/to/kotlin-horizontalization-check \
  --assessment /path/to/controlled-technical-writing/scripts/assess_text.py \
  --vale /path/to/vale
```

The JSON plan lists changed paths and hashes, without private instruction text.
Copy its `planId` into the same command with these extra flags:

```sh
--apply --expected-plan PLAN_ID
```

A changed target, source, or selected tool invalidates the plan.
The installer backs up existing files before its first resource write.
It records the backup manifest and receipt under
`$XDG_STATE_HOME/agent-engineering`, or `~/.local/state/agent-engineering`.
Each file replacement is atomic. A partial application reports its changed paths.
Review a fresh plan before retrying an interrupted update.

Repeated installation keeps one B0 block and one definition for each owned hook.
Unrelated hooks keep their order and content.
An unknown Pi check extension, symlink, malformed block, or modified owned hook
stops the plan before resource writes.
Settings, models, authentication, trust hashes, and other extensions stay untouched.

## Check native selection and trust

```sh
agent-check inspect
```

The report shows block hashes, overrides, source matches, and selected tools.
Use a fresh Pi session and Codex `debug prompt-input` for effective selection.
The qualified native fixtures find one B0 occurrence while retaining prior instructions.
Explicit overrides, custom homes, or native instruction budgets can suppress it.

The Codex definitions need native hook review.
Use App Server `hooks/list` to inspect their identities, hashes, and trust state.
The installer does not grant trust or edit `config.toml`.
Untrusted or disabled hooks do not establish an automatic check.
Use the explicit handoff command until native hook approval is complete.

Pi 1.3.0 awaits checks at `turn_end` and `agent_before_settle`.
These events cannot veto settlement.
Codex 0.163.0 runs `Stop` after the final assistant text.
A failed hook can report `stopped` while the CLI still exits zero.
Already emitted text remains visible.
The explicit handoff exit status is the validation gate.

## Current prose contract

The restored v1 assessor checks a repository glossary as well as prose.
The adapter prefers `glossary.json` or `docs/glossary.json` over a Markdown reader view.
Without JSON, it checks `GLOSSARY.md` or `docs/GLOSSARY.md`.
Multiple sources of the same form are ambiguous and fail selection.
The glossary path and bytes bind each prose receipt and its cache.

Without a glossary, the real assessor still measures prose.
It returns `INCOMPLETE` with exit 2; the adapter preserves that non-passing result.
It never invents glossary terms to make a check pass.
The earlier pinned v2 report shape remains readable for existing explicit selections.
No superseded distribution is installed by this support.

Both report shapes must pass their exact owner schema, selected-document hashes,
engine version, policy digest, and exit/findings checks.
Malformed output, missing tools, incomplete coverage, and failed inputs cannot pass.
The existing Kotlin layout findings remain advisory.

## Run explicit checks

```sh
agent-check turn --repo /path/to/project --session review-1 --file README.md
agent-check handoff --repo /path/to/project --session review-1 --file src/main/kotlin/example/Thing.kt
agent-check status --repo /path/to/project --session review-1
```

Repeat `--file` to select more files.
Each path must name a Kotlin or prose file inside the selected working directory.
The command rejects symlinks, parent traversal, directories, and unsupported file types.
A deleted Kotlin file still selects its surviving package peers and ancestors.
The layout checker remains advisory.

The first explicit selection needs no `begin` command.
Later calls keep that session's explicit selections.
The adapter never discovers a repository, invokes Git, reads its index, or scans its file inventory.
Commits and ignore rules do not change the selection.
Files without an explicit selection remain outside assessment.
The Kotlin heuristic still examines package names near a selected Kotlin file.
The prose assessor still reads the selected repository glossary.

Receipts bind selected file bytes, tool identity, glossary bytes, and Kotlin package names.
An input change during assessment prevents a reusable success receipt.
Unchanged results, including failures, stay cached.
Use `--retry` for an explicit repeat.
Concurrent calls fail without a scope reset.

Native events reuse the explicit selection for the same working directory and session ID.
Without a selection, they report `not-applicable` with `no-explicit-files`.
That result supplies no assessment evidence.
The Codex adapter also accepts repeated `--file` arguments in a reviewed hook command.
The Pi adapter keeps its existing event contracts and registers no file-selection tool.
Native adapters do not infer changed paths from shell commands or model text.

Old Git snapshot files remain private historical data.
The adapter uses `selection.json` and never reads the old session baseline.
A fresh native session needs a new explicit selection.
