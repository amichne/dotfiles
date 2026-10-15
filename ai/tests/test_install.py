from __future__ import annotations

import subprocess
from pathlib import Path

from .conftest import Shell, copy_runtime, init_git


def prepare(shell: Shell) -> None:
    copy_runtime(shell, "install.py", "prompts", "workflows.py", ".gitignore")
    for name in ("ci", "review"):
        source = Path(__file__).resolve().parents[1] / "tasks" / name
        target = shell.root / "ai/tasks" / name
        _ = target.write_bytes(source.read_bytes())
        target.chmod(0o755)


def test_plan_apply_fresh_shell_uninstall(shell: Shell) -> None:
    prepare(shell)
    home = Path(shell.env["HOME"])
    startup = home / ".zshrc"
    _ = startup.write_text("# User startup stays unchanged\n", encoding="utf-8")
    before = startup.read_bytes()
    plan = shell.run("install", "plan")
    assert plan.returncode == 0, plan.stderr
    assert ".local/bin/ai" in plan.stdout
    assert not (home / ".local/bin/ai").exists()
    applied = shell.run("install", "apply")
    assert applied.returncode == 0, applied.stderr
    assert shell.run("install", "apply").returncode == 0
    env = dict(shell.env, PATH=f"{home / '.local/bin'}:{shell.env['PATH']}")
    for name in ("one", "two"):
        result = subprocess.run(
            ["/bin/zsh", "-f", "-c", 'ai list && ai run "$1" "two words"', "zsh", name],
            cwd=shell.cwd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "Fixture one" in result.stdout
        assert result.stdout.endswith("two words\n")
    assert startup.read_bytes() == before
    assert not (home / ".bashrc").exists()
    removed = shell.run("install", "uninstall")
    assert removed.returncode == 0, removed.stderr
    assert not (home / ".local/bin/ai").is_symlink()
    assert not (Path(shell.env["XDG_CONFIG_HOME"]) / "ai").is_symlink()
    assert startup.read_bytes() == before


def test_conflict_preserves_all_targets(shell: Shell) -> None:
    prepare(shell)
    destination = Path(shell.env["XDG_CONFIG_HOME"]) / "ai"
    destination.mkdir(parents=True)
    _ = (destination / "keep").write_text("user data", encoding="utf-8")
    result = shell.run("install", "apply")
    assert result.returncode == 65
    assert "conflict" in result.stderr
    assert (destination / "keep").read_text() == "user data"
    assert not (Path(shell.env["HOME"]) / ".local/bin/ai").exists()


def test_clean_clone_recovers_commands(shell: Shell) -> None:
    prepare(shell)
    # The source fixture is committed. The destination receives only Git content.
    init_git(shell)
    clone = shell.cwd / "fresh clone"
    cloned = subprocess.run(
        ["git", "clone", "--quiet", str(shell.root), str(clone)],
        env=shell.env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert cloned.returncode == 0, cloned.stderr
    fresh = Shell(clone, shell.cwd, shell.env)
    assert fresh.run("install", "apply").returncode == 0
    for name in ("one", "two"):
        result = fresh.run("run", name, "from clone")
        assert result.returncode == 0, result.stderr
        assert result.stdout.endswith("from clone\n")
    listed = fresh.run("list")
    assert "ci" in listed.stdout and "review" in listed.stdout
    for name in ("ci", "review"):
        assert fresh.run("run", name, "--help").returncode == 0
