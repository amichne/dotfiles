#!/usr/bin/env -S uv run --locked --script
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = []
# [tool.uv]
# no-build = true
# [[tool.uv.index]]
# name = "pypi"
# url = "https://pypi.org/simple"
# default = true
# ///
"""Manage selected HOME files in the amichne/dotfiles bare repository."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import assert_never

ORIGINS = frozenset(
    {
        "git@github.com:amichne/dotfiles.git",
        "https://github.com/amichne/dotfiles.git",
        "https://github.com/amichne/dotfiles",
        "ssh://git@github.com/amichne/dotfiles.git",
    }
)
REQUIRED = (
    ".zshrc",
    ".zprofile",
    ".local/bin/df",
    ".local/bin/keys",
    ".local/bin/keys.lock",
    ".local/bin/shell-prompt",
    "scripts/df.py",
    "scripts/df.py.lock",
)
USAGE = """Usage: df status [args] | diff [args] | add PATH... | commit [args]
       df git <git arguments> | setup plan [--json]
All operations use ~/.dotfiles.git with HOME as the worktree.
"""


class Reason(StrEnum):
    MISSING_REPOSITORY = "missing-repository"
    NOT_BARE = "not-bare"
    UNEXPECTED_ORIGIN = "unexpected-origin"
    OUTSIDE_HOME = "outside-home"
    NAMED_PATH_NEEDED = "named-path-needed"
    INVALID_COMMAND = "invalid-command"


@dataclass(frozen=True, slots=True)
class Failure:
    reason: Reason


@dataclass(frozen=True, slots=True)
class _GitCall:
    first: str
    rest: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Plan:
    json: bool


@dataclass(frozen=True, slots=True)
class _Help:
    pass


@dataclass(frozen=True, slots=True)
class _BareHome:
    home: Path
    metadata: Path
    origin: str

    def arguments(self, call: _GitCall) -> list[str]:
        return [
            "git",
            f"--git-dir={self.metadata}",
            f"--work-tree={self.home}",
            call.first,
            *call.rest,
        ]


def git_environment() -> dict[str, str]:
    removed = {
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_COMMON_DIR",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_NAMESPACE",
        "GIT_CONFIG",
        "GIT_CONFIG_PARAMETERS",
        "GIT_CONFIG_COUNT",
        "GIT_IMPLICIT_WORK_TREE",
    }
    return {
        key: value
        for key, value in os.environ.items()
        if key not in removed and not key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))
    }


def open_home(home: Path, env: dict[str, str]) -> _BareHome | Failure:
    metadata = home / ".dotfiles.git"
    if not metadata.is_dir() or metadata.is_symlink():
        return Failure(Reason.MISSING_REPOSITORY)
    base = ["git", f"--git-dir={metadata}"]
    bare = subprocess.run(
        [*base, "rev-parse", "--is-bare-repository"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if bare.returncode or bare.stdout.strip() != "true":
        return Failure(Reason.NOT_BARE)
    origin = subprocess.run(
        [*base, "remote", "get-url", "origin"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if origin.returncode or origin.stdout.strip() not in ORIGINS:
        return Failure(Reason.UNEXPECTED_ORIGIN)
    return _BareHome(home, metadata, origin.stdout.strip())


def named_paths(home: Path, first: str, rest: list[str]) -> _GitCall | Failure:
    result: list[str] = []
    for value in (first, *rest):
        path = Path(value)
        candidate = path if path.is_absolute() else home / path
        if ".." in path.parts or not candidate.is_relative_to(home):
            return Failure(Reason.OUTSIDE_HOME)
        relative = candidate.relative_to(home)
        if not relative.parts or relative.parts[0] == ".dotfiles.git":
            return Failure(Reason.NAMED_PATH_NEEDED)
        if not candidate.resolve().is_relative_to(home):
            return Failure(Reason.OUTSIDE_HOME)
        result.append(str(relative))
    return _GitCall("--literal-pathspecs", ("add", "--", *result))


def parse(argv: list[str], home: Path) -> _GitCall | _Plan | _Help | Failure:
    match argv:
        case [] | ["help" | "-h" | "--help"]:
            return _Help()
        case ["setup", "plan"]:
            return _Plan(json=False)
        case ["setup", "plan", "--json"]:
            return _Plan(json=True)
        case ["add", first, *rest]:
            return named_paths(home, first, rest)
        case ["status" | "diff" | "commit" as operation, *rest]:
            return _GitCall(operation, tuple(rest))
        case ["git", first, *rest]:
            return _GitCall(first, tuple(rest))
        case _:
            return Failure(Reason.INVALID_COMMAND)


def plan(repository: _BareHome, env: dict[str, str], operation: _Plan) -> int:
    status = subprocess.run(
        repository.arguments(_GitCall("status", ("--porcelain=v1", "--untracked-files=no"))),
        env={**env, "GIT_OPTIONAL_LOCKS": "0"},
        cwd=repository.home,
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode:
        return status.returncode
    missing = [path for path in REQUIRED if not (repository.home / path).is_file()]
    report = {
        "repository": str(repository.metadata),
        "worktree": str(repository.home),
        "origin": repository.origin,
        "missing": missing,
        "status": status.stdout,
    }
    if operation.json:
        print(json.dumps(report))
    else:
        print(
            f"Repository: {repository.metadata}\nWorktree: {repository.home}\nOrigin: {repository.origin}"
        )
        for path in missing:
            print(f"Missing: {path}")
        print(status.stdout, end="")
    return 65 if missing else 0


def main(argv: list[str]) -> int:
    home = Path.home().resolve()
    operation = parse(argv, home)
    if isinstance(operation, Failure):
        print(f"df: {operation.reason}", file=sys.stderr)
        return 64
    if isinstance(operation, _Help):
        print(USAGE, end="")
        return 0
    env = git_environment()
    opened = open_home(home, env)
    if isinstance(opened, Failure):
        print(f"df: {opened.reason}", file=sys.stderr)
        return 65
    match operation:
        case _Plan():
            return plan(opened, env, operation)
        case _GitCall():
            return subprocess.run(
                opened.arguments(operation), env=env, cwd=home, check=False
            ).returncode
        case _:
            assert_never(operation)


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except OSError as error:
        print(f"df: io-failed: {error.strerror}", file=sys.stderr)
        raise SystemExit(74) from error
    except KeyboardInterrupt:
        raise SystemExit(130) from None
