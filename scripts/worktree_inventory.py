"""Read registered worktrees without changing source, indexes, or registrations."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal


class Code(StrEnum):
    INVALID_ARGUMENTS = "invalid-arguments"
    INVALID_CONFIG = "invalid-config"
    GIT_FAILED = "git-failed"
    DEADLINE = "deadline-exceeded"
    OUTPUT_LIMIT = "output-limit"
    WORKTREE_LIMIT = "worktree-limit"
    INVALID_RECORD = "invalid-worktree-record"
    MISSING = "missing"
    BARE = "bare"


@dataclass(frozen=True)
class Rejected:
    code: Code


@dataclass(frozen=True)
class Request:
    repositories: tuple[Path, ...]
    config: Path
    json: bool


@dataclass(frozen=True)
class Limits:
    max_worktrees: int
    timeout_seconds: int


@dataclass(frozen=True)
class Registration:
    path: Path
    head: str
    branch: str
    kind: Literal["branch", "detached", "bare"]
    locked: bool
    prunable: bool


@dataclass(frozen=True)
class Clean:
    pass


@dataclass(frozen=True)
class Changed:
    tracked: bool
    untracked: bool


@dataclass(frozen=True)
class Inspected:
    registration: Registration
    state: Clean | Changed | Rejected


@dataclass(frozen=True)
class Repository:
    path: Path
    worktrees: tuple[Inspected, ...]
    failures: tuple[Code, ...]


def parse(arguments: list[str], default_config: Path) -> Request | Rejected:
    repositories: list[Path] = []
    config = default_config
    json_output = False
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        index += 1
        if argument == "--json" and not json_output:
            json_output = True
        elif argument in {"--repo", "--config"} and index < len(arguments):
            value = arguments[index]
            index += 1
            if not value or value.startswith("--"):
                return Rejected(Code.INVALID_ARGUMENTS)
            if argument == "--repo":
                path = Path(value).absolute()
                if path not in repositories:
                    repositories.append(path)
            else:
                config = Path(value)
        else:
            return Rejected(Code.INVALID_ARGUMENTS)
    if not repositories or len(repositories) > 8:
        return Rejected(Code.INVALID_ARGUMENTS)
    return Request(tuple(repositories), config, json_output)


def read_limits(path: Path) -> Limits | Rejected:
    try:
        if path.stat().st_size > 4096:
            return Rejected(Code.INVALID_CONFIG)
        raw = tomllib.loads(path.read_text())
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        return Rejected(Code.INVALID_CONFIG)
    maximum: object = raw.get("max_worktrees")
    timeout: object = raw.get("timeout_seconds")
    if (
        set(raw) != {"max_worktrees", "timeout_seconds"}
        or type(maximum) is not int
        or not 1 <= maximum <= 512
        or type(timeout) is not int
        or not 1 <= timeout <= 120
    ):
        return Rejected(Code.INVALID_CONFIG)
    return Limits(maximum, timeout)


def registrations(raw: bytes) -> tuple[Registration, ...] | Rejected:
    rows: list[Registration] = []
    for record in raw.split(b"\0\0"):
        if not record:
            continue
        fields: dict[str, str] = {}
        for raw_field in record.split(b"\0"):
            key, _, value = os.fsdecode(raw_field).partition(" ")
            if key in fields or key not in {
                "worktree",
                "HEAD",
                "branch",
                "detached",
                "bare",
                "locked",
                "prunable",
            }:
                return Rejected(Code.INVALID_RECORD)
            fields[key] = value
        path = Path(fields.get("worktree", ""))
        head, branch = fields.get("HEAD", ""), fields.get("branch", "")
        kind: Literal["branch", "detached", "bare"]
        if "bare" in fields and not {"HEAD", "branch", "detached"}.intersection(fields):
            kind = "bare"
        elif re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", head):
            if branch.startswith("refs/heads/") and "detached" not in fields:
                kind = "branch"
            elif "detached" in fields and not branch:
                kind = "detached"
            else:
                return Rejected(Code.INVALID_RECORD)
        else:
            return Rejected(Code.INVALID_RECORD)
        if not path.is_absolute():
            return Rejected(Code.INVALID_RECORD)
        rows.append(
            Registration(path, head, branch, kind, "locked" in fields, "prunable" in fields)
        )
    return tuple(rows) if rows else Rejected(Code.INVALID_RECORD)


def working_state(raw: bytes) -> Clean | Changed | Rejected:
    tracked = untracked = False
    fields = raw.split(b"\0")
    index = 0
    while index < len(fields) and fields[index]:
        entry = fields[index]
        index += 1
        if len(entry) < 4 or entry[2:3] != b" ":
            return Rejected(Code.INVALID_RECORD)
        if entry[:2] == b"??":
            untracked = True
        else:
            tracked = True
            if b"R" in entry[:2] or b"C" in entry[:2]:
                if index >= len(fields) or not fields[index]:
                    return Rejected(Code.INVALID_RECORD)
                index += 1
    return Changed(tracked, untracked) if tracked or untracked else Clean()


@dataclass(frozen=True)
class GitReader:
    environment: dict[str, str]
    deadline: float

    def read(self, root: Path, *arguments: str) -> bytes | Rejected:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            return Rejected(Code.DEADLINE)
        try:
            result = subprocess.run(
                [
                    "git",
                    "--no-optional-locks",
                    "-c",
                    "core.fsmonitor=false",
                    "-c",
                    "core.untrackedCache=false",
                    "-C",
                    str(root),
                    *arguments,
                ],
                env={**self.environment, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"},
                capture_output=True,
                timeout=remaining,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return Rejected(Code.DEADLINE)
        except OSError:
            return Rejected(Code.GIT_FAILED)
        if result.returncode:
            return Rejected(Code.GIT_FAILED)
        return (
            result.stdout if len(result.stdout) <= 4 * 1024 * 1024 else Rejected(Code.OUTPUT_LIMIT)
        )


def inspect_repository(root: Path, reader: GitReader, remaining: int) -> Repository:
    listed = reader.read(root, "worktree", "list", "--porcelain", "-z")
    parsed = listed if isinstance(listed, Rejected) else registrations(listed)
    if isinstance(parsed, Rejected):
        return Repository(root, (), (parsed.code,))
    failures: list[Code] = [Code.WORKTREE_LIMIT] if len(parsed) > remaining else []
    inspected: list[Inspected] = []
    for registration in parsed[:remaining]:
        if registration.kind == "bare":
            state: Clean | Changed | Rejected = Rejected(Code.BARE)
        elif not registration.path.is_dir():
            state = Rejected(Code.MISSING)
        else:
            status = reader.read(
                registration.path,
                "status",
                "--porcelain=v1",
                "-z",
                "--untracked-files=normal",
                "--ignore-submodules=none",
            )
            state = status if isinstance(status, Rejected) else working_state(status)
            if isinstance(state, Rejected):
                failures.append(state.code)
        inspected.append(Inspected(registration, state))
    return Repository(root, tuple(inspected), tuple(dict.fromkeys(failures)))


def encode_worktree(item: Inspected) -> dict[str, object]:
    registration = item.registration
    reasons = ["activity-unproved", "delivery-unproved"]
    if registration.locked:
        reasons.append("locked")
    if registration.prunable:
        reasons.append("prunable")
    match item.state:
        case Clean():
            state: dict[str, object] = {"kind": "clean"}
        case Changed(tracked, untracked):
            state = {"kind": "changed", "tracked": tracked, "untracked": untracked}
            if tracked:
                reasons.append("dirty")
            if untracked:
                reasons.append("untracked")
        case Rejected(code):
            state = {"kind": "unavailable", "reason": code.value}
            reasons.append(code.value)
    return {
        "path": str(registration.path),
        "head": registration.head or None,
        "branch": registration.branch or None,
        "kind": registration.kind,
        "locked": registration.locked,
        "prunable": registration.prunable,
        "workingState": state,
        "decision": "retain",
        "reasons": reasons,
    }


def run(request: Request, environment: dict[str, str]) -> int:
    limits = read_limits(request.config)
    if isinstance(limits, Rejected):
        report: dict[str, object] = {
            "version": 1,
            "status": "incomplete",
            "failure": limits.code.value,
            "repositories": [],
        }
        failed = True
    else:
        reader = GitReader(environment, time.monotonic() + limits.timeout_seconds)
        rows: list[dict[str, object]] = []
        remaining = limits.max_worktrees
        failed = False
        for path in request.repositories:
            result = inspect_repository(path, reader, remaining)
            remaining -= len(result.worktrees)
            failed = failed or bool(result.failures)
            rows.append(
                {
                    "requestedPath": str(result.path),
                    "status": "incomplete" if result.failures else "complete",
                    "failure": result.failures[0].value if result.failures else None,
                    "failures": [failure.value for failure in result.failures],
                    "worktrees": [encode_worktree(item) for item in result.worktrees],
                }
            )
        report = {
            "version": 1,
            "status": "incomplete" if failed else "complete",
            "policy": {
                "action": "retain",
                "maxWorktrees": limits.max_worktrees,
                "timeoutSeconds": limits.timeout_seconds,
            },
            "repositories": rows,
        }
    if request.json:
        print(json.dumps(report, ensure_ascii=True))
    else:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    return 1 if failed else 0
