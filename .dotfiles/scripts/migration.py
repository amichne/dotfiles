"""Verify the last bare HOME revision supported by the checkout migration."""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path

from install_state import apply_lock, digest, encoded
from layered import (
    Change,
    File,
    LayerConflict,
    Link,
    check_parents,
    fingerprint,
    inspect,
    ownership_record,
    shell_manifest,
    write,
)

BASELINE = "cbe207a2585b05ebc9b738cb0574a98e3269fab8"

ORIGINS = frozenset(
    {
        "git@github.com:amichne/dotfiles.git",
        "https://github.com/amichne/dotfiles.git",
        "https://github.com/amichne/dotfiles",
        "ssh://git@github.com/amichne/dotfiles.git",
    }
)


def verify_baseline(home: Path, env: dict[str, str], converted: dict[Path, Change]) -> str:
    # A local inspection must use the original objects and never fetch missing ones.
    env = {
        **env,
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_ALLOW_PROTOCOL": "",
    }
    metadata = home / ".dotfiles.git"
    if not metadata.is_dir() or metadata.is_symlink():
        raise LayerConflict("missing bare installation")

    def git(*arguments: str) -> bytes:
        result = subprocess.run(
            ["git", f"--git-dir={metadata}", *arguments],
            cwd=home,
            env=env,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise LayerConflict(f"cannot verify bare installation: git {arguments[0]}")
        return result.stdout

    if git("rev-parse", "--is-bare-repository").strip() != b"true":
        raise LayerConflict("expected a bare repository")
    origin = os.fsdecode(git("remote", "get-url", "origin")).strip()
    if origin not in ORIGINS:
        raise LayerConflict("unexpected bare repository origin")
    if (
        git("symbolic-ref", "HEAD").strip() != b"refs/heads/main"
        or git("rev-parse", "HEAD").decode().strip() != BASELINE
    ):
        raise LayerConflict(f"migration requires bare main at {BASELINE}")
    worktrees = metadata / "worktrees"
    if worktrees.is_symlink() or (worktrees.exists() and any(worktrees.iterdir())):
        raise LayerConflict("bare repository has linked worktrees")
    for name in (
        "commondir",
        "objects/info/alternates",
        "MERGE_HEAD",
        "rebase-apply",
        "rebase-merge",
    ):
        if os.path.lexists(metadata / name):
            raise LayerConflict(f"unsupported bare repository state: {name}")
    if any(metadata.glob("*.lock")) or any((metadata / "refs").rglob("*.lock")):
        raise LayerConflict("bare repository has an active Git lock")

    # The index must describe the complete baseline tree with an ordinary stage-zero
    # entry for every file. Comparing raw HOME bytes independently also catches
    # changes hidden by index flags, fsmonitor, clean filters, or core.fileMode.
    index = git("ls-files", "--stage", "-z").split(b"\0")[:-1]
    expected: list[bytes] = []
    for record in git("ls-tree", "-rz", "--full-tree", BASELINE).split(b"\0")[:-1]:
        header, name = record.split(b"\t", 1)
        mode, kind, oid = header.split()
        target = home / os.fsdecode(name)
        if kind != b"blob" or mode not in (b"100644", b"100755"):
            raise LayerConflict(f"unsupported baseline entry: {target}")
        expected.append(mode + b" " + oid + b" 0\t" + name)
        check_parents(target, home)
        content = inspect(target)
        change = converted.get(target)
        if change is not None and content == change.after:
            # An interrupted apply can leave this exact replacement. Its saved
            # original must still match the independent Git tree below.
            content = change.before
        if not isinstance(content, File):
            raise LayerConflict(f"expected a tracked regular file: {target}")
        blob = f"blob {len(content.data)}\0".encode() + content.data
        actual = hashlib.sha1(blob, usedforsecurity=False).hexdigest().encode()
        if actual != oid or bool(content.mode & 0o100) != (mode == b"100755"):
            raise LayerConflict(f"changed tracked file: {target}")
    if expected != index:
        raise LayerConflict("bare index has staged changes")
    index_file = metadata / "index"
    if index_file.is_symlink() or not index_file.is_file():
        raise LayerConflict("expected a regular bare Git index")
    location = metadata.stat()
    # The comparison above binds the staged entries. Git may refresh its stat
    # cache during ordinary inspection without changing any staged entry.
    return digest(encoded([BASELINE, origin, location.st_dev, location.st_ino]))


def migrate(
    source: Path,
    revision: Callable[[], str],
    home: Path,
    state: Path,
    env: dict[str, str],
    expected: str | None,
) -> dict[str, object]:
    """Keep the bare index active until every replacement and the layer receipt exist."""
    archive = state / "bare-main"
    metadata = home / ".dotfiles.git"
    archived = archive / "repository.git"
    if source.is_relative_to(metadata) or source.is_relative_to(state):
        raise LayerConflict("choose a checkout outside Git metadata and installation state")
    with apply_lock(state) if expected is not None else nullcontext():
        if archive.is_symlink() or (archive.exists() and not archive.is_dir()):
            raise LayerConflict(f"unexpected recovery path: {archive}")
        if os.path.lexists(archived):
            raise LayerConflict(f"migration already archived the repository at {archived}")
        pending = archive.exists()
        ledger = state / "layered.json"
        entries = shell_manifest(source, home)
        paths = [str(entry.target) for entry in entries]
        owner = File(ownership_record(source, paths, paths), 0o600)
        installed = inspect(ledger)
        if installed is not None and (not pending or installed != owner):
            raise LayerConflict(f"unexpected layer ownership: {ledger}")
        changes: list[Change] = []
        remaining: list[Change] = []
        inputs: list[object] = []
        for entry in entries:
            relative = entry.source.relative_to(source)
            if entry.target != home / relative:
                raise LayerConflict("migration requires the default ZDOTDIR and XDG_CONFIG_HOME")
            if entry.source.resolve() != entry.source or not entry.source.is_file():
                raise LayerConflict(f"missing or linked checkout file: {entry.source}")
            check_parents(entry.target, home)
            current = inspect(entry.target)
            original = current
            if pending:
                backup = archive / "files" / relative
                check_parents(backup, home)
                original = inspect(backup)
            if not isinstance(original, File):
                raise LayerConflict(f"missing original regular file: {entry.target}")
            after = File(entry.block, original.mode) if entry.block else Link(str(entry.source))
            change = Change(entry, original, after)
            changes.append(change)
            if current == original:
                remaining.append(change)
            elif not pending or current != after:
                raise LayerConflict(f"changed migration destination: {entry.target}")
            inputs.append(
                [digest(entry.source.read_bytes()), fingerprint(original), fingerprint(after)]
            )
        legacy = verify_baseline(home, env, {c.entry.target: c for c in changes} if pending else {})
        ancestor = next(path for path in (archive, *archive.parents) if path.exists())
        if metadata.stat().st_dev != ancestor.stat().st_dev or metadata.is_mount():
            raise LayerConflict("bare metadata must be movable to the recovery directory by rename")
        head = revision()
        identity = digest(encoded([legacy, str(home), str(source), head, inputs]))
        report: dict[str, object] = {
            "status": "planned",
            "action": "migrate",
            "planId": identity,
            "source": str(source),
            "revision": head,
            "previousRevision": BASELINE,
            "archivedRepository": str(archived),
            "changes": [c.report() for c in changes],
        }
        receipt = encoded(report)
        if pending:
            saved = inspect(archive / "receipt.json")
            if not isinstance(saved, File) or saved.data != receipt:
                raise LayerConflict(f"migration inputs differ from the saved receipt at {archive}")
        if expected is None:
            return {**report, "remaining": [str(c.entry.target) for c in remaining]}
        if expected != identity:
            raise LayerConflict("stale-plan")
        if not pending:
            # Publish the full set of preimages before the first HOME replacement.
            with tempfile.TemporaryDirectory(dir=state) as staging:
                prepared = Path(staging) / "bare-main"
                prepared.mkdir(mode=0o700)
                for change in changes:
                    backup = prepared / "files" / change.entry.target.relative_to(home)
                    write(backup, None, change.before, home)
                _ = (prepared / "receipt.json").write_bytes(receipt)
                _ = prepared.rename(archive)
        if installed is None:
            write(ledger, None, owner, home)
        for change in remaining:
            write(change.entry.target, change.before, change.after, home)
        # Recheck the index and the real active files immediately before handoff.
        converted = {c.entry.target: c for c in changes}
        if verify_baseline(home, env, converted) != legacy or any(
            inspect(c.entry.target) != c.after for c in changes
        ):
            raise LayerConflict("HOME changed before repository archival")
        _ = metadata.rename(archived)
        return {**report, "status": "migrated"}
