"""Reclaim disk from linked worktrees, saving unmerged work as patches first.

The plan is read-only. ``--apply`` deletes ignored build output (directories Git
reports as ignored whose name is a configured build name). With
``remove_worktrees`` it also removes the worktree after its work is saved.

A worktree with uncommitted changes or commits not on the base ref is written
to the patch catalog before anything in it is deleted. A worktree in which a
Gradle or Kotlin daemon holds files is always retained. When no such daemon
runs at all, recent activity alone does not retain a worktree.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

DEFAULT_BUILD_NAMES = ("build", ".gradle", ".kotlin", "node_modules", "out")
DAEMON_PATTERN = "GradleDaemon|KotlinCompileDaemon|GradleWrapperMain"
GIT_TIMEOUT_SECONDS = 30


class Code(StrEnum):
    INVALID_ARGUMENTS = "invalid-arguments"
    INVALID_CONFIG = "invalid-config"


class Retain(StrEnum):
    MAIN = "main-worktree"
    LOCKED = "locked"
    MISSING = "missing"
    CURRENT = "current-directory"
    DAEMON = "daemon-active"
    ACTIVE = "recently-active"
    CHANGED = "changed-unsaved"
    GIT_FAILED = "git-failed"


@dataclass(frozen=True)
class Rejected:
    code: Code


@dataclass(frozen=True)
class Settings:
    idle_days: int
    build_names: frozenset[str]
    patch_root: Path
    base_ref: str
    patch_changed: bool
    remove_worktrees: bool
    daemon_pattern: str


@dataclass(frozen=True)
class Request:
    repositories: tuple[Path, ...]
    settings: Settings
    apply: bool
    json: bool


@dataclass(frozen=True)
class Target:
    path: Path
    bytes: int


@dataclass(frozen=True)
class Worktree:
    repository: Path
    path: Path
    retained: Retain | None
    targets: tuple[Target, ...] = ()
    needs_patch: bool = False


def read_settings(path: Path) -> Settings | Rejected:
    try:
        raw = tomllib.loads(path.read_text()) if path.is_file() else {}
    except (OSError, tomllib.TOMLDecodeError):
        return Rejected(Code.INVALID_CONFIG)
    idle = raw.get("idle_days", 3)
    names = raw.get("build_names", list(DEFAULT_BUILD_NAMES))
    root = raw.get("patch_root", "~/.worktrees/patches")
    base = raw.get("base_ref", "origin/main")
    patch_changed = raw.get("patch_changed", True)
    remove = raw.get("remove_worktrees", False)
    pattern = raw.get("daemon_pattern", DAEMON_PATTERN)
    entries = cast("list[object]", names) if isinstance(names, list) else []
    build_names = tuple(n for n in entries if isinstance(n, str) and n and "/" not in n)
    if (
        not isinstance(idle, int)
        or isinstance(idle, bool)
        or idle < 0
        or not build_names
        or len(build_names) != len(entries)
        or not isinstance(root, str)
        or not isinstance(base, str)
        or not isinstance(patch_changed, bool)
        or not isinstance(remove, bool)
        or not isinstance(pattern, str)
        or not pattern
    ):
        return Rejected(Code.INVALID_CONFIG)
    return Settings(
        idle, frozenset(build_names), Path(root).expanduser(), base, patch_changed, remove, pattern
    )


def parse(arguments: list[str], default_config: Path) -> Request | Rejected:
    repositories: list[Path] = []
    config = default_config
    idle: int | None = None
    remove: bool | None = None
    apply = as_json = False
    items = iter(arguments)
    for item in items:
        match item:
            case "--repo" | "--config" | "--idle-days":
                value = next(items, None)
                if value is None:
                    return Rejected(Code.INVALID_ARGUMENTS)
                if item == "--repo":
                    repositories.append(Path(value).expanduser().resolve())
                elif item == "--config":
                    config = Path(value).expanduser()
                elif value.isdigit():
                    idle = int(value)
                else:
                    return Rejected(Code.INVALID_ARGUMENTS)
            case "--remove-worktrees":
                remove = True
            case "--apply":
                apply = True
            case "--json":
                as_json = True
            case _:
                return Rejected(Code.INVALID_ARGUMENTS)
    if not repositories:
        return Rejected(Code.INVALID_ARGUMENTS)
    settings = read_settings(config)
    if isinstance(settings, Rejected):
        return settings
    settings = Settings(
        settings.idle_days if idle is None else idle,
        settings.build_names,
        settings.patch_root,
        settings.base_ref,
        settings.patch_changed,
        settings.remove_worktrees if remove is None else remove,
        settings.daemon_pattern,
    )
    return Request(tuple(repositories), settings, apply, as_json)


def git(root: Path, env: dict[str, str], *arguments: str) -> bytes | None:
    try:
        result = subprocess.run(
            ("git", "-C", str(root), *arguments),
            env={**env, "GIT_OPTIONAL_LOCKS": "0"},
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    return None if result.returncode else result.stdout


def daemon_paths(pattern: str) -> tuple[Path, ...] | None:
    """Return paths that build daemons hold open, or None when no daemon runs."""
    found = subprocess.run(("pgrep", "-f", pattern), capture_output=True, text=True, check=False)
    pids = [pid for pid in found.stdout.split() if pid.isdigit() and int(pid) != os.getpid()]
    if not pids:
        return None
    listed = subprocess.run(
        ("lsof", "-n", "-P", "-Fn", "-p", ",".join(pids)),
        capture_output=True,
        text=True,
        check=False,
    )
    return tuple(Path(line[1:]) for line in listed.stdout.splitlines() if line.startswith("n/"))


def registrations(raw: bytes) -> list[tuple[Path, bool, bool]]:
    """Return (path, locked, prunable) for each worktree record."""
    records: list[tuple[Path, bool, bool]] = []
    for block in raw.split(b"\0\0"):
        fields = [f.decode(errors="surrogateescape") for f in block.split(b"\0") if f]
        paths = [f.removeprefix("worktree ") for f in fields if f.startswith("worktree ")]
        if len(paths) != 1:
            continue
        locked = any(f == "locked" or f.startswith("locked ") for f in fields)
        prunable = any(f == "prunable" or f.startswith("prunable ") for f in fields)
        records.append((Path(paths[0]), locked, prunable))
    return records


def last_activity(worktree: Path, env: dict[str, str]) -> float | None:
    raw = git(worktree, env, "rev-parse", "--absolute-git-dir")
    if raw is None:
        return None
    git_dir = Path(raw.decode().strip())
    stamps = [
        (git_dir / name).stat().st_mtime
        for name in ("index", "HEAD", "logs/HEAD")
        if (git_dir / name).exists()
    ]
    return max(stamps, default=None)


def disk_bytes(root: Path) -> int:
    total = 0
    for directory, _, files in os.walk(root, followlinks=False):
        for name in files:
            try:
                total += os.lstat(os.path.join(directory, name)).st_blocks * 512
            except OSError:
                continue
    return total


def build_targets(
    worktree: Path, names: frozenset[str], env: dict[str, str]
) -> tuple[Target, ...] | None:
    raw = git(
        worktree,
        env,
        "ls-files",
        "-z",
        "--others",
        "--ignored",
        "--exclude-standard",
        "--directory",
    )
    if raw is None:
        return None
    targets: list[Target] = []
    for entry in raw.decode(errors="surrogateescape").split("\0"):
        if not entry.endswith("/") or Path(entry).name not in names:
            continue
        path = worktree / entry.rstrip("/")
        if path.is_symlink() or not path.is_dir() or worktree not in path.resolve().parents:
            continue
        targets.append(Target(path, disk_bytes(path)))
    return tuple(targets)


def unmerged(worktree: Path, base: str, env: dict[str, str]) -> bool:
    """True unless HEAD is proven to be contained in the base ref."""
    return git(worktree, env, "merge-base", "--is-ancestor", "HEAD", base) is None


def inspect(
    repository: Path,
    path: Path,
    locked: bool,
    prunable: bool,
    request: Request,
    env: dict[str, str],
    held: tuple[Path, ...] | None,
    now: float,
    cwd: Path,
) -> Worktree:
    settings = request.settings
    if locked:
        return Worktree(repository, path, Retain.LOCKED)
    if prunable or not path.is_dir():
        return Worktree(repository, path, Retain.MISSING)
    if cwd == path or path in cwd.parents:
        return Worktree(repository, path, Retain.CURRENT)
    if held is not None and any(h == path or path in h.parents for h in held):
        return Worktree(repository, path, Retain.DAEMON)
    status = git(path, env, "status", "--porcelain=v1", "--untracked-files=normal")
    activity = last_activity(path, env)
    if status is None or activity is None:
        return Worktree(repository, path, Retain.GIT_FAILED)
    if held is not None and now - activity < settings.idle_days * 86400:
        return Worktree(repository, path, Retain.ACTIVE)
    changed = bool(status.strip())
    if changed and not settings.patch_changed:
        return Worktree(repository, path, Retain.CHANGED)
    targets = build_targets(path, settings.build_names, env)
    if targets is None:
        return Worktree(repository, path, Retain.GIT_FAILED)
    needs_patch = changed or unmerged(path, settings.base_ref, env)
    return Worktree(repository, path, None, targets, needs_patch)


def save_patch(row: Worktree, settings: Settings, env: dict[str, str], stamp: str) -> Path | None:
    """Write commits beyond the base, uncommitted changes, and untracked files."""
    wt = row.path
    # Worktree names repeat across parents (e.g. <id>/kast), so key by path too.
    key = f"{wt.name}-{hashlib.sha256(str(wt).encode()).hexdigest()[:8]}"
    destination = settings.patch_root / row.repository.name / key / stamp
    commits = git(wt, env, "format-patch", "--binary", "--stdout", f"{settings.base_ref}..HEAD")
    tracked = git(wt, env, "diff", "--binary", "HEAD")
    untracked = git(wt, env, "ls-files", "-z", "--others", "--exclude-standard")
    head = git(wt, env, "rev-parse", "HEAD")
    branch = git(wt, env, "branch", "--show-current")
    if commits is None or tracked is None or untracked is None or head is None or branch is None:
        return None
    pieces = [tracked]
    for name in untracked.decode(errors="surrogateescape").split("\0"):
        if not name:
            continue
        # --no-index exits 1 when files differ; read stdout regardless.
        added = subprocess.run(
            ("git", "-C", str(wt), "diff", "--no-index", "--binary", "--", "/dev/null", name),
            env=env,
            capture_output=True,
            check=False,
        )
        if added.returncode not in (0, 1):
            return None
        pieces.append(added.stdout)
    try:
        destination.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        return None
    _ = (destination / "commits.patch").write_bytes(commits)
    _ = (destination / "worktree.patch").write_bytes(b"".join(pieces))
    _ = (destination / "meta.json").write_text(
        json.dumps(
            {
                "repository": str(row.repository),
                "worktree": str(wt),
                "branch": branch.decode().strip(),
                "head": head.decode().strip(),
                "base": settings.base_ref,
                "restore": "git worktree add -b <branch> <path> <base>; git am commits.patch; git apply worktree.patch",
            },
            indent=2,
        )
        + "\n"
    )
    return destination


def gib(count: int) -> str:
    return f"{count / 2**30:.1f} GiB"


def run(request: Request, env: dict[str, str]) -> int:
    settings = request.settings
    now = time.time()
    stamp = time.strftime("%Y%m%dT%H%M%S")
    cwd = Path.cwd().resolve()
    held = daemon_paths(settings.daemon_pattern)
    rows: list[Worktree] = []
    seen: set[Path] = set()
    for repository in request.repositories:
        raw = git(repository, env, "worktree", "list", "--porcelain", "-z")
        if raw is None:
            rows.append(Worktree(repository, repository, Retain.GIT_FAILED))
            continue
        for index, (path, locked, prunable) in enumerate(registrations(raw)):
            # Repositories named twice, or as worktrees of each other, list the same paths.
            if path in seen:
                continue
            seen.add(path)
            if index == 0:
                rows.append(Worktree(repository, path, Retain.MAIN))
            else:
                rows.append(
                    inspect(repository, path, locked, prunable, request, env, held, now, cwd)
                )
    results: list[dict[str, object]] = []
    removed = 0
    for row in rows:
        patch: Path | None = None
        action = "retain" if row.retained else "plan"
        idle_without_output = not row.targets and not settings.remove_worktrees
        if request.apply and row.retained is None and not idle_without_output:
            try:
                if row.needs_patch:
                    patch = save_patch(row, settings, env, stamp)
                    if patch is None:
                        action = "patch-failed"
                if action != "patch-failed":
                    if settings.remove_worktrees:
                        # Work is saved in the catalog (or merged and clean), so force is safe.
                        gone = git(
                            row.repository, env, "worktree", "remove", "--force", str(row.path)
                        )
                        action = "removed-worktree" if gone is not None else "remove-failed"
                        if gone is not None:
                            removed += sum(t.bytes for t in row.targets)
                    else:
                        for target in row.targets:
                            shutil.rmtree(target.path)
                            removed += target.bytes
                        action = "removed-build"
            except OSError:
                action = "io-failed"
        results.append(
            {
                "path": str(row.path),
                "retained": row.retained,
                "action": action,
                "needsPatch": row.needs_patch,
                "patch": None if patch is None else str(patch),
                "targets": [{"path": str(t.path), "bytes": t.bytes} for t in row.targets],
            }
        )
    total = sum(t.bytes for row in rows for t in row.targets)
    if request.json:
        print(
            json.dumps(
                {
                    "version": 2,
                    "applied": request.apply,
                    "daemonsRunning": held is not None,
                    "idleDays": settings.idle_days,
                    "removeWorktrees": settings.remove_worktrees,
                    "reclaimableBytes": total,
                    "removedBytes": removed,
                    "worktrees": results,
                }
            )
        )
        return 0
    print(f"build daemons running: {'yes' if held is not None else 'no'}")
    for row, result in zip(rows, results, strict=True):
        if row.retained is not None:
            print(f"retain  {row.retained:<18} {row.path}")
            continue
        size = gib(sum(t.bytes for t in row.targets))
        note = " (patch)" if row.needs_patch else ""
        print(f"{result['action']:<16} {size:>9}{note}  {row.path}")
        if result["patch"]:
            print(f"  saved {result['patch']}")
    if request.apply:
        print(f"removed at least {gib(removed)}")
    else:
        print(f"reclaimable build output {gib(total)}; rerun with --apply")
    return 0
