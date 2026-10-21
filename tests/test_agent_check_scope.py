from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .conftest import Home
from .test_agent_checks import configure


def invoke(home: Home, *arguments: str) -> subprocess.CompletedProcess[str]:
    return home.run(
        sys.executable, str(home.path / ".config/agent-engineering/check.py"), *arguments
    )


def forbid_git(home: Home) -> Path:
    log = home.path.parent / "git-invocations"
    home.env["GIT_INVOCATION_LOG"] = str(log)
    tool = home.tools / "git"
    _ = tool.write_text('#!/bin/sh\nprintf invoked >> "$GIT_INVOCATION_LOG"\nexit 97\n')
    tool.chmod(0o755)
    return log


def test_lifecycle_never_invokes_git(home: Home) -> None:
    _ = configure(home)
    (home.path / ".git").mkdir()
    log = forbid_git(home)
    for phase in ("begin", "turn", "handoff"):
        result = invoke(home, phase, "--session", "no-git")
        assert result.returncode == 0, result.stdout + result.stderr
        report = json.loads(result.stdout)
        assert report["status"] == "not-applicable"
        assert report["reason"] == "no-explicit-files"
    assert not log.exists()


def test_explicit_scope_needs_no_git_or_start_and_excludes_unnamed_files(home: Home) -> None:
    owner = configure(home)
    log = forbid_git(home)
    _ = (home.path / "README.md").write_text("Good prose.\n")
    _ = (home.path / "private.md").write_text("BAD private prose.\n")
    result = invoke(home, "handoff", "--session", "explicit", "--file", "README.md")
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "passed"
    assert "private.md" not in result.stdout
    assert not log.exists()
    _ = (home.path / ".gitignore").write_text("*\n")
    result = invoke(home, "handoff", "--session", "explicit")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["checks"]["prose"]["cached"] is True
    assert (owner / "scripts/count").read_text() == "1"


def test_explicit_failure_survives_native_stop_without_git(home: Home) -> None:
    _ = configure(home)
    log = forbid_git(home)
    _ = (home.path / "README.md").write_text("BAD prose.\n")
    result = invoke(home, "handoff", "--session", "native", "--file", "README.md")
    assert result.returncode == 1, result.stdout + result.stderr
    result = subprocess.run(
        [sys.executable, str(home.path / ".config/agent-engineering/check.py"), "codex"],
        cwd=home.path,
        env=home.env,
        capture_output=True,
        text=True,
        check=False,
        input=json.dumps(
            {"hook_event_name": "Stop", "cwd": str(home.path), "session_id": "native"}
        ),
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["continue"] is False
    assert not log.exists()


def test_rejected_explicit_path_cannot_invoke_a_validator(home: Home) -> None:
    owner = configure(home)
    log = forbid_git(home)
    outside = home.path.parent / "private.md"
    _ = outside.write_text("Private.\n")
    for name in (str(outside), "../private.md", ".", ".codex/config.toml"):
        result = invoke(home, "handoff", "--session", "rejected", "--file", name)
        assert result.returncode == 1, result.stdout + result.stderr
    assert (owner / "scripts/count").read_text() == "0"
    assert not log.exists()
    assert outside.read_text() == "Private.\n"
