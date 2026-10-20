from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from .conftest import Home


def run(home: Home, *arguments: str, event: object = None) -> tuple[int, dict[str, object]]:
    result = subprocess.run(
        [sys.executable, str(home.path / ".config/agent-engineering/check.py"), *arguments],
        cwd=home.path,
        env=home.env,
        input=json.dumps(event) if event is not None else None,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return result.returncode, json.loads(result.stdout)


def initialize(home: Home) -> None:
    for arguments in (
        ("init", "-q"),
        ("config", "user.name", "Fixture"),
        ("config", "user.email", "fixture@example.invalid"),
        ("add", "-f", "README.md"),
        ("commit", "-qm", "initial"),
    ):
        result = home.run("/usr/bin/git", *arguments)
        assert result.returncode == 0, result.stderr


def configure(home: Home) -> Path:
    # Bounded fake validators prove orchestration only. Real validator qualification
    # uses the separate native fixture, with pinned Slopsentral and Vale inputs.
    owner = home.tools / "owner with spaces"
    scripts = owner / "scripts"
    scripts.mkdir(parents=True)
    assets = owner / "assets/vale"
    assets.mkdir(parents=True)
    _ = (assets / "resources.lock.json").write_text("{}")
    count = scripts / "count"
    _ = count.write_text("0")
    assessment = scripts / "assess.py"
    _ = assessment.write_text(
        "import json, pathlib, sys\n"
        "counter = pathlib.Path(__file__).with_name('count')\n"
        "counter.write_text(str(int(counter.read_text()) + 1))\n"
        "paths = sys.argv[3:]\n"
        "bad = any('BAD' in pathlib.Path(p).read_text() for p in paths)\n"
        "print(json.dumps({'type':'ASSESSED','schemaVersion':2,'documents':paths}))\n"
        "sys.exit(1 if bad else 0)\n"
    )
    kotlin = owner / "kotlin"
    _ = kotlin.write_text(
        "import json,sys\n"
        "print(json.dumps({'ok':True,'status':'advisory','findings':[], 'arguments':sys.argv[1:]}))\n"
    )
    _ = kotlin.with_name("kotlin.lock").write_text("fixture")
    vale = owner / "vale"
    _ = vale.write_text("fixture")
    code, report = run(
        home,
        "configure",
        "--kotlin",
        str(kotlin),
        "--assessment",
        str(assessment),
        "--vale",
        str(vale),
    )
    assert code == 0, report
    return owner


def start(home: Home) -> None:
    _ = (home.path / "README.md").write_text("Base.\n")
    initialize(home)
    assert run(home, "begin", "--session", "fixture")[0] == 0


def test_changed_dirty_files_commits_and_cached_failure(home: Home) -> None:
    _ = (home.path / "README.md").write_text("Base.\n")
    initialize(home)
    _ = (home.path / "README.md").write_text("Preexisting BAD prose.\n")
    owner = configure(home)
    assert run(home, "begin", "--session", "fixture")[0] == 0
    code, report = run(home, "turn", "--session", "fixture")
    assert code == 0 and report["status"] == "no-changes"
    _ = (home.path / "README.md").write_text("Changed BAD prose.\n")
    code, report = run(home, "turn", "--session", "fixture")
    assert code == 1 and report["status"] == "failed"
    count = owner / "scripts/count"
    assert count.read_text() == "1"
    for phase in ("begin", "turn", "handoff"):
        _ = run(home, phase, "--session", "fixture")
    assert count.read_text() == "1"
    assert run(home, "handoff", "--session", "fixture")[0] == 1
    assert run(home, "handoff", "--session", "fixture", "--retry")[0] == 1
    assert count.read_text() == "2"
    _ = (home.path / "README.md").write_text("Good prose.\n")
    assert home.run("/usr/bin/git", "commit", "-qam", "during session").returncode == 0
    assert run(home, "handoff", "--session", "fixture")[0] == 0
    assert count.read_text() == "3"
    assert run(home, "handoff", "--session", "fixture")[0] == 0
    assert count.read_text() == "3"


def test_missing_tool_invalid_output_and_recovery(home: Home) -> None:
    start(home)
    _ = (home.path / "README.md").write_text("New prose.\n")
    code, report = run(home, "handoff", "--session", "fixture")
    assert code == 1 and report["status"] == "failed"
    owner = configure(home)
    assessment = owner / "scripts/assess.py"
    original = assessment.read_text()
    _ = assessment.write_text("print('invalid')\n")
    assert run(home, "handoff", "--session", "fixture")[0] == 1
    _ = assessment.write_text(original)
    assert run(home, "handoff", "--session", "fixture")[0] == 0
    (owner / "vale").unlink()
    assert run(home, "handoff", "--session", "fixture")[0] == 1


def test_literal_paths_deletion_and_unrelated_scope(home: Home) -> None:
    start(home)
    _ = configure(home)
    name = "literal $(touch PWNED) ' document.md"
    _ = (home.path / name).write_text("Good prose.\n")
    assert home.run("/usr/bin/git", "add", "-f", name).returncode == 0
    code, report = run(home, "turn", "--session", "fixture")
    assert code == 0, report
    assert not (home.path / "PWNED").exists()
    assert name in json.dumps(report)
    assert ".config/agent-engineering/B0.md" not in json.dumps(report)
    (home.path / name).unlink()
    assert run(home, "handoff", "--session", "fixture")[1]["status"] == "no-changes"


def test_native_stop_failure_has_no_continuation_or_false_green(home: Home) -> None:
    start(home)
    _ = (home.path / "README.md").write_text("New prose.\n")
    event = {
        "hook_event_name": "Stop",
        "cwd": str(home.path),
        "session_id": "fixture",
        "stop_hook_active": True,
    }
    code, report = run(home, "codex", event=event)
    assert code == 0
    assert report["continue"] is False
    assert "failed" in str(report["stopReason"])
    assert "decision" not in report
    _ = configure(home)
    code, report = run(home, "codex", event=event)
    assert code == 0 and "continue" not in report
    assert run(home, "codex", event={})[1]["continue"] is False


def test_unstarted_session_and_outside_symlink_fail(home: Home) -> None:
    start(home)
    assert run(home, "handoff", "--session", "other")[0] == 1
    outside = home.path.parent / "outside.md"
    _ = outside.write_text("Private.\n")
    (home.path / "escape.md").symlink_to(outside)
    assert home.run("/usr/bin/git", "add", "-f", "escape.md").returncode == 0
    assert run(home, "turn", "--session", "fixture")[0] == 1
    assert outside.read_text() == "Private.\n"


def test_fresh_session_keeps_live_configuration_private(home: Home) -> None:
    start(home)
    secret = home.path / ".codex/config.toml"
    secret.parent.mkdir(exist_ok=True)
    _ = secret.write_text('model = "private-choice"\n')
    before = secret.read_bytes()
    assert run(home, "begin", "--session", "second")[0] == 0
    assert secret.read_bytes() == before
    assert not os.path.exists(home.path / ".codex/auth.json")


def test_input_change_during_check_cannot_cache_success(home: Home) -> None:
    start(home)
    owner = configure(home)
    _ = (home.path / "README.md").write_text("New prose.\n")
    script = owner / "scripts/assess.py"
    _ = script.write_text(
        "import json,pathlib,sys\n"
        "pathlib.Path(sys.argv[3]).write_text('Changed during assessment.')\n"
        "print(json.dumps({'type':'ASSESSED','schemaVersion':2,'documents':[{}]}))\n"
    )
    code, report = run(home, "turn", "--session", "fixture")
    assert code == 1 and "input-changed-during-check" in json.dumps(report)
    sessions = home.path / ".local/state/agent-engineering/sessions"
    assert list(sessions.glob("*/prose.json")) == []


def test_changed_ignore_scope_does_not_expand_to_unrelated_prose(home: Home) -> None:
    start(home)
    _ = (home.path / "private.md").write_text("Private BAD prose.\n")
    _ = (home.path / ".gitignore").write_text("!.gitignore\n!private.md\n")
    code, report = run(home, "turn", "--session", "fixture")
    assert code == 1 and "ignore-scope-changed" in str(report)
    assert "private.md" not in str(report)


def test_cancellation_kills_validator_and_does_not_cache_success(home: Home) -> None:
    start(home)
    owner = configure(home)
    _ = (home.path / "README.md").write_text("New prose.\n")
    script = owner / "scripts/assess.py"
    marker = script.with_name("child-pid")
    _ = script.write_text(
        "import os,pathlib,time\n"
        "pathlib.Path(__file__).with_name('child-pid').write_text(str(os.getpid()))\n"
        "time.sleep(30)\n"
    )
    with subprocess.Popen(
        [
            sys.executable,
            str(home.path / ".config/agent-engineering/check.py"),
            "turn",
            "--session",
            "fixture",
        ],
        cwd=home.path,
        env=home.env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as process:
        for _ in range(100):
            if marker.exists():
                break
            time.sleep(0.02)
        assert marker.exists()
        process.terminate()
        stdout, _ = process.communicate(timeout=5)
        assert json.loads(stdout)["status"] == "failed"
    child_alive = True
    try:
        os.kill(int(marker.read_text()), 0)
    except ProcessLookupError:
        child_alive = False
    assert child_alive is False
    assert list((home.path / ".local/state/agent-engineering/sessions").glob("*/prose.json")) == []
