# Clean-slate cutover procedure

The destination is amichne/dotfiles. The old Config implementation remains recovery material until the replacement passes.

## Inventory and rehearsal

Bind the replacement to its exact committed tree.
Record the current launcher targets, startup files, selected Git metadata, refs, index digest, and registered worktrees.
Use only named public paths. Do not scan private harness directories.

The inspected host uses .cfg/repo.git, .cfg/shell, .local/bin/cfg, and an older .local/bin/ai.
The current .zshrc loads .cfg/shell functions and completions.
The existing .config/ai is a directory, so the new link installer refuses it.

The replacement inventory must name each startup or command path that it changes.
It must also name the older behaviors that it keeps or retires.
The AI MVP supplies create, list, inspect, run review, and run ci.
It does not supply Config's cfg inspect, Pi shell-edit transaction, work dashboard, or complete Python recovery interface.
Do not label those operations as replaced without a new acceptance decision.

Rehearse the exact inventory in a disposable HOME.
Place sentinel files in the Pi and Codex directories and an unrelated staged entry in a test-owned Git index.
Assert that plan creates no configuration changes.
Assert that drift and conflicting ownership stop apply before writes.
Inject an interruption after each replacement.
Assert that recovery restores exact bytes, modes, symlinks, and unrelated staging.

## Live transition

Archive each approved preimage outside the replacement paths.
Keep an independent recovery entrypoint with the archive.
Reexamine the source identity, ownership, and preimages immediately before each effect.
Stop if a file, index, or Git identity differs from the admitted inventory.

Replace the old startup entrypoint with the dotfiles entrypoint.
Replace the named AI command and registry targets after their preimages enter the archive.
Retire only the old launchers whose replacements pass the selected acceptance.
Keep the current terminal open.

Start a fresh Zsh process.
Examine the selected source, startup status, command discovery, argument forwarding, and local report paths.
Exercise a registered task and its explicit rejection case.
Examine the independent recovery command before retirement of the old runtime.

Do not restart applications as an implicit part of cutover.
Do not delete shared interpreters, credentials, sessions, history, or unrelated HOME paths.

## Retirement and recovery

The old Git metadata can own commits absent from dotfiles.
Its archive must keep refs, index, reflogs, and worktree records.
Changing a remote URL does not import that history or prove that it is obsolete.

Keep recovery source, its interpreter, receipts, and preimages together.
Restore only paths that still match the replacement's recorded postimages.
Reject later edits instead of overwriting them.

After fresh-shell acceptance and recovery pass, remove the retired source from active paths.
Keep the archive outside the active source tree.
Report source consolidation and live cutover as separate outcomes.
