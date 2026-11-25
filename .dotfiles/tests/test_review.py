import os
import pty
import subprocess
import sys

import pytest

from tests.conftest import Home


def tool(home: Home, name: str, body: str) -> None:
    path = home.tools / name
    _ = path.write_text(f"#!{sys.executable}\n" + body)
    path.chmod(0o755)


def invoke(home: Home, *args: str) -> subprocess.CompletedProcess[str]:
    master, slave = pty.openpty()
    try:
        return subprocess.run(
            [str(home.path / ".local/bin/review"), "walk", *args],
            cwd=home.path,
            env=home.env,
            stdin=slave,
            stderr=slave,
            stdout=subprocess.PIPE,
            text=True,
            check=False,
            timeout=20,
        )
    finally:
        os.close(slave)
        os.close(master)


def gum_fixture(home: Home, *, save: bool = True) -> None:
    tool(
        home,
        "gum",
        f"SAVE = {save!r}\n"
        + """
import sys
from pathlib import Path
state = Path.home()
args = sys.argv[1:]
if args[0] == "filter":
    options = sys.stdin.read().splitlines()
    print(options[-1] if (state / "noted").exists() else options[0])
elif args[0] == "choose":
    if (state / "tried").exists():
        (state / "noted").touch()
        print("Leave a note")
    else:
        (state / "tried").touch()
        print(next(a for a in args if a.startswith(("Try the handoff", "Look for conflict"))))
elif args[0] == "write":
    print("The old content stays." if "expect" in args[-1] else "Worth another look.")
elif args[0] == "pager":
    sys.stdin.read()
elif args[0] == "confirm":
    sys.exit(0 if SAVE and args[-1].startswith("Save this draft") else 1)
else:
    sys.exit(8)
""",
    )


@pytest.mark.parametrize("save", [True, False])
def test_handoff_and_save_are_separate_decisions(home: Home, save: bool) -> None:
    gum_fixture(home, save=save)
    target = home.path / "review notes.md"
    result = invoke(home, "--demo", "--output", str(target))
    assert result.returncode == (0 if save else 1)
    assert target.exists() == save
    if save:
        draft = target.read_text()
        assert "Before: keep me (8 bytes)" in draft and "Exit: 1\nAfter: (empty) (0 bytes)" in draft
        assert "Expected: The old content stays." in draft and "Worth another look." in draft
        assert invoke(home, "--demo", "--output", str(target)).returncode != 0
        assert target.read_text() == draft
    else:
        assert result.stdout == ""


@pytest.mark.parametrize("drift", [True, False])
def test_snapshot_and_patch_observation(home: Home, drift: bool) -> None:
    gum_fixture(home)
    tool(
        home,
        "gh",
        f"DRIFT = {drift!r}\n"
        + """
import json, sys
from pathlib import Path
seen = Path.home() / "loaded"
if sys.argv[1] == "pr":
    head = ("c" if DRIFT and seen.exists() else "a") * 40
    print("\\t".join(["https://github.com/example/repo/pull/42", "b" * 40, head, "1"]))
else:
    assert "--paginate" in sys.argv
    seen.touch()
    print(json.dumps({"filename":"a file.txt","patch":"@@ -0,0 +1 @@\\n+<<<<<<< ours"}))
""",
    )
    target = home.path / "draft.md"
    result = invoke(home, "42", "--output", str(target))
    assert target.exists() != drift
    if drift:
        assert result.returncode == 1
        assert not (home.path / "tried").exists()
    else:
        assert result.returncode == 0
        draft = target.read_text()
        assert "a" * 40 in draft and "2:+<<<<<<< ours" in draft
        assert "## a file.txt" in draft


def test_headless_walk_returns_before_creating_draft(home: Home) -> None:
    result = home.run(str(home.path / ".local/bin/review"), "walk", "--demo")
    assert result.returncode == 2 and "interactive terminal" in result.stderr
    assert not (home.path / "review-demo.md").exists()
