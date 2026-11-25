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
"""Manage the shell layer from an ordinary checkout."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from git_environment import git_environment
from install_state import encoded
from layered import LayerConflict, layered_install
from migration import migrate

Reason = Literal[
    "git-failed",
    "invalid-source-repository",
    "not-source-root",
    "missing-dependency",
    "symlink-state",
]


class Rejected(Exception):
    """A named precondition failure or a native command failure."""

    def __init__(self, reason: Reason, detail: str = "", status: int = 65):
        super().__init__(f"{reason}:{detail}" if detail else reason)
        self.status = status


class Arguments(argparse.Namespace):
    migrate: bool
    uninstall: bool
    source: Path
    apply: bool
    expected_plan: str | None


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
class Source:
    worktree: Path
    repository: Path

    def arguments(self) -> list[str]:
        return [
            "-C",
            str(self.worktree),
            f"--git-dir={self.repository}",
            f"--work-tree={self.worktree}",
        ]


def open_source(worktree: Path, env: dict[str, str]) -> Source:
    if (worktree / ".git").is_symlink():
        raise Rejected("invalid-source-repository", "unsafe-metadata")
    discovery = ["-C", str(worktree)]
    root = Path(os.fsdecode(git(env, discovery, "rev-parse", "--show-toplevel")).strip())
    if root.resolve() != worktree:
        raise Rejected("not-source-root")
    metadata = Path(os.fsdecode(git(env, discovery, "rev-parse", "--absolute-git-dir")).strip())
    if not metadata.is_dir() or metadata.is_symlink() or metadata.resolve() != metadata:
        raise Rejected("invalid-source-repository", "unsafe-metadata")
    return Source(worktree, metadata)


def state_path(home: Path) -> Path:
    state = home / ".local/state/dotfiles-install"
    # Recovery receipts always stay under HOME, independent of an ambient XDG override.
    for parent in (state, *state.parents):
        if parent.is_symlink():
            raise Rejected("symlink-state")
        if parent == home:
            break
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--layered", action="store_true", help=argparse.SUPPRESS)
    action = parser.add_mutually_exclusive_group()
    _ = action.add_argument("--uninstall", action="store_true")
    _ = action.add_argument(
        "--migrate", action="store_true", help="convert the supported bare main"
    )
    _ = parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    _ = parser.add_argument("--apply", action="store_true")
    _ = parser.add_argument("--expected-plan")
    args = parser.parse_args(namespace=Arguments())
    if args.apply != (args.expected_plan is not None):
        parser.error("--apply and --expected-plan must appear together")
    env = {**git_environment(), "GIT_OPTIONAL_LOCKS": "0"}
    if shutil.which("git", path=env.get("PATH")) is None:
        raise Rejected("missing-dependency", "git", 69)
    home = Path.home().resolve()
    if not args.migrate and os.path.lexists(home / ".dotfiles.git"):
        raise LayerConflict(f"bare installation at {home / '.dotfiles.git'}; migration required")
    source = open_source(args.source.resolve(), env)
    if source.worktree == home or os.path.lexists(source.worktree / ".dotfiles.git"):
        raise LayerConflict("an ordinary source checkout is required")

    def revision() -> str:
        return git(env, source.arguments(), "rev-parse", "HEAD").decode().strip()

    if args.migrate:
        report = migrate(source.worktree, revision, home, state_path(home), env, args.expected_plan)
    else:
        report = layered_install(
            source.worktree,
            revision,
            home,
            state_path(home),
            args.uninstall,
            args.expected_plan,
        )
    print(encoded(report).decode(), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Rejected as error:
        print(f"install: {error}", file=sys.stderr)
        raise SystemExit(error.status) from error
    except LayerConflict as error:
        print(f"install: {error}", file=sys.stderr)
        raise SystemExit(65) from error
    except OSError as error:
        print(f"install: io-failed: {error.strerror}", file=sys.stderr)
        raise SystemExit(74) from error
    except KeyboardInterrupt:
        raise SystemExit(130) from None
