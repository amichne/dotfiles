"""Filesystem evidence and standalone recovery. This module needs only Python's standard library."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import TypeGuard

# This is the complete admitted Zsh/Config inventory, not a filesystem scan.
PATHS = (
    ".zshrc",
    ".zshenv",
    ".zprofile",
    ".zlogin",
    ".zlogout",
    ".local/bin/ai",
    ".config/ai",
    ".local/bin/dotfiles",
    ".local/bin/cfg",
    ".local/bin/config",
    ".cfg/shell",
    ".cfg/repo.git",
    ".local/share/config/repo.git",
)
PARENT_PATHS = frozenset({".", *(str(parent) for name in PATHS for parent in Path(name).parents)})


class Kind(StrEnum):
    ABSENT = "absent"
    FILE = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"


class Phase(StrEnum):
    PREPARED = "prepared"
    APPLIED = "applied"
    RECOVERING = "recovering"
    RECOVERED = "recovered"


class Observation(StrEnum):
    APPLIED = "applied"
    RECOVERED = "recovered"
    INCOMPLETE = "incomplete"
    DRIFTED = "drifted"


@dataclass(frozen=True)
class Image:
    kind: Kind
    digest: str

    def __post_init__(self) -> None:
        if re.fullmatch(r"[a-f0-9]{64}", self.digest) is None:
            raise ValueError("invalid image digest")


@dataclass(frozen=True)
class Refused:
    detail: str


@dataclass(frozen=True)
class Restored:
    pass


def image(path: Path) -> Image:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return Image(Kind.ABSENT, hashlib.sha256(b"absent").hexdigest())
    digest = hashlib.sha256()
    digest.update(str(stat.S_IMODE(info.st_mode)).encode() + b"\0")
    if stat.S_ISLNK(info.st_mode):
        kind = Kind.SYMLINK
        digest.update(os.fsencode(path.readlink()))
    elif stat.S_ISREG(info.st_mode):
        kind = Kind.FILE
        with path.open("rb") as content:
            if os.fstat(content.fileno()).st_ino != info.st_ino:
                raise OSError("file changed during read")
            for block in iter(lambda: content.read(1024 * 1024), b""):
                digest.update(block)
    elif stat.S_ISDIR(info.st_mode):
        kind = Kind.DIRECTORY
        for child in sorted(path.iterdir()):
            member = image(child)
            digest.update(
                os.fsencode(child.name) + b"\0" + member.kind.encode() + member.digest.encode()
            )
    else:
        raise OSError(f"unsupported file kind: {path}")
    after = path.lstat()
    if (info.st_ino, info.st_dev, info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (
        after.st_ino,
        after.st_dev,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        raise OSError(f"path changed during read: {path}")
    digest.update(kind.encode())
    return Image(kind, digest.hexdigest())


@dataclass(frozen=True)
class Parent:
    path: str
    device: int
    inode: int
    mode: int

    def __post_init__(self) -> None:
        if (
            self.path not in PARENT_PATHS
            or self.device < 0
            or self.inode < 0
            or not 0 <= self.mode <= 0o7777
        ):
            raise ValueError("invalid inventory parent")


def parents(home: Path, paths: tuple[str, ...]) -> tuple[Parent, ...] | Refused:
    names = {"."}
    for name in paths:
        names.update(parent.as_posix() for parent in Path(name).parents)
    result: list[Parent] = []
    for name in sorted(names):
        path = home / name
        if not path.exists() and not path.is_symlink():
            result.append(Parent(name, 0, 0, 0))
            continue
        if not path.is_dir() or path.is_symlink():
            return Refused(f"existing physical parent directory needed: {path}")
        info = path.stat()
        result.append(Parent(name, info.st_dev, info.st_ino, stat.S_IMODE(info.st_mode)))
    return tuple(result)


def admit_parents(home: Path, expected: tuple[Parent, ...]) -> Refused | None:
    actual = parents(home, tuple(parent.path + "/leaf" for parent in expected))
    if isinstance(actual, Refused):
        return actual
    if actual != expected:
        return Refused("parent identity or mode changed")
    return None


@contextmanager
def locked(home: Path) -> Iterator[None]:
    # Lock the existing directory. No lock file or HOME directory is created.
    descriptor = os.open(home, os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(descriptor)


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_json(path: Path, value: object) -> None:
    descriptor, name = tempfile.mkstemp(prefix=".receipt-", dir=path.parent)
    temporary = Path(name)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        _ = output.write(json.dumps(value, sort_keys=True, indent=2) + "\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


@dataclass(frozen=True)
class Entry:
    path: str
    before: Image
    after: Image


@dataclass(frozen=True)
class Journal:
    home: Path
    parents: tuple[Parent, ...]
    entries: tuple[Entry, ...]
    plan_digest: str


@dataclass(frozen=True)
class _Object:
    fields: dict[str, object]


def _sequence(value: object) -> TypeGuard[list[object]]:
    return isinstance(value, list)


def _fields(value: object, names: set[str]) -> dict[str, object]:
    if not isinstance(value, _Object) or set(value.fields) != names:
        raise ValueError("invalid journal fields")
    return value.fields


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("invalid journal text")
    return value


def _integer(value: object) -> int:
    if type(value) is not int:
        raise ValueError("invalid journal integer")
    return value


def _image(value: object) -> Image:
    fields = _fields(value, {"kind", "digest"})
    return Image(Kind(_text(fields["kind"])), _text(fields["digest"]))


def read_journal(archive: Path) -> Journal:
    if archive.resolve() != archive or archive.is_symlink():
        raise ValueError("archive must use a physical absolute path")
    for name in ("before", "after", "discard"):
        directory = archive / name
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("invalid archive directory")
    content = (archive / "journal.json").read_bytes()
    if hashlib.sha256(content).hexdigest() != (archive / "journal.sha256").read_text().strip():
        raise ValueError("journal digest differs from its receipt")
    raw: object = json.loads(content, object_hook=_Object)
    fields = _fields(raw, {"home", "parents", "entries", "plan_digest"})
    home = Path(_text(fields["home"]))
    if not home.is_absolute() or home.resolve() != home or not home.is_dir():
        raise ValueError("invalid recovery HOME")
    raw_entries = fields["entries"]
    raw_parents = fields["parents"]
    if not _sequence(raw_entries) or not _sequence(raw_parents):
        raise ValueError("invalid journal collections")
    entries: list[Entry] = []
    for item in raw_entries:
        values = _fields(item, {"path", "before", "after"})
        entries.append(
            Entry(_text(values["path"]), _image(values["before"]), _image(values["after"]))
        )
    if tuple(entry.path for entry in entries) != PATHS:
        raise ValueError("invalid recovery inventory")
    expected_names = PARENT_PATHS
    parent_entries: list[Parent] = []
    for item in raw_parents:
        values = _fields(item, {"path", "device", "inode", "mode"})
        parent_entries.append(
            Parent(
                _text(values["path"]),
                _integer(values["device"]),
                _integer(values["inode"]),
                _integer(values["mode"]),
            )
        )
    if frozenset(parent.path for parent in parent_entries) != expected_names or len(
        parent_entries
    ) != len(expected_names):
        raise ValueError("invalid recovery parents")
    digest = _text(fields["plan_digest"])
    if re.fullmatch(r"[a-f0-9]{64}", digest) is None:
        raise ValueError("invalid plan digest")
    plan_bytes = (archive / "plan.json").read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != digest:
        raise ValueError("approved plan differs from its journal")
    raw_plan: object = json.loads(plan_bytes, object_hook=_Object)
    if not isinstance(raw_plan, _Object):
        raise ValueError("invalid approved plan")
    python = Path(_text(raw_plan.fields.get("interpreter")))
    if python != Path(sys.executable).resolve() or image(python) != _image(
        raw_plan.fields.get("interpreter_image")
    ):
        raise ValueError("shared recovery interpreter changed")
    return Journal(home, tuple(parent_entries), tuple(entries), digest)


def save_journal(archive: Path, journal: Journal) -> None:
    value = {
        "home": str(journal.home),
        "parents": [asdict(parent) for parent in journal.parents],
        "entries": [asdict(entry) for entry in journal.entries],
        "plan_digest": journal.plan_digest,
    }
    write_json(archive / "journal.json", value)
    with (archive / "journal.sha256").open("x", encoding="ascii") as receipt:
        _ = receipt.write(
            hashlib.sha256((archive / "journal.json").read_bytes()).hexdigest() + "\n"
        )
        receipt.flush()
        os.fsync(receipt.fileno())
    write_json(archive / "state.json", {"status": Phase.PREPARED})


def phase(archive: Path) -> Phase:
    raw: object = json.loads((archive / "state.json").read_bytes(), object_hook=_Object)
    return Phase(_text(_fields(raw, {"status"})["status"]))


def admissible(archive: Path, journal: Journal) -> Refused | None:
    rejected = admit_parents(journal.home, journal.parents)
    if rejected:
        return rejected
    for index, entry in enumerate(journal.entries):
        target = image(journal.home / entry.path)
        backup = image(archive / "before" / str(index))
        if backup.kind == Kind.ABSENT and target == entry.before:
            continue
        if backup != entry.before:
            return Refused(f"preimage absent or changed: {entry.path}")
        if target != entry.after and target.kind != Kind.ABSENT:
            return Refused(f"replacement changed: {entry.path}")
    return None


def restore_locked(archive: Path, journal: Journal) -> Restored | Refused:
    # Examine every postimage before the first restore.
    rejected = admissible(archive, journal)
    if rejected:
        return rejected
    current = phase(archive)
    if current in (Phase.APPLIED, Phase.RECOVERED):
        for entry in journal.entries:
            expected = entry.after if current == Phase.APPLIED else entry.before
            if image(journal.home / entry.path) != expected:
                return Refused(f"completed operation drift: {entry.path}")
    write_json(archive / "state.json", {"status": Phase.RECOVERING})
    for index, entry in reversed(tuple(enumerate(journal.entries))):
        rejected = admissible(archive, journal)
        if rejected:
            return rejected
        target = journal.home / entry.path
        backup = archive / "before" / str(index)
        if image(backup).kind == Kind.ABSENT and image(target) == entry.before:
            continue
        if image(target).kind != Kind.ABSENT:
            discard = archive / "discard" / str(index)
            if discard.exists() or discard.is_symlink():
                return Refused(f"recovery discard already exists: {entry.path}")
            os.replace(target, discard)
            sync_directory(target.parent)
            sync_directory(discard.parent)
        if entry.before.kind != Kind.ABSENT:
            os.replace(backup, target)
            sync_directory(backup.parent)
            sync_directory(target.parent)
    if not all(image(journal.home / entry.path) == entry.before for entry in journal.entries):
        return Refused("preimages changed before recovery completed")
    write_json(archive / "state.json", {"status": Phase.RECOVERED})
    return Restored()


def status(archive: Path) -> Observation:
    journal = read_journal(archive)
    with locked(journal.home), locked(archive):
        if admissible(archive, journal):
            return Observation.DRIFTED
        current = phase(archive)
        if current == Phase.APPLIED:
            return (
                Observation.APPLIED
                if all(image(journal.home / entry.path) == entry.after for entry in journal.entries)
                else Observation.DRIFTED
            )
        if current == Phase.RECOVERED:
            return (
                Observation.RECOVERED
                if all(
                    image(journal.home / entry.path) == entry.before for entry in journal.entries
                )
                else Observation.DRIFTED
            )
        return Observation.INCOMPLETE


def recover(archive: Path) -> Restored | Refused:
    if archive.is_symlink() or archive.resolve() != archive:
        return Refused("recovery archive must have a physical absolute path")
    journal = read_journal(archive)
    with locked(journal.home), locked(archive):
        return restore_locked(archive, journal)


def main() -> int:
    archive = Path(__file__).resolve().parent
    try:
        result = recover(archive)
        if isinstance(result, Refused):
            print(f"cutover: {result.detail}", file=sys.stderr)
            return 75
        print(json.dumps({"status": "recovered", "archive": str(archive)}))
        return 0
    except (OSError, ValueError) as error:
        print(f"cutover: recovery stopped: {error}", file=sys.stderr)
        return 74
    except KeyboardInterrupt:
        print("cutover: recovery interrupted. Run this entrypoint again.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
