from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from .conftest import Home


def run(home: Home, *arguments: str, event: object = None) -> tuple[int, dict[str, object]]:
    result = subprocess.run(
        [
            sys.executable,
            os.environ.get(
                "DOTFILES_TEST_AGENT_CHECK", str(home.path / ".config/agent-engineering/check.py")
            ),
            *arguments,
        ],
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
    references = owner / "references"
    references.mkdir()
    _ = (references / "text-assessment.schema.json").write_bytes(
        (Path(__file__).parent / "fixtures/text-assessment.schema.json").read_bytes()
    )
    count = scripts / "count"
    _ = count.write_text("0")
    assessment = scripts / "assess.py"
    _ = assessment.write_text(
        "import hashlib, json, pathlib, sys\n"
        "counter = pathlib.Path(__file__).with_name('count')\n"
        "counter.write_text(str(int(counter.read_text()) + 1))\n"
        "paths = sys.argv[3:]\n"
        "bad = any('BAD' in pathlib.Path(p).read_text() for p in paths)\n"
        "finding = {'type':'FINDING','category':'DICTION','rule':'Slopsentral.Modals','severity':'warning','line':1,'span':[1,3],'message':'Fixture finding.'}\n"
        "documents = [{'type':'DOCUMENT_ASSESSMENT','path':p,'sourceSha256':hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest(),'metrics':{'words':4,'sentences':1,'estimatedSyllables':4,'wordsPerSentence':4.0,'fleschKincaidGrade':-2.23},'findings':[finding] if bad else []} for p in paths]\n"
        "print(json.dumps({'type':'ASSESSED','schemaVersion':2,'engine':{'type':'VALE','version':'3.24.0','policySha256':hashlib.sha256(b'{}').hexdigest()},'comprehension':{'type':'NOT_ASSESSED'},'documents':documents}))\n"
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


def test_ignored_nested_ignore_cannot_discharge_failed_file(home: Home) -> None:
    _ = (home.path / "README.md").write_text("Base.\n")
    initialize(home)
    _ = (home.path / ".gitignore").write_text("sub/.gitignore\n")
    nested = home.path / "sub"
    nested.mkdir()
    owner = configure(home)
    assert run(home, "begin", "--session", "fixture")[0] == 0
    source = nested / "new.md"
    _ = source.write_text("BAD prose.\n")
    assert run(home, "handoff", "--session", "fixture")[0] == 1
    _ = (nested / ".gitignore").write_text("new.md\n")
    code, report = run(home, "handoff", "--session", "fixture")
    assert code == 1 and report["status"] == "failed", report
    assert "scope" in str(report)
    assert (owner / "scripts/count").read_text() == "1"
    _ = (nested / ".gitignore").write_text("")
    assert run(home, "handoff", "--session", "fixture")[0] == 1
    (nested / ".gitignore").unlink()
    assert run(home, "handoff", "--session", "fixture")[0] == 1
    _ = source.write_text("Good prose.\n")
    assert run(home, "handoff", "--session", "fixture")[0] == 0


def test_projectless_native_is_not_applicable_and_explicit_check_fails(home: Home) -> None:
    for event in ("SessionStart", "Stop"):
        code, report = run(
            home,
            "codex",
            event={"hook_event_name": event, "cwd": str(home.path), "session_id": "projectless"},
        )
        assert code == 0 and "continue" not in report, report
        assert "not-applicable" in str(report) and "outside-repository" in str(report)
        assert "unavailable" not in str(report)
    for command in ("begin", "handoff"):
        code, report = run(home, command, "--session", "projectless")
        assert code == 1 and report["status"] == "failed"


@pytest.mark.parametrize(
    "mutation",
    [
        "incomplete",
        "missing-engine",
        "wrong-version",
        "missing-metrics",
        "extra-document-field",
        "wrong-path",
        "wrong-digest",
        "missing-document",
        "duplicate-document",
        "findings-exit-zero",
        "empty-findings-exit-one",
        "bad-finding",
        "nonfinite-metric",
        "wrong-policy",
    ],
)
def test_malformed_assessment_never_passes_or_reuses_success(home: Home, mutation: str) -> None:
    start(home)
    owner = configure(home)
    document = home.path / "README.md"
    _ = document.write_text("New prose.\n")
    assert run(home, "turn", "--session", "fixture")[0] == 0
    other = home.path / "second.md"
    _ = other.write_text("More prose.\n")
    assert home.run("/usr/bin/git", "add", "-f", "second.md").returncode == 0
    documents: list[dict[str, object]] = [
        {
            "type": "DOCUMENT_ASSESSMENT",
            "path": str(path),
            "sourceSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "metrics": {
                "words": 4,
                "sentences": 1,
                "estimatedSyllables": 4,
                "wordsPerSentence": 4,
                "fleschKincaidGrade": -2.23,
            },
            "findings": [],
        }
        for path in (document, other)
    ]
    payload: dict[str, object] = {
        "type": "ASSESSED",
        "schemaVersion": 2,
        "engine": {
            "type": "VALE",
            "version": "3.24.0",
            "policySha256": hashlib.sha256(b"{}").hexdigest(),
        },
        "comprehension": {"type": "NOT_ASSESSED"},
        "documents": documents,
    }
    # Typed JSON mutation fixtures are external protocol inputs, independent of the parser.
    first = dict(documents[0])
    exit_code = 0
    if mutation == "incomplete":
        payload = {"type": "ASSESSED", "schemaVersion": 2, "documents": [{}]}
    elif mutation == "missing-engine":
        _ = payload.pop("engine")
    elif mutation == "wrong-version":
        payload["engine"] = {"type": "VALE", "version": "0", "policySha256": "0" * 64}
    elif mutation == "missing-metrics":
        del first["metrics"]
    elif mutation == "extra-document-field":
        first["surprise"] = True
    elif mutation == "wrong-path":
        first["path"] = str(home.path / "unselected.md")
    elif mutation == "wrong-digest":
        first["sourceSha256"] = "0" * 64
    elif mutation == "missing-document":
        _ = documents.pop()
    elif mutation == "duplicate-document":
        documents[1] = first
    elif mutation == "findings-exit-zero":
        first["findings"] = [
            {
                "type": "FINDING",
                "category": "DICTION",
                "rule": "Slopsentral.Modals",
                "severity": "warning",
                "line": 1,
                "span": [1, 3],
                "message": "Fixture finding.",
            }
        ]
    elif mutation == "empty-findings-exit-one":
        exit_code = 1
    elif mutation == "bad-finding":
        first["findings"] = [{}]
        exit_code = 1
    elif mutation == "nonfinite-metric":
        first["metrics"] = {
            "words": 4,
            "sentences": 1,
            "estimatedSyllables": 4,
            "wordsPerSentence": 4,
            "fleschKincaidGrade": float("nan"),
        }
    elif mutation == "wrong-policy":
        payload["engine"] = {"type": "VALE", "version": "3.24.0", "policySha256": "0" * 64}
    documents[0] = first
    script = owner / "scripts/assess.py"
    _ = script.write_text(
        "import sys\nprint(" + repr(json.dumps(payload)) + ")\nsys.exit(" + str(exit_code) + ")\n"
    )
    for _ in range(2):
        code, report = run(home, "handoff", "--session", "fixture")
        assert code == 1 and report["status"] == "failed", (mutation, report)


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


def test_unsupported_kotlin_root_cannot_report_clean_layout(home: Home) -> None:
    start(home)
    _ = configure(home)
    _ = (home.path / "Scratch.kt").write_text("class Scratch\n")
    assert home.run("/usr/bin/git", "add", "-f", "Scratch.kt").returncode == 0
    code, report = run(home, "turn", "--session", "fixture")
    assert code == 1 and "unsupported-kotlin-source-root" in str(report)


def test_ignored_package_peer_names_invalidate_layout_cache(home: Home) -> None:
    start(home)
    _ = configure(home)
    package = home.path / "src/main/kotlin/feature"
    package.mkdir(parents=True)
    source = package / "Changed.kt"
    _ = source.write_text("class Changed\n")
    assert home.run("/usr/bin/git", "add", "-f", str(source)).returncode == 0
    first = run(home, "turn", "--session", "fixture")
    assert first[0] == 0 and '"cached": false' in json.dumps(first[1])
    assert '"cached": true' in json.dumps(run(home, "handoff", "--session", "fixture")[1])
    _ = (package / "IgnoredPeer.kt").write_text("class IgnoredPeer\n")
    result = run(home, "handoff", "--session", "fixture")
    assert result[0] == 0 and '"cached": false' in json.dumps(result[1])


def test_concurrent_check_rejects_without_resetting_session(home: Home) -> None:
    start(home)
    _, report = run(home, "begin", "--session", "fixture")
    lock = Path(str(report["receipt"])).with_name("lock")
    with lock.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        code, report = run(home, "handoff", "--session", "fixture")
        assert code == 1 and report["status"] == "failed"
    assert run(home, "handoff", "--session", "fixture")[1]["status"] == "no-changes"


def test_tool_permission_change_invalidates_receipt(home: Home) -> None:
    start(home)
    owner = configure(home)
    _ = (home.path / "README.md").write_text("New prose.\n")
    assert run(home, "handoff", "--session", "fixture")[0] == 0
    assert run(home, "handoff", "--session", "fixture")[0] == 0
    count = owner / "scripts/count"
    assert count.read_text() == "1"
    (owner / "vale").chmod(0o700)
    assert run(home, "handoff", "--session", "fixture")[0] == 0
    assert count.read_text() == "2"


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
