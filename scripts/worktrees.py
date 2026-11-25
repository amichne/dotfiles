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
"""Reclaim worktrees in explicitly named repositories."""

from __future__ import annotations

import sys
from pathlib import Path

import build_reclaim
from git_environment import git_environment

USAGE = """Usage: dotfiles reclaim --repo PATH [--repo PATH ...] [--config FILE] [--idle-days N]
                 [--remove-worktrees] [--apply] [--json]
"""


def main(argv: list[str]) -> int:
    if argv in ([], ["--help"], ["-h"], ["help"]):
        print(USAGE, end="")
        return 0
    if argv[0] == "reclaim":
        reclaim = build_reclaim.parse(
            argv[1:], Path(__file__).resolve().parents[1] / ".config/worktree-reclaim.toml"
        )
        if isinstance(reclaim, build_reclaim.Rejected):
            print(f"dotfiles: {reclaim.code}", file=sys.stderr)
            return 64
        return build_reclaim.run(reclaim, git_environment())
    print("dotfiles: invalid-command", file=sys.stderr)
    return 64


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except OSError as error:
        print(f"dotfiles: io-failed: {error.strerror}", file=sys.stderr)
        raise SystemExit(74) from error
    except KeyboardInterrupt:
        raise SystemExit(130) from None
