"""Manage the three Zsh startup files, Git include, and Starship link in one checkout."""

from __future__ import annotations

import json
import os
import shlex
import stat
import sys
import tempfile
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path

from install_state import apply_lock, digest, encoded

START = b"# >>> amichne/dotfiles >>>"
END = b"# <<< amichne/dotfiles <<<"


class LayerConflict(ValueError):
    """A source, destination, or ownership record needs attention before apply."""


@dataclass(frozen=True)
class Entry:
    source: Path
    target: Path
    block: bytes | None  # None denotes a symbolic link.


def configured_path(name: str, default: Path) -> Path:
    path = Path(os.environ.get(name) or default)
    if not path.is_absolute() or ".." in path.parts:
        raise LayerConflict(f"{name} needs an absolute path without '..'")
    return path


def manifest(source: Path, home: Path) -> tuple[Entry, ...]:
    zd = configured_path("ZDOTDIR", home)
    config = configured_path("XDG_CONFIG_HOME", home / ".config")
    if any(ord(c) < 32 for c in str(source)):
        raise LayerConflict("unsupported control character in checkout path")

    def block(lines: str) -> bytes:
        return b"\n".join([START, os.fsencode(lines), END, b""])

    entries: list[Entry] = []
    for name in (".zshenv", ".zprofile", ".zshrc"):
        path = source / name
        quoted = shlex.quote(str(path))
        # A missing checkout must not stop the personal startup file.
        hook = block(f"if [[ -r {quoted} ]]; then source {quoted}; fi")
        entries.append(Entry(path, zd / name, hook))
    aliases = source / ".config/git/config"
    quoted_git = str(aliases).replace("\\", "\\\\").replace('"', '\\"')
    include = block(f'[include]\n\tpath = "{quoted_git}"')
    entries.append(Entry(aliases, config / "git/config", include))
    entries.append(Entry(source / ".config/starship.toml", config / "starship.toml", None))
    return tuple(entries)


@dataclass(frozen=True)
class File:
    data: bytes
    mode: int


@dataclass(frozen=True)
class Link:
    points_to: str


type Contents = File | Link | None


def inspect(path: Path) -> Contents:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(info.st_mode):
        return Link(os.readlink(path))
    if not stat.S_ISREG(info.st_mode):
        raise LayerConflict(f"expected a regular file: {path}")
    return File(path.read_bytes(), stat.S_IMODE(info.st_mode))


def fingerprint(contents: Contents) -> object:
    match contents:
        case None:
            return None
        case File(data, mode):
            return {"sha256": digest(data), "mode": mode}
        case Link(target):
            return {"link": target}


def check_parents(path: Path, home: Path) -> None:
    for parent in path.parents:
        if parent == home:
            break
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise LayerConflict(f"unexpected destination parent: {parent}")


def desired(
    entry: Entry, before: Contents, owned: bool, created: bool, uninstall: bool
) -> Contents:
    if entry.block is None:
        expected = Link(str(entry.source))
        if before is not None and (before != expected or not owned):
            raise LayerConflict(f"occupied link destination: {entry.target}")
        return None if uninstall else expected
    if isinstance(before, Link):
        raise LayerConflict(f"unexpected symlink: {entry.target}")
    data = before.data if before else b""
    mode = before.mode if before else 0o600
    if START in data or END in data:
        if not owned or data.count(START) != 1 or data.count(END) != 1 or entry.block not in data:
            raise LayerConflict(f"unrecognized managed block: {entry.target}")
        offset = data.index(entry.block)
        if offset and data[offset - 1 : offset] != b"\n" and data[:offset] != b"\xef\xbb\xbf":
            raise LayerConflict(f"edited managed block: {entry.target}")
        if not uninstall:
            return before
        remainder = data.replace(entry.block, b"", 1)
        return None if created and not remainder else File(remainder, mode)
    if uninstall:
        return before
    if b"\0" in data:
        raise LayerConflict(f"binary configuration: {entry.target}")
    offset = 3 if data.startswith(b"\xef\xbb\xbf") else 0
    if data.startswith(b"#!"):
        if b"\n" not in data:
            raise LayerConflict(f"unterminated interpreter line: {entry.target}")
        offset = data.index(b"\n") + 1
    return File(data[:offset] + entry.block + data[offset:], mode)


@dataclass(frozen=True)
class Change:
    entry: Entry
    before: Contents
    after: Contents

    def report(self) -> dict[str, object]:
        return {
            "path": str(self.entry.target),
            "operation": "link" if self.entry.block is None else "block",
            "source": str(self.entry.source),
            "block": os.fsdecode(self.entry.block) if self.entry.block else None,
        }


@dataclass(frozen=True)
class Plan:
    identity: str
    revision: str
    ownership: bytes
    changes: tuple[Change, ...]


def build_plan(source: Path, revision: str, home: Path, state: Path, uninstall: bool) -> Plan:
    if os.path.lexists(home / ".dotfiles.git"):
        raise LayerConflict("bare installation requires migration")
    entries = manifest(source, home)
    ledger = inspect(state / "layered.json")
    paths = [str(e.target) for e in entries]
    initial: list[str] = []
    if isinstance(ledger, Link):
        raise LayerConflict(f"unexpected ownership link: {state}")
    if ledger:
        try:
            record: dict[str, object] = json.loads(ledger.data)
            created = record["created"]
            if not isinstance(created, list):
                raise ValueError("expected the list of created files")
            initial = [path for path in paths if path in created]
        except (ValueError, KeyError, TypeError) as error:
            raise LayerConflict(f"invalid ownership record: {state}") from error
    snapshots: list[object] = []
    changes: list[Change] = []
    for entry in entries:
        check_parents(entry.target, home)
        if entry.target.is_relative_to(source) or entry.target.is_relative_to(state):
            raise LayerConflict(f"destination overlaps installer files: {entry.target}")
        if entry.source.resolve() != entry.source or not entry.source.is_file():
            raise LayerConflict(f"missing or linked checkout file: {entry.source}")
        before = inspect(entry.target)
        name = str(entry.target)
        if not ledger and before is None:
            initial.append(name)
        snapshots.append([name, fingerprint(before), digest(entry.source.read_bytes())])
        if uninstall and not ledger:
            continue
        after = desired(entry, before, bool(ledger), name in initial, uninstall)
        if before != after:
            changes.append(Change(entry, before, after))
    ownership = encoded({"version": 1, "source": str(source), "targets": paths, "created": initial})
    if ledger and ledger.data != ownership:
        raise LayerConflict(f"checkout or destination differs from ownership record: {state}")
    identity = digest(encoded([revision, digest(ownership), bool(ledger), uninstall, snapshots]))
    return Plan(identity, revision, ownership, tuple(changes))


def write(path: Path, before: Contents, after: Contents, home: Path) -> None:
    check_parents(path, home)
    if inspect(path) != before:
        raise LayerConflict(f"destination changed: {path}")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    match after:
        case None:
            path.unlink()
        case Link(target):
            path.symlink_to(target)
        case File(data, mode):
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as out:
                temp = Path(out.name)
                try:
                    _ = out.write(data)
                    out.flush()
                    os.fchmod(out.fileno(), mode)
                    if before is None:
                        os.link(temp, path)
                    else:
                        if inspect(path) != before:
                            raise LayerConflict(f"destination changed: {path}")
                        _ = temp.replace(path)
                finally:
                    temp.unlink(missing_ok=True)


def layered_install(
    source: Path,
    revision: Callable[[], str],
    home: Path,
    state: Path,
    uninstall: bool,
    expected: str | None,
) -> dict[str, object]:
    with apply_lock(state) if expected is not None else nullcontext():
        plan = build_plan(source, revision(), home, state, uninstall)
        report: dict[str, object] = {
            "status": "planned",
            "action": "uninstall" if uninstall else "install",
            "source": str(source),
            "revision": plan.revision,
            "planId": plan.identity,
            "changes": [change.report() for change in plan.changes],
        }
        if expected is None:
            return report
        if plan.identity != expected:
            raise LayerConflict("stale-plan")
        ledger = state / "layered.json"
        if plan.changes:
            backup = Path(tempfile.mkdtemp(prefix="layered-", dir=state))
            report["backup"] = str(backup)
            preimages: dict[str, object] = {}
            for i, change in enumerate(plan.changes):
                before = change.before
                preimages[str(change.entry.target)] = {
                    "backup": str(i) if isinstance(before, File) else None,
                    "before": fingerprint(before),
                    "after": fingerprint(change.after),
                }
                if isinstance(before, File):
                    _ = (backup / str(i)).write_bytes(before.data)
            _ = (backup / "receipt.json").write_bytes(encoded({**report, "preimages": preimages}))
            print(f"install: recovery-receipt:{backup / 'receipt.json'}", file=sys.stderr)
            if not uninstall and not ledger.exists():
                write(ledger, None, File(plan.ownership, 0o600), home)
            for change in plan.changes:
                write(change.entry.target, change.before, change.after, home)
        if uninstall and ledger.exists():
            ledger.unlink()
    report["status"] = "uninstalled" if uninstall else "installed"
    return report
