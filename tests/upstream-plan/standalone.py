#!/usr/bin/env -S uv run --locked --script
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["pytest==8.4.2"]
# [tool.uv]
# no-build = true
# required-version = ">=0.12.9"
# [[tool.uv.index]]
# name = "pypi"
# url = "https://pypi.org/simple"
# default = true
# ///
"""Git mechanism proofs for D2, without a manager implementation."""

from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Mapping

SOURCE_SHA = "6765d34a572b94f76592ef9dd0b0cdb5c9baac2b"
SOURCE = Path(__file__).resolve().parents[2]
PUBLIC_PATH = "plugins/core/evolution-proof.zsh"
CONFLICT_PATH = "profiles/personal.conf"
PRIVATE_PATH = ".enterprise/profile.toml"
PRIVATE_BYTES = b'[shell]\neditor = "enterprise-editor"\n'
PUBLIC_BYTES = b'print -r -- "portable addition"\n'


@dataclass(frozen=True, slots=True)
class _ObjectId:
    value: str


@dataclass(frozen=True, slots=True)
class InvalidGitOutput:
    pass


def parse_object_id(raw: bytes) -> _ObjectId | InvalidGitOutput:
    if re.fullmatch(rb"[0-9a-f]{40}", raw) is None:
        return InvalidGitOutput()
    return _ObjectId(raw.decode("ascii"))


class ConflictStage(StrEnum):
    BASE = "1"
    ENTERPRISE = "2"
    PUBLIC = "3"


@dataclass(frozen=True, slots=True)
class ConflictEntry:
    blob: _ObjectId
    stage: ConflictStage
    path: str


@dataclass(frozen=True, slots=True)
class MergedTree:
    tree: _ObjectId


@dataclass(frozen=True, slots=True)
class ConflictedTree:
    tree: _ObjectId
    first: ConflictEntry
    rest: tuple[ConflictEntry, ...]


type MergeEvidence = MergedTree | ConflictedTree | InvalidGitOutput


def parse_conflict(record: bytes) -> ConflictEntry | InvalidGitOutput:
    match = re.fullmatch(rb"100644 ([0-9a-f]{40}) ([123])\t([^\0]+)", record)
    if match is None:
        return InvalidGitOutput()
    blob = parse_object_id(match[1])
    if isinstance(blob, InvalidGitOutput):
        return blob
    try:
        path = match[3].decode("utf-8")
    except UnicodeDecodeError:
        return InvalidGitOutput()
    return ConflictEntry(blob, ConflictStage(match[2].decode("ascii")), path)


def parse_merge(status: int, raw: bytes) -> MergeEvidence:
    """Parse the pinned Git command's NUL protocol, never conflict-marker text."""
    fields = raw.split(b"\0")
    tree = parse_object_id(fields[0])
    if isinstance(tree, InvalidGitOutput) or fields[-1] != b"":
        return InvalidGitOutput()
    records = tuple(field for field in fields[1:-1] if field)
    if status == 0 and not records:
        return MergedTree(tree)
    if status != 1 or not records:
        return InvalidGitOutput()
    entries: list[ConflictEntry] = []
    for record in records:
        entry = parse_conflict(record)
        if isinstance(entry, InvalidGitOutput):
            return entry
        entries.append(entry)
    return ConflictedTree(tree, entries[0], tuple(entries[1:]))


@dataclass(frozen=True, slots=True)
class Git:
    """Effects stay in test-owned repositories with literal arguments."""

    root: Path
    environment: Mapping[str, str]
    metadata: Path | None = None

    def run(self, *arguments: str) -> subprocess.CompletedProcess[bytes]:
        prefix = ["/usr/bin/git", "--no-optional-locks", "-C", str(self.root)]
        if self.metadata is not None:
            prefix += [f"--git-dir={self.metadata}", f"--work-tree={self.root}"]
        return subprocess.run(
            [
                *prefix,
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "protocol.allow=never",
                "-c",
                "protocol.file.allow=always",
                *arguments,
            ],
            env=self.environment,
            capture_output=True,
            check=False,
            timeout=30,
        )

    def ok(self, *arguments: str) -> bytes:
        result = self.run(*arguments)
        assert result.returncode == 0, (arguments, result.returncode, result.stderr)
        return result.stdout

    def oid(self, expression: str) -> _ObjectId:
        parsed = parse_object_id(self.ok("rev-parse", expression).strip())
        assert not isinstance(parsed, InvalidGitOutput)
        return parsed

    def commit(self, path: str, contents: bytes) -> _ObjectId:
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        _ = destination.write_bytes(contents)
        _ = self.ok("add", "--force", "--", path)
        _ = self.ok("commit", "--quiet", "-m", f"Fixture: {path}")
        return self.oid("HEAD")


@dataclass(frozen=True, slots=True)
class Fixture:
    public: Git
    enterprise: Git

    def fetch(self) -> _ObjectId:
        _ = self.enterprise.ok("fetch", "--quiet", str(self.public.root), "HEAD")
        return self.enterprise.oid("FETCH_HEAD")


@pytest.fixture
def repositories(tmp_path: Path) -> Fixture:
    environment = {
        "HOME": str(tmp_path / "outer-home"),
        "PATH": os.defpath,
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_AUTHOR_NAME": "Fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z",
        "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
    }
    for suffix in ("CONFIG", "DATA", "STATE", "CACHE"):
        environment[f"XDG_{suffix}_HOME"] = str(tmp_path / suffix.lower())
    source = Git(SOURCE, environment)
    assert source.oid(f"{SOURCE_SHA}^{{commit}}").value == SOURCE_SHA
    public = Git(tmp_path / "public source with spaces", environment)
    _ = source.ok("clone", "--quiet", "--no-local", "--no-checkout", str(SOURCE), str(public.root))
    _ = public.ok("checkout", "--quiet", "--detach", SOURCE_SHA)
    home = tmp_path / "enterprise HOME with spaces"
    home.mkdir()
    enterprise = Git(home, {**environment, "HOME": str(home)}, home / ".cfg/repo.git")
    _ = public.ok(
        "clone", "--quiet", "--no-local", "--bare", str(public.root), str(enterprise.metadata)
    )
    _ = enterprise.ok("checkout", "--quiet", "-b", "enterprise", SOURCE_SHA)
    _ = enterprise.commit(PRIVATE_PATH, PRIVATE_BYTES)
    for path in (".pi/agent/auth.json", ".codex/sessions/private-sentinel"):
        target = home / path
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = target.write_bytes(b"test-owned private sentinel\n")
    return Fixture(public, enterprise)


@dataclass(frozen=True, slots=True)
class Snapshot:
    head: _ObjectId
    refs: bytes
    index: bytes
    files: tuple[tuple[str, int, bytes], ...]


def snapshot(git: Git) -> Snapshot:
    metadata = git.metadata or git.root / ".git"
    entries: list[tuple[str, int, bytes]] = []
    for directory, children, files in os.walk(git.root, followlinks=False):
        root = Path(directory)
        children[:] = sorted(child for child in children if root / child != metadata)
        for name in sorted([*children, *files]):
            path = root / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                content = os.fsencode(path.readlink())
            elif stat.S_ISREG(mode):
                content = hashlib.sha256(path.read_bytes()).digest()
            else:
                content = b""
            entries.append((path.relative_to(git.root).as_posix(), mode, content))
    return Snapshot(
        git.oid("HEAD"), git.ok("show-ref"), (metadata / "index").read_bytes(), tuple(entries)
    )


def merge(repositories: Fixture, upstream: _ObjectId) -> MergeEvidence:
    result = repositories.enterprise.run(
        "merge-tree",
        "--write-tree",
        "--no-messages",
        "-z",
        "HEAD",
        upstream.value,
    )
    return parse_merge(result.returncode, result.stdout)


def test_clean_addition_keeps_private_tree_and_destination(repositories: Fixture) -> None:
    public_head = repositories.public.commit(PUBLIC_PATH, PUBLIC_BYTES)
    enterprise = repositories.enterprise
    before = snapshot(enterprise)
    public_before = snapshot(repositories.public)
    upstream = repositories.fetch()
    assert upstream == public_head
    assert enterprise.ok("merge-base", "HEAD", upstream.value).strip() == SOURCE_SHA.encode()
    assert enterprise.ok("config", "--get", "core.bare") == b"true\n"
    outcome = merge(repositories, upstream)
    assert isinstance(outcome, MergedTree)
    assert enterprise.ok("show", f"{outcome.tree.value}:{PUBLIC_PATH}") == PUBLIC_BYTES
    assert enterprise.ok("show", f"{outcome.tree.value}:{PRIVATE_PATH}") == PRIVATE_BYTES
    assert snapshot(enterprise) == before
    assert snapshot(repositories.public) == public_before
    assert repositories.public.oid("HEAD") == public_head
    assert repositories.public.ok("diff", "--exit-code") == b""
    print(
        f"CLEAN_ADDITION source={SOURCE_SHA} public={upstream.value} "
        f"enterprise={before.head.value} tree={outcome.tree.value}"
    )


def test_conflict_reports_exact_stage_blobs_without_destination_writes(
    repositories: Fixture,
) -> None:
    enterprise = repositories.enterprise
    enterprise_head = enterprise.commit(CONFLICT_PATH, b"shell.editor=enterprise-editor\n")
    public_head = repositories.public.commit(CONFLICT_PATH, b"shell.editor=portable-editor\n")
    before = snapshot(enterprise)
    upstream = repositories.fetch()
    outcome = merge(repositories, upstream)
    assert isinstance(outcome, ConflictedTree)
    expected = (
        ConflictEntry(
            enterprise.oid(f"{SOURCE_SHA}:{CONFLICT_PATH}"), ConflictStage.BASE, CONFLICT_PATH
        ),
        ConflictEntry(
            enterprise.oid(f"{enterprise_head.value}:{CONFLICT_PATH}"),
            ConflictStage.ENTERPRISE,
            CONFLICT_PATH,
        ),
        ConflictEntry(
            enterprise.oid(f"{public_head.value}:{CONFLICT_PATH}"),
            ConflictStage.PUBLIC,
            CONFLICT_PATH,
        ),
    )
    assert (outcome.first, *outcome.rest) == expected
    assert snapshot(enterprise) == before
    print(
        f"PATH_CONFLICT source={SOURCE_SHA} public={public_head.value} "
        f"enterprise={enterprise_head.value} path={CONFLICT_PATH}"
    )


def test_staged_and_unstaged_work_survives_the_git_probe(repositories: Fixture) -> None:
    enterprise = repositories.enterprise
    staged = enterprise.root / "home/dot_config/atuin/config.toml"
    _ = staged.write_bytes(staged.read_bytes() + b"\n# unrelated staged edit\n")
    _ = enterprise.ok("add", "--", "home/dot_config/atuin/config.toml")
    dirty = enterprise.root / "README.md"
    _ = dirty.write_bytes(dirty.read_bytes() + b"\n# unrelated unstaged edit\n")
    _ = repositories.public.commit(PUBLIC_PATH, PUBLIC_BYTES)
    before = snapshot(enterprise)
    upstream = repositories.fetch()
    assert isinstance(merge(repositories, upstream), MergedTree)
    assert snapshot(enterprise) == before


@pytest.mark.parametrize("raw", [b"", b"HEAD", b"a" * 39, b"A" * 40, b"a" * 40 + b"\n"])
def test_object_identity_rejects_unresolved_or_malformed_input(raw: bytes) -> None:
    assert parse_object_id(raw) == InvalidGitOutput()


def test_merge_protocol_rejects_failure_and_incomplete_conflicts() -> None:
    tree = b"a" * 40 + b"\0"
    assert parse_merge(0, tree) == MergedTree(_ObjectId("a" * 40))
    assert parse_merge(1, tree) == InvalidGitOutput()
    assert parse_merge(128, tree) == InvalidGitOutput()
    assert parse_merge(0, tree + b"unrecognized\0") == InvalidGitOutput()


def main(arguments: list[str]) -> int:
    if arguments == ["--self-test"]:
        return int(pytest.main([str(Path(__file__).resolve()), "-q", "-o", "addopts="]))
    print("usage: standalone.py --self-test")
    return 0 if arguments in (["--help"], ["-h"]) else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
