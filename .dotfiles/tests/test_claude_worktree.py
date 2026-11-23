from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.test_main import SOURCE, git

FAKE_WT = """#!/bin/sh
printf '%s\\n' "$@" > "$WT_LOG"
printf '%s\\n' "$WORKTRUNK_WORKTREE_PATH" > "$WT_LOG.template"
[ "$WT_MODE" != fail ] || exit 9
mkdir -p "$WT_DESTINATION"
[ "$WT_MODE" != garbage ] || { echo nonsense; exit 0; }
printf '{"action":"created","path":"%s"}\\n' "$WT_DESTINATION"
"""


@dataclass(frozen=True)
class Fixture:
    path: Path
    checkout: Path
    remote: Path
    fresh: str
    env: dict[str, str]

    def create(
        self, name: str, *, cwd: Path | None = None, mode: str = "ok"
    ) -> subprocess.CompletedProcess[str]:
        payload = {
            "hook_event_name": "WorktreeCreate",
            "cwd": str(cwd or self.checkout),
            "name": name,
        }
        return self.run(json.dumps(payload), mode)

    def run(self, payload: str, mode: str = "ok") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(SOURCE / ".local/bin/claude-worktree")],
            input=payload,
            env={**self.env, "WT_MODE": mode},
            capture_output=True,
            text=True,
            check=False,
        )

    def arguments(self) -> list[str]:
        return (self.path / "wt.log").read_text().splitlines()

    def template(self) -> str:
        return (self.path / "wt.log.template").read_text().strip()


@pytest.fixture
def fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Fixture:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    remote, source, checkout = (tmp_path / n for n in ("remote", "source", "checkout"))
    _ = git(tmp_path, "init", "--bare", "-b", "main", str(remote))
    _ = git(tmp_path, "clone", str(remote), str(source))
    _ = git(source, "config", "user.email", "fixture@example.com")
    _ = git(source, "config", "user.name", "Fixture")
    _ = git(source, "switch", "-C", "main")
    _ = git(source, "commit", "--allow-empty", "-m", "initial")
    _ = git(source, "push", "origin", "main")
    _ = git(tmp_path, "clone", str(remote), str(checkout))
    _ = git(source, "commit", "--allow-empty", "-m", "fresh remote tip")
    _ = git(source, "push", "origin", "main")
    tools = tmp_path / "tools"
    tools.mkdir()
    _ = (tools / "wt").write_text(FAKE_WT)
    (tools / "wt").chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{tools}:{os.environ['PATH']}",
        "WT_LOG": str(tmp_path / "wt.log"),
        "WT_DESTINATION": str(tmp_path / "created"),
        "WORKTRUNK_WORKTREE_PATH": "/root/{{ remote_repo }}/{{ branch | sanitize }}",
    }
    return Fixture(tmp_path, checkout, remote, git(source, "rev-parse", "HEAD"), env)


def test_new_worktree_starts_from_the_fetched_remote_default(fixture: Fixture) -> None:
    stale = git(fixture.checkout, "rev-parse", "main")
    result = fixture.create("bridge-cse_1")
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{fixture.path / 'created'}\n"
    assert fixture.arguments() == [
        "switch",
        "--no-cd",
        "--format",
        "json",
        "--create",
        "--base",
        fixture.fresh,
        "bridge-cse_1",
    ]
    assert fixture.template() == "/root/{{ remote_repo }}/{{ branch | sanitize }}"
    assert git(fixture.checkout, "rev-parse", "main") == stale != fixture.fresh


def test_existing_branch_is_not_recreated(fixture: Fixture) -> None:
    _ = git(fixture.checkout, "branch", "existing")
    result = fixture.create("existing")
    assert result.returncode == 0, result.stderr
    assert fixture.arguments() == ["switch", "--no-cd", "--format", "json", "existing"]


def test_failed_fetch_uses_the_last_fetched_commit(fixture: Fixture) -> None:
    last = git(fixture.checkout, "rev-parse", "origin/main")
    _ = git(fixture.checkout, "remote", "set-url", "origin", str(fixture.path / "missing"))
    result = fixture.create("offline")
    assert result.returncode == 0, result.stderr
    assert "reason=fetch-failed" in result.stderr
    assert fixture.arguments()[-2:] == [last, "offline"]


def test_repository_without_a_remote_uses_its_directory_name(fixture: Fixture) -> None:
    _ = git(fixture.checkout, "remote", "remove", "origin")
    result = fixture.create("local")
    assert result.returncode == 0, result.stderr
    assert "reason=no-origin-head" in result.stderr
    assert "--base" not in fixture.arguments()
    assert fixture.template() == "/root/{{ repo }}/{{ branch | sanitize }}"


@pytest.mark.parametrize("name", ["", "-", "--create", "@{-1}", "a..b", "a b"])
def test_invalid_name_never_reaches_worktrunk(fixture: Fixture, name: str) -> None:
    result = fixture.create(name)
    assert result.returncode == 1
    assert result.stdout == ""
    assert "outcome=invalid-name" in result.stderr
    assert not (fixture.path / "wt.log").exists()


@pytest.mark.parametrize("payload", ["", "[]", "{}", '{"hook_event_name":"WorktreeRemove"}'])
def test_invalid_payload_is_rejected(fixture: Fixture, payload: str) -> None:
    result = fixture.run(payload)
    assert result.returncode == 1
    assert result.stdout == ""
    assert "outcome=invalid-payload" in result.stderr


@pytest.mark.parametrize(
    ("mode", "outcome"), [("fail", "switch-failed"), ("garbage", "invalid-result")]
)
def test_worktrunk_failure_prints_no_path(fixture: Fixture, mode: str, outcome: str) -> None:
    result = fixture.create("task", mode=mode)
    assert result.returncode == 1
    assert result.stdout == ""
    assert f"outcome={outcome}" in result.stderr


@pytest.mark.parametrize(
    ("inside", "arguments", "expected"),
    [
        (
            True,
            ["--name", "x"],
            ["--spawn", "worktree", "--no-create-session-in-dir", "--name", "x"],
        ),
        (True, ["--continue"], ["--continue"]),
        (True, ["--session-id", "1"], ["--session-id", "1"]),
        (True, ["--spawn=same-dir"], ["--spawn=same-dir"]),
        (False, [], []),
    ],
)
def test_claude_rc_arguments(
    fixture: Fixture, inside: bool, arguments: list[str], expected: list[str]
) -> None:
    claude = fixture.path / "tools/claude"
    _ = claude.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    claude.chmod(0o755)
    outside = fixture.path / "outside"
    outside.mkdir()
    result = subprocess.run(
        [
            "zsh",
            "-f",
            "-c",
            'fpath=("$SOURCE/.config/zsh/functions" $fpath); autoload -Uz claude-rc; claude-rc "$@"',
            "fixture",
            *arguments,
        ],
        cwd=fixture.checkout if inside else outside,
        env={
            **fixture.env,
            "SOURCE": str(SOURCE),
            "GIT_CEILING_DIRECTORIES": str(fixture.path),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["remote-control", *expected]
    assert ("not in a Git worktree" in result.stderr) != inside
