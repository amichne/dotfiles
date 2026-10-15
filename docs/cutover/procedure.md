# Clean-slate cutover procedure

`dotfiles cutover` replaces an admitted Zsh installation and preserves its exact preimages in a private recovery archive.
Every target needs an explicit HOME path. No command defaults to the caller's HOME.
The source checkout, configuration parser, plugin manifest, and AI installer keep their existing ownership.

## Prepare the source

Keep the selected checkout at a clean commit.
Install the declared dependencies with the explicit setup command:

~~~sh
uv run --locked --script cutover/setup.py
~~~

The public dispatcher uses locked dependencies in offline mode.
Normal shell startup does not invoke the cutover tool.
Mise trust remains a separate prerequisite for AI task execution.
Review the registry before you use the native `mise trust` command.

## Admit the inventory

Use a disposable HOME for the first rehearsal.
Keep the inventory and plan outside the selected source checkout.

~~~sh
./bin/dotfiles cutover inventory --home /absolute/disposable-home > /tmp/inventory.json
~~~

If both legacy Git directories exist, select one with `--legacy-git .cfg/repo.git` or `--legacy-git .local/share/config/repo.git`.
The command rejects registered linked worktrees and symbolic links to Git metadata.
It reads named paths and Git metadata. It does not scan Pi or Codex directories.

The inventory contains all supported targets:

| Paths | Intended result |
| --- | --- |
| `.zshrc` | Complete marked entrypoint from the normal installer |
| `.zshenv`, `.zprofile`, `.zlogin`, `.zlogout` | Archived and retired |
| `.local/bin/ai`, `.config/ai` | Links from the AI installer |
| `.local/bin/dotfiles` | Link to the selected dotfiles command |
| `.local/bin/cfg`, `.local/bin/config` | Archived and retired |
| `.cfg/shell` | Archived and retired |
| `.cfg/repo.git`, `.local/share/config/repo.git` | Archived and retired |

Each entry records its file kind, digest, and declared owner.
Digests bind file bytes, modes, directory entries, and symbolic-link text.
The legacy identity records HEAD, the tree, refs, index bytes, and registered worktrees.

Examine each existing path before you change its owner from `unreviewed` to `legacy-config`.
Use `dotfiles` only for an entry that already matches its intended postimage.
Keep `absent` for absent paths.
An owner outside these choices causes rejection.

Resolve the three legacy feature decisions before you request a plan.
This version accepts explicit `retire` decisions for `cfg-inspect`, `pi-shell-edit`, and `work-dashboard`.
It does not implement those legacy commands.
The new recovery command handles this cutover transaction.
It does not import Config's complete Python recovery interface.

## Examine the plan

~~~sh
./bin/dotfiles cutover plan --inventory /tmp/inventory.json --archive /absolute/recovery/archive > /tmp/plan.json
~~~

Choose a new archive path with an existing physical parent on the same filesystem as the targets.
Keep the archive outside the source and replacement paths.
The replacement parent directories must already exist.

The plan binds the admitted preimages, source commit, Git identity, parent identities, shared Python interpreter, and intended postimages.
It also binds local configuration files and selected plugin files through their existing native owners.
The plan prints the complete replacement text and link destinations.
Planning creates no changes in the target HOME or archive.
The normal installer renders the entrypoint in a temporary staging directory.

Examine the complete plan before apply.
If a bound input changes, create a new inventory and plan.

## Apply and examine the result

Stop other writers to the target paths.
Keep the current terminal open until acceptance and recovery pass.
Do not start another shell during replacement.
The directory lock serializes this tool. Other programs do not obey that lock.

~~~sh
./bin/dotfiles cutover apply --plan /tmp/plan.json
./bin/dotfiles cutover status --archive /absolute/recovery/archive
~~~

Apply reexamines the source and inputs before each replacement.
It creates a private archive with the approved plan, journal, receipt digests, recovery source, and launch command before target replacement.
Native renames preserve the preimages without copying symbolic-link targets.
Git metadata keeps its objects, refs, index, reflogs, and worktree records.

Apply starts a fresh Zsh process with global startup files disabled.
The probe examines the selected runtime and command discovery.
It disables history output before exit.
A failed probe restores the admitted preimages.
The archive keeps the probe's source identity and exit status.

A repeated apply accepts only the same completed plan with unchanged postimages and recovery data.
Source drift, input drift, conflicting ownership, or altered staged payloads stop the operation.
An incomplete archive remains available for recovery.

## Recover independently

~~~sh
/absolute/recovery/archive/recover
~~~

The archived command uses a pinned shared Python interpreter with isolated startup and no site packages.
It does not need uv, Pydantic, the source checkout, or the retired Config runtime.
Keep that Python installation and the archive at their recorded paths.
The archive records the interpreter identity. It does not copy the Python installation.

Recovery examines the complete set of preimages and postimages before its first replacement.
After completed apply, an edited or deleted postimage causes rejection without partial recovery.
During an interrupted operation, recovery admits the recorded transitional file states.
Later content that differs from those states causes rejection.

Recovery moves replacements into the archive and restores the exact preimages.
Unrelated files, configuration, credentials, sessions, history, and Git staging stay outside replacement effects.
Repeated recovery accepts the restored state.
An interrupted recovery can resume through the same archived command.

Handled file errors, Ctrl-C, and SIGTERM trigger an automatic recovery try.
After an abrupt process exit, use the archived command explicitly.
If recovery rejects drift, preserve the archive and examine the named path.
Do not overwrite later edits to force recovery.

## Results and acceptance

Successful inventory and plan commands emit one JSON document.
Apply, status, and recovery emit a JSON status when input parsing and file access succeed.
Input or file errors can leave stdout empty. Diagnostics use stderr.

| Exit | Meaning |
| --- | --- |
| `0` | Successful operation, applied state, or recovered state |
| `2` | Argument usage error or unavailable offline uv environment |
| `8` | Incomplete transaction reported by status |
| `65` | Invalid inventory, plan, or receipt |
| `74` | File operation or lock failure |
| `75` | Rejected precondition or drift |
| `130` | Interrupted operation |

The independent recovery command returns `74` for a receipt error.

From the repository root, run:

~~~sh
uv run --locked --project cutover python cutover/check.py
uv run --locked --script cutover/standalone.py --self-test
./scripts/check.sh
~~~

The cases use disposable HOME directories and real Git, mise, filesystem renames, and fresh Zsh processes.
They include abrupt stops after every replacement, handled interruption, resumed recovery, malformed receipts, private sentinels, and unrelated Git staging.
The script self-test repeats two complete command paths with isolated script dependencies.
No live HOME acceptance or machine cutover occurred.

This version supports the default HOME paths for Zsh and XDG configuration.
It does not manage Bash startup, alternate ZDOTDIR layouts, application restarts, or shared-interpreter removal.
Process interruption cases do not prove recovery after power loss or concurrent external writes.
