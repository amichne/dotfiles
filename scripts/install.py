#!/usr/bin/env -S uv run --locked --script
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = []
# [tool.uv]
# no-build = true
# required-version = ">=0.12.9"
# [[tool.uv.index]]
# name = "pypi"
# url = "https://pypi.org/simple"
# default = true
# ///
"""Plan or apply a reviewed Dotfiles commit to the single bare HOME index."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from df import ORIGINS, Failure, git_environment, open_home

PRIVATE = frozenset(
    {
        ".pi/agent/APPEND_SYSTEM.md",
        ".pi/agent/AGENTS.md",
        ".codex/AGENTS.md",
        ".codex/hooks.json",
        ".pi/agent/extensions/engineering-checks.ts",
    }
)
PACKAGE = "npm:pi-subagents@0.79.0"
Reason = Literal[
    "git-failed",
    "unsupported-tree-entry",
    "symlink-target",
    "non-file-target",
    "invalid-source-repository",
    "not-source-root",
    "unexpected-source-origin",
    "dirty-source",
    "empty-source",
    "private-source-path",
    "invalid-installed-repository",
    "dirty-home",
    "divergent-history",
    "untracked-conflict",
    "missing-dependency",
    "symlink-state",
    "destination-changed",
    "stale-plan",
]


class Rejected(Exception):
    """A named precondition failure or a native command failure."""

    def __init__(self, reason: Reason, detail: str = "", status: int = 65):
        super().__init__(f"{reason}:{detail}" if detail else reason)
        self.status = status


class Arguments(argparse.Namespace):
    source: Path
    apply: bool
    expected_plan: str | None
    with_pi_subagents: bool


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(data: object) -> bytes:
    return (json.dumps(data, sort_keys=True, ensure_ascii=True) + "\n").encode()


def git(environment: dict[str, str], prefix: list[str], *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", *prefix, *args],
        env=environment,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        # Git can print source or destination content in an error. Keep the stage and code only.
        raise Rejected("git-failed", args[0], result.returncode)
    return result.stdout


@dataclass(frozen=True)
class Entry:
    mode: int
    oid: str


def tree(environment: dict[str, str], prefix: list[str], revision: str) -> dict[str, Entry]:
    entries: dict[str, Entry] = {}
    for record in git(environment, prefix, "ls-tree", "--full-tree", "-rz", revision).split(b"\0"):
        if not record:
            continue
        fields, raw = record.split(b"\t", 1)
        mode, kind, oid = fields.decode("ascii").split()
        name = os.fsdecode(raw)
        path = PurePosixPath(name)
        if (
            mode not in {"100644", "100755"}
            or kind != "blob"
            or path.is_absolute()
            or ".." in path.parts
            or {".git", ".dotfiles.git"}.intersection(path.parts)
        ):
            raise Rejected("unsupported-tree-entry")
        entries[name] = Entry(0o755 if mode == "100755" else 0o644, oid)
    return entries


def regular_file(root: Path, name: str) -> tuple[bytes, int] | None:
    path = root / name
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise Rejected("symlink-target")
        if parent == root:
            break
    if not path.exists():
        return None
    if not path.is_file():
        raise Rejected("non-file-target")
    return path.read_bytes(), path.stat().st_mode & 0o777


@dataclass(frozen=True)
class Installed:
    revision: str
    head: str
    index_sha256: str | None


@dataclass(frozen=True)
class Plan:
    source: Path
    home: Path
    origin: str
    revision: str
    previous: Installed | None
    changes: tuple[str, ...]
    adopted: tuple[str, ...]
    preserved: tuple[str, ...]
    snapshots: dict[str, tuple[bytes, int] | None]
    pi: Path | None
    identity: str

    def report(self) -> dict[str, object]:
        action: Literal["install", "update", "unchanged"] = (
            "install"
            if self.previous is None
            else "unchanged"
            if self.previous.revision == self.revision
            else "update"
        )
        return {
            "status": "planned",
            "planId": self.identity,
            "action": action,
            "source": str(self.source),
            "home": str(self.home),
            "revision": self.revision,
            "previousRevision": self.previous.revision if self.previous else None,
            "changes": self.changes,
            "adoptedIdenticalFiles": self.adopted,
            "preservedPrivateFiles": self.preserved,
            "packages": [PACKAGE] if self.pi else [],
        }


def build_plan(source: Path, home: Path, packages: bool, env: dict[str, str]) -> Plan:
    source_git = ["-C", str(source)]
    if (source / ".dotfiles.git").exists():
        opened = open_home(source, env)
        if isinstance(opened, Failure):
            raise Rejected("invalid-source-repository", opened.reason)
        source_git = ["-C", str(source), f"--git-dir={opened.metadata}", f"--work-tree={source}"]
    elif (
        Path(os.fsdecode(git(env, source_git, "rev-parse", "--show-toplevel")).strip()).resolve()
        != source
    ):
        raise Rejected("not-source-root")
    origin = os.fsdecode(git(env, source_git, "remote", "get-url", "origin")).strip()
    if origin not in ORIGINS:
        raise Rejected("unexpected-source-origin")
    if git(env, source_git, "status", "--porcelain=v1", "--untracked-files=no"):
        raise Rejected("dirty-source")
    revision = git(env, source_git, "rev-parse", "HEAD").decode().strip()
    entries = tree(env, source_git, revision)
    if not entries:
        raise Rejected("empty-source")
    if PRIVATE.intersection(entries):
        raise Rejected("private-source-path")
    metadata = home / ".dotfiles.git"
    previous: Installed | None = None
    old: dict[str, Entry] = {}
    if metadata.exists() or metadata.is_symlink():
        opened = open_home(home, env)
        if isinstance(opened, Failure):
            raise Rejected("invalid-installed-repository", opened.reason)
        target_git = ["-C", str(home), f"--git-dir={metadata}", f"--work-tree={home}"]
        if git(env, target_git, "status", "--porcelain=v1", "--untracked-files=no"):
            raise Rejected("dirty-home")
        current = git(env, target_git, "rev-parse", "HEAD").decode().strip()
        # No fetch or index write occurs during the plan.
        ancestry = subprocess.run(
            ["git", *source_git, "merge-base", "--is-ancestor", current, revision],
            env=env,
            capture_output=True,
            check=False,
        )
        if ancestry.returncode:
            raise Rejected("divergent-history")
        old = tree(env, target_git, "HEAD")
        index_data = regular_file(metadata, "index")
        previous = Installed(
            current,
            (metadata / "HEAD").read_text(),
            digest(index_data[0]) if index_data else None,
        )
    names = sorted(entries.keys() | old.keys())
    snapshots = {name: regular_file(home, name) for name in names}
    adopted: list[str] = []
    for name in entries.keys() - old.keys():
        item = snapshots[name]
        if item is not None and (
            item[0] != git(env, source_git, "cat-file", "blob", entries[name].oid)
            or bool(item[1] & 0o111) != bool(entries[name].mode & 0o111)
        ):
            raise Rejected("untracked-conflict", name)
        if item is not None:
            adopted.append(name)
    changes = tuple(name for name in names if old.get(name) != entries.get(name))
    preserved = tuple(name for name in changes if name in PRIVATE and name not in entries)
    pi: Path | None = None
    if packages:
        binary = shutil.which("pi", path=env.get("PATH"))
        if binary is None:
            raise Rejected("missing-dependency", "pi", 69)
        pi = Path(binary).resolve()
    facts = {
        "source": str(source),
        "home": str(home),
        "origin": origin,
        "revision": revision,
        "previous": previous.revision if previous else None,
        "head": previous.head if previous else None,
        "index": previous.index_sha256 if previous else None,
        "files": {
            name: [digest(item[0]), item[1]] if item else None for name, item in snapshots.items()
        },
        "pi": [str(pi), digest(pi.read_bytes())] if pi else None,
    }
    _ = state_path(home)
    return Plan(
        source,
        home,
        origin,
        revision,
        previous,
        changes,
        tuple(sorted(adopted)),
        preserved,
        snapshots,
        pi,
        digest(encoded(facts)),
    )


def state_path(home: Path) -> Path:
    state = home / ".local/state/dotfiles-install"
    # Recovery receipts always stay under HOME, independent of an ambient XDG override.
    for parent in (state, *state.parents):
        if parent.is_symlink():
            raise Rejected("symlink-state")
        if parent == home:
            break
    return state


def apply_plan(plan: Plan, state: Path, env: dict[str, str]) -> tuple[dict[str, object], int]:
    backup = Path(tempfile.mkdtemp(prefix="apply-", dir=state))
    manifest: dict[str, object] = {
        **plan.report(),
        "status": "prepared",
        "backup": str(backup),
        "preimages": {
            name: {"sha256": digest(item[0]), "mode": item[1]} if item else None
            for name in plan.changes
            for item in [plan.snapshots[name]]
        },
    }
    receipt = backup / "receipt.json"
    # Copy every changed preimage before the first Git write.
    for name in plan.changes:
        item = plan.snapshots[name]
        if item is not None:
            path = backup / "files" / name
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            _ = path.write_bytes(item[0])
            path.chmod(item[1])
    _ = receipt.write_bytes(encoded(manifest))
    metadata = plan.home / ".dotfiles.git"
    target_git = ["-C", str(plan.home), f"--git-dir={metadata}", f"--work-tree={plan.home}"]
    try:
        if plan.previous is None:
            with tempfile.TemporaryDirectory(prefix="metadata-", dir=state) as directory:
                temporary = Path(directory) / "repo.git"
                _ = git(
                    env,
                    [],
                    "clone",
                    "--bare",
                    "--single-branch",
                    "--no-hardlinks",
                    str(plan.source),
                    str(temporary),
                )
                _ = git(env, [f"--git-dir={temporary}"], "remote", "set-url", "origin", plan.origin)
                # Source movement never selects a different revision.
                _ = git(env, [f"--git-dir={temporary}"], "update-ref", "HEAD", plan.revision)
                if metadata.exists() or metadata.is_symlink():
                    raise Rejected("destination-changed")
                _ = temporary.rename(metadata)
            _ = git(env, target_git, "read-tree", plan.revision)
            for name in plan.changes:
                if plan.snapshots[name] is None:
                    # checkout-index refuses a file that appears after the plan.
                    _ = git(env, target_git, "checkout-index", "--", name)
        elif plan.previous.revision != plan.revision:
            _ = git(
                env,
                target_git,
                "fetch",
                "--no-tags",
                "--no-write-fetch-head",
                str(plan.source),
                plan.revision,
            )
            _ = git(
                env,
                target_git,
                "merge",
                "--ff-only",
                "--no-edit",
                plan.revision,
            )
    except (Rejected, OSError):
        manifest["status"] = "files-failed"
        print(f"install: recovery-receipt:{receipt}", file=sys.stderr)
        raise
    finally:
        # Formerly public native instructions become private without losing their contents.
        for name in plan.preserved:
            item = plan.snapshots[name]
            if item is not None and not (plan.home / name).exists():
                path = plan.home / name
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as handle:
                    _ = handle.write(item[0])
                path.chmod(item[1])
        _ = receipt.write_bytes(encoded(manifest))
    manifest["status"] = "installed"
    status = 0
    if plan.pi is not None:
        package_env = {
            **env,
            "HOME": str(plan.home),
            "PI_CODING_AGENT_DIR": str(plan.home / ".pi/agent"),
        }
        try:
            status = subprocess.run(
                [str(plan.pi), "install", PACKAGE],
                env=package_env,
                cwd=plan.home,
                stdout=sys.stderr,
                check=False,
            ).returncode
        except OSError:
            status = 74
            manifest["failure"] = "pi-unavailable"
        if status:
            manifest["status"] = "package-failed"
    _ = receipt.write_bytes(encoded(manifest))
    return manifest, status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    _ = parser.add_argument("--apply", action="store_true")
    _ = parser.add_argument("--expected-plan")
    _ = parser.add_argument("--with-pi-subagents", action="store_true")
    args = parser.parse_args(namespace=Arguments())
    if args.apply != (args.expected_plan is not None):
        parser.error("--apply and --expected-plan must appear together")
    env = {**git_environment(), "GIT_OPTIONAL_LOCKS": "0"}
    if shutil.which("git", path=env.get("PATH")) is None:
        raise Rejected("missing-dependency", "git", 69)
    plan = build_plan(args.source.resolve(), Path.home().resolve(), args.with_pi_subagents, env)
    if not args.apply:
        print(encoded(plan.report()).decode(), end="")
        return 0
    if args.expected_plan != plan.identity:
        raise Rejected("stale-plan")
    state = state_path(plan.home)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = state / "apply.lock"
    if lock.is_symlink():
        raise Rejected("symlink-state")
    with lock.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        current = build_plan(plan.source, plan.home, args.with_pi_subagents, env)
        if current.identity != plan.identity:
            raise Rejected("stale-plan")
        report, status = apply_plan(current, state, env)
    print(encoded(report).decode(), end="")
    return status


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Rejected as error:
        print(f"install: {error}", file=sys.stderr)
        raise SystemExit(error.status) from error
    except OSError as error:
        print(f"install: io-failed: {error.strerror}", file=sys.stderr)
        raise SystemExit(74) from error
    except KeyboardInterrupt:
        raise SystemExit(130) from None
