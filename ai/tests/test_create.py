from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from .conftest import Shell, copy_runtime, init_git


def prepare(shell: Shell, *, ready: bool = True, passes: bool = True) -> None:
    copy_runtime(shell, "create.py", "install.py", "prompts", ".gitignore")
    init_git(shell)
    fake = Path(shell.env["PATH"].split(":")[0]) / "pi"
    _ = fake.write_text(
        f"#!{sys.executable}\nfrom pathlib import Path\nimport sys\n"
        "Path('pi-args').write_text(repr(sys.argv[1:]))\n"
        f"Path('proposal.toml').write_text('name = \\\"greet\\\"\\nstatus = \\\"{'ready' if ready else 'needs-input'}\\\"\\n')\n"
        "Path('requirements.md').write_text('Print a literal greeting. No network.\\n')\n"
        'Path(\'task\').write_text(\'#!/bin/bash\\n#MISE description="Print a greeting"\\nprintf \\"hello %s\\\\n\\" \\"$1\\"\\n\')\n'
        "Path('verify').write_text('#!/bin/bash\\nset -eu\\n"
        + ('test \\"$(\\"$1\\" world)\\" = \\"hello world\\"\\n' if passes else "exit 17\\n")
        + "')\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)


def test_review_verify_commit_register(shell: Shell) -> None:
    prepare(shell)
    # Unrelated staged work must remain staged and outside the generated commit.
    unrelated = shell.root / "unrelated"
    _ = unrelated.write_text("keep", encoding="utf-8")
    _ = subprocess.run(
        ["git", "-C", str(shell.root), "add", "unrelated"], env=shell.env, check=True
    )
    result = shell.run("create", "Print a greeting with a name", input_text="y\ny\n")
    assert result.returncode == 0, result.stderr + result.stdout
    assert result.stdout.index("Print a greeting") < result.stdout.index("Run this verification?")
    assert "Verification passed" in result.stdout
    assert "Invocation: ai run greet" in result.stdout
    task = shell.root / "ai/tasks/greet"
    assert task.is_file()
    execution = shell.run("run", "greet", "space name")
    assert execution.returncode == 0, execution.stderr
    assert execution.stdout == "hello space name\n"
    tracked = subprocess.run(
        ["git", "-C", str(shell.root), "show", "--format=", "--name-only", "HEAD"],
        env=shell.env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert set(tracked.stdout.splitlines()) == {
        "ai/tasks/greet",
        "ai/verification/greet",
        "ai/requirements/greet.md",
    }
    assert "unrelated" not in tracked.stdout
    staged = subprocess.run(
        ["git", "-C", str(shell.root), "diff", "--cached", "--name-only"],
        env=shell.env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert staged.stdout == "unrelated\n"


def test_unresolved_requirements_cannot_register(shell: Shell) -> None:
    prepare(shell, ready=False)
    result = shell.run("create", "Greet", input_text="y\ny\n")
    assert result.returncode != 0
    assert "needs-input" in result.stderr
    assert not (shell.root / "ai/tasks/greet").exists()


def test_failed_verification_cannot_register(shell: Shell) -> None:
    prepare(shell, passes=False)
    result = shell.run("create", "Greet", input_text="y\ny\n")
    assert result.returncode == 17, result.stderr + result.stdout
    assert not (shell.root / "ai/tasks/greet").exists()


def test_decline_keeps_draft_unregistered(shell: Shell) -> None:
    prepare(shell)
    result = shell.run("create", "Greet", input_text="n\n")
    assert result.returncode != 0
    assert not (shell.root / "ai/tasks/greet").exists()
    assert list((shell.root / "ai/drafts").glob("*/task"))


def test_decline_registration_keeps_verified_task_unregistered(shell: Shell) -> None:
    prepare(shell)
    result = shell.run("create", "Greet", input_text="y\nn\n")
    assert "Verification passed" in result.stdout
    assert result.returncode != 0
    assert not (shell.root / "ai/tasks/greet").exists()


def test_commit_failure_removes_unregistered_files(shell: Shell) -> None:
    prepare(shell)
    hook = shell.root / ".git/hooks/pre-commit"
    _ = hook.write_text("#!/bin/bash\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    result = shell.run("create", "Greet", input_text="y\ny\n")
    assert "Verification passed" in result.stdout
    assert result.returncode != 0
    assert not (shell.root / "ai/tasks/greet").exists()
    assert not (shell.root / "ai/verification/greet").exists()


def test_generated_command_survives_clone(shell: Shell) -> None:
    prepare(shell)
    assert shell.run("create", "Greet", input_text="y\ny\n").returncode == 0
    clone = shell.cwd / "generated clone"
    _ = subprocess.run(
        ["git", "clone", "--quiet", str(shell.root), str(clone)],
        env=shell.env,
        check=True,
    )
    fresh_home = shell.cwd / "fresh-home"
    fresh_home.mkdir()
    env = dict(
        shell.env,
        HOME=str(fresh_home),
        XDG_CONFIG_HOME=str(fresh_home / ".config"),
        XDG_DATA_HOME=str(fresh_home / ".local/share"),
        XDG_STATE_HOME=str(fresh_home / ".local/state"),
        XDG_CACHE_HOME=str(fresh_home / ".cache"),
    )
    fresh = Shell(clone, shell.cwd, env)
    assert fresh.run("install", "apply").returncode == 0
    result = fresh.run("run", "greet", "from Git")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "hello from Git\n"


def test_mutated_verification_input_cannot_register(shell: Shell) -> None:
    prepare(shell)
    pi = Path(shell.env["PATH"].split(":")[0]) / "pi"
    with pi.open("a") as script:
        _ = script.write(
            "Path('verify').write_text('#!/bin/bash\\nprintf changed >> \\\"$1\\\"\\n')\n"
        )
    result = shell.run("create", "Greet", input_text="y\ny\n")
    assert result.returncode == 65, result.stderr
    assert "verification changed its inputs" in result.stderr
    assert not (shell.root / "ai/tasks/greet").exists()


@pytest.mark.parametrize("marker", ["# MISE", "# [MISE]", "// MISE", ":: MISE", "#MISE\t"])
def test_alternate_mise_metadata_cannot_bypass_draft_contract(shell: Shell, marker: str) -> None:
    prepare(shell)
    pi = Path(shell.env["PATH"].split(":")[0]) / "pi"
    with pi.open("a") as script:
        line = f'{marker} env={{UNREVIEWED="value"}}\n'
        _ = script.write(f"with Path('task').open('a') as f: f.write({line!r})\n")
    result = shell.run("create", "Greet", input_text="y\ny\n")
    assert result.returncode == 65, result.stderr
    assert "invalid draft" in result.stderr
    assert not (shell.root / "ai/tasks/greet").exists()
