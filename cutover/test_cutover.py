from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Fixture:
    source: Path
    home: Path
    archive: Path
    env: dict[str, str]

    def command(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.source / "bin/dotfiles"), "cutover", *arguments],
            env=self.env,
            cwd=self.home,
            capture_output=True,
            text=True,
            check=False,
        )

    def plan(self, legacy_git: str | None = None) -> Path:
        selector = [] if legacy_git is None else ["--legacy-git", legacy_git]
        inventory = self.command("inventory", "--home", str(self.home), *selector)
        assert inventory.returncode == 0, inventory.stderr
        data = json.loads(inventory.stdout)
        for entry in data["entries"]:
            entry["owner"] = "absent" if entry["kind"] == "absent" else "legacy-config"
        data["decisions"] = {name: "retire" for name in data["decisions"]}
        admitted = self.home.parent / "reviewed.json"
        _ = admitted.write_text(json.dumps(data))
        result = self.command("plan", "--inventory", str(admitted), "--archive", str(self.archive))
        assert result.returncode == 0, result.stderr
        plan = self.home.parent / "plan.json"
        _ = plan.write_text(result.stdout)
        return plan


def git(fixture: Fixture, *arguments: str, legacy: bool = False) -> bytes:
    prefix = [
        "/usr/bin/git",
        "--no-optional-locks",
        "-C",
        str(fixture.home if legacy else fixture.source),
    ]
    if legacy:
        prefix += [f"--git-dir={fixture.home / '.cfg/repo.git'}", f"--work-tree={fixture.home}"]
    return subprocess.run(
        [*prefix, *arguments],
        env=fixture.env,
        capture_output=True,
        check=True,
    ).stdout


@pytest.fixture
def fixture(tmp_path: Path) -> Fixture:
    source = tmp_path / "source with spaces"
    source.mkdir()
    for directory in ("bin", "lib", "shell", "config", "profiles", "plugins", "ai", "cutover"):
        _ = shutil.copytree(
            SOURCE / directory,
            source / directory,
            ignore=shutil.ignore_patterns(
                ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "drafts"
            ),
        )
    home = tmp_path / "disposable HOME"
    home.mkdir()
    tools = tmp_path / "tools"
    tools.mkdir()
    for tool in ("uv", "mise"):
        executable = shutil.which(tool)
        assert executable is not None
        if tool == "uv" and ("shims" in executable or Path(executable).resolve().name == "mise"):
            executable = subprocess.run(
                ["mise", "which", "uv"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        (tools / tool).symlink_to(Path(executable).resolve())
    (tools / "python3.12").symlink_to(Path(sys.executable).resolve())
    env = {
        "HOME": str(home),
        "PATH": f"{tools}:/usr/bin:/bin",
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "XDG_STATE_HOME": str(home / ".local/state"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "Fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "MISE_AUTO_INSTALL": "false",
        "MISE_TASK_RUN_AUTO_INSTALL": "false",
        "MISE_COLOR": "0",
        "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
    }
    fixture = Fixture(source, home, tmp_path / "recovery archive", env)
    for name, content in {
        ".zshrc": b'source "$HOME/.cfg/shell/runtime.sh"\n',
        ".zshenv": b"export OLD_STARTUP=1\n",
        ".cfg/shell/runtime.sh": b"export OLD_RUNTIME=1\n",
        ".local/bin/cfg": b"#!/bin/sh\nexit 42\n",
        ".config/ai/legacy-task": b"old command\n",
        ".config/dotfiles/config.conf": b"shell.editor=fixture-editor\nfeature.atuin=off\nfeature.starship=off\nfeature.zoxide=off\nfeature.sdkman=off\n",
        ".pi/agent/auth.json": b"test-owned private Pi sentinel\n",
        ".codex/sessions/private": b"test-owned private Codex sentinel\n",
        "unrelated.txt": b"keep staged work\n",
    }.items():
        path = home / name
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_bytes(content)
    (home / ".local/bin/cfg").chmod(0o751)
    (home / ".local/bin/ai").symlink_to("cfg")
    _ = git(fixture, "init", "-q", str(source))
    _ = git(fixture, "add", ".")
    _ = git(fixture, "commit", "-qm", "source fixture")
    _ = subprocess.run(
        [str(tools / "uv"), "sync", "--locked", "--no-dev", "--project", str(source / "cutover")],
        env=env,
        capture_output=True,
        check=True,
    )
    _ = git(fixture, "init", "--bare", "-q", str(home / ".cfg/repo.git"))
    _ = git(fixture, "add", ".zshrc", ".zshenv", ".cfg/shell/runtime.sh", legacy=True)
    _ = git(fixture, "commit", "-qm", "legacy fixture", legacy=True)
    _ = git(fixture, "add", "unrelated.txt", legacy=True)
    _ = subprocess.run(
        [str(tools / "mise"), "trust", str(source / "ai/mise.toml")],
        env=env,
        capture_output=True,
        check=True,
    )
    return fixture


def snapshot(root: Path) -> dict[str, tuple[int, bytes]]:
    result: dict[str, tuple[int, bytes]] = {}
    for directory, children, files in os.walk(root, followlinks=False):
        parent = Path(directory)
        for name in sorted([*children, *files]):
            path = parent / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                data = os.fsencode(path.readlink())
            elif stat.S_ISREG(mode):
                data = hashlib.sha256(path.read_bytes()).digest()
            else:
                data = b""
            result[path.relative_to(root).as_posix()] = (mode, data)
    return result


def test_inventory_and_plan_are_read_only(fixture: Fixture) -> None:
    before = snapshot(fixture.home)
    plan = fixture.plan()
    assert snapshot(fixture.home) == before
    assert not fixture.archive.exists()
    data = json.loads(plan.read_text())
    assert data["source"]["head"] == git(fixture, "rev-parse", "HEAD").decode().strip()
    assert {entry["path"] for entry in data["entries"]} >= {
        ".zshrc",
        ".zshenv",
        ".local/bin/ai",
        ".config/ai",
        ".local/bin/cfg",
        ".cfg/repo.git",
        ".cfg/shell",
    }
    assert all(not entry["path"].startswith((".pi", ".codex")) for entry in data["entries"])


def test_plan_file_resolves_from_the_caller_directory(fixture: Fixture) -> None:
    plan = fixture.plan()
    relative = fixture.home / "reviewed-plan.json"
    _ = relative.write_bytes(plan.read_bytes())
    before = snapshot(fixture.home)
    result = fixture.command("apply", "--plan", relative.name)
    assert result.returncode == 0, result.stderr
    recovered = fixture.command("recover", "--archive", str(fixture.archive))
    assert recovered.returncode == 0, recovered.stderr
    assert snapshot(fixture.home) == before


def test_apply_and_independent_recovery(fixture: Fixture) -> None:
    before = snapshot(fixture.home)
    plan = fixture.plan()
    applied = fixture.command("apply", "--plan", str(plan))
    assert applied.returncode == 0, applied.stderr
    state = fixture.command("status", "--archive", str(fixture.archive))
    assert state.returncode == 0, state.stderr
    assert json.loads(state.stdout)["status"] == "applied"
    assert stat.S_IMODE(fixture.archive.stat().st_mode) == 0o700
    assert json.loads((fixture.archive / "acceptance.json").read_text())["exit"] == 0
    assert not (fixture.home / ".cfg/repo.git").exists()
    assert not (fixture.home / ".cfg/shell").exists()
    assert not (fixture.home / ".local/bin/cfg").exists()
    assert (fixture.home / ".local/bin/ai").resolve() == fixture.source / "bin/ai"
    assert (fixture.home / ".config/ai").resolve() == fixture.source / "ai"
    repeated = fixture.command("apply", "--plan", str(plan))
    assert repeated.returncode == 0, repeated.stderr
    unavailable = fixture.source.with_name("unavailable source")
    _ = fixture.source.rename(unavailable)
    recovered = subprocess.run(
        [str(fixture.archive / "recover")],
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert recovered.returncode == 0, recovered.stderr
    assert snapshot(fixture.home) == before
    assert (
        subprocess.run(
            [str(fixture.archive / "recover")], capture_output=True, check=False
        ).returncode
        == 0
    )

    _ = unavailable.rename(fixture.source)
    state = fixture.command("status", "--archive", str(fixture.archive))
    assert state.returncode == 0, state.stderr
    assert json.loads(state.stdout)["status"] == "recovered"


def test_fresh_shell_uses_one_runtime(fixture: Fixture) -> None:
    plan = fixture.plan()
    assert fixture.command("apply", "--plan", str(plan)).returncode == 0
    shell = subprocess.run(
        [
            "/bin/zsh",
            "-dlic",
            'HISTFILE=/dev/null; [[ -z $OLD_RUNTIME && -z $OLD_STARTUP && $DOTFILES_RUNTIME_LOADED == 1 && $EDITOR == fixture-editor ]] && "$HOME/.local/bin/ai" run review --help',
        ],
        env=fixture.env,
        cwd=fixture.home,
        capture_output=True,
        text=True,
        check=False,
    )
    assert shell.returncode == 0, shell.stderr
    assert "Local PR review" in shell.stdout
    rejected = subprocess.run(
        [str(fixture.home / ".local/bin/ai"), "run", "../escape"],
        env=fixture.env,
        cwd=fixture.home,
        capture_output=True,
        check=False,
    )
    assert rejected.returncode != 0


@pytest.mark.parametrize("edit", ["content", "deletion"])
def test_completed_recovery_rejects_drift(fixture: Fixture, edit: str) -> None:
    plan = fixture.plan()
    assert fixture.command("apply", "--plan", str(plan)).returncode == 0
    target = fixture.home / ".zshrc"
    if edit == "content":
        _ = target.write_text("new user content\n")
    else:
        target.unlink()
    before = snapshot(fixture.home)
    state = fixture.command("status", "--archive", str(fixture.archive))
    assert state.returncode == 75, state.stderr
    assert json.loads(state.stdout)["status"] == "drifted"
    result = fixture.command("recover", "--archive", str(fixture.archive))
    assert result.returncode != 0
    assert snapshot(fixture.home) == before


@pytest.mark.parametrize("stop", ["KeyboardInterrupt", "OSError", "SIGTERM"])
def test_handled_stop_restores_preimages(fixture: Fixture, stop: str) -> None:
    before = snapshot(fixture.home)
    plan = fixture.plan()
    script = (
        "import os,sys,runpy,signal\nfrom pathlib import Path\n"
        "original=os.replace\nfired=False\n"
        "def stopped(source,destination):\n"
        " global fired\n original(source,destination)\n"
        f" if not fired and Path(destination)==Path({str(fixture.home / '.zshrc')!r}):\n"
        + (
            "  fired=True\n  os.kill(os.getpid(), signal.SIGTERM)\n"
            if stop == "SIGTERM"
            else f"  fired=True\n  raise {stop}()\n"
        )
        + "os.replace=stopped\n"
        f"sys.argv=['cutover','apply','--plan',{str(plan)!r}]\n"
        "runpy.run_module('cutover.standalone', run_name='__main__', alter_sys=True)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=fixture.source,
        env=fixture.env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == (74 if stop == "OSError" else 130), result.stderr
    assert snapshot(fixture.home) == before


@pytest.mark.parametrize(
    ("path", "stage"),
    [
        (path, "restore")
        for path in [
            ".zshrc",
            ".zshenv",
            ".local/bin/ai",
            ".config/ai",
            ".local/bin/cfg",
            ".cfg/shell",
            ".cfg/repo.git",
        ]
    ]
    + [(".zshrc", "discard")],
)
def test_interrupted_recovery_resumes(fixture: Fixture, path: str, stage: str) -> None:
    before = snapshot(fixture.home)
    plan = fixture.plan()
    assert fixture.command("apply", "--plan", str(plan)).returncode == 0
    script = (
        "import os,runpy\nfrom pathlib import Path\noriginal=os.replace\n"
        "def stopped(source,destination):\n"
        " original(source,destination)\n"
        f" if Path({'destination' if stage == 'restore' else 'source'})==Path({str(fixture.home / path)!r}): os._exit(97)\n"
        "os.replace=stopped\n"
        f"runpy.run_path({str(fixture.archive / 'recovery.py')!r}, run_name='__main__')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=fixture.home,
        env=fixture.env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 97, result.stderr
    resumed = subprocess.run(
        [str(fixture.archive / "recover")], capture_output=True, text=True, check=False
    )
    assert resumed.returncode == 0, resumed.stderr
    assert snapshot(fixture.home) == before


def test_changed_staged_payload_cannot_be_installed(fixture: Fixture) -> None:
    before = snapshot(fixture.home)
    plan = fixture.plan()
    script = (
        "import os,sys\nfrom pathlib import Path\nfrom cutover.standalone import main\n"
        "original=os.replace\n"
        "def changed(source,destination):\n"
        " original(source,destination)\n"
        f" if Path(source)==Path({str(fixture.home / '.zshrc')!r}):\n"
        f"  Path({str(fixture.archive / 'after/0')!r}).write_text('unreviewed replacement\\n')\n"
        "os.replace=changed\n"
        f"sys.exit(main(['apply','--plan',{str(plan)!r}]))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=fixture.source,
        env=fixture.env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0, result.stdout
    target = fixture.home / ".zshrc"
    assert not target.exists() or target.read_bytes() == b'source "$HOME/.cfg/shell/runtime.sh"\n'
    assert (
        subprocess.run(
            [str(fixture.archive / "recover")], capture_output=True, check=False
        ).returncode
        == 0
    )
    assert snapshot(fixture.home) == before


CRASH_POINTS = [
    (".zshrc", "archive"),
    (".zshrc", "install"),
    (".zshenv", "archive"),
    (".local/bin/ai", "archive"),
    (".local/bin/ai", "install"),
    (".config/ai", "archive"),
    (".config/ai", "install"),
    (".local/bin/dotfiles", "install"),
    (".local/bin/cfg", "archive"),
    (".cfg/shell", "archive"),
    (".cfg/repo.git", "archive"),
]


@pytest.mark.parametrize(("path", "stage"), CRASH_POINTS)
def test_abrupt_stop_after_each_replacement_recovers(
    fixture: Fixture,
    path: str,
    stage: str,
) -> None:
    before = snapshot(fixture.home)
    plan = fixture.plan()
    script = (
        "import os,sys\nfrom pathlib import Path\nfrom cutover.standalone import main\n"
        "original=os.replace\n"
        "def stopped(source,destination):\n"
        " original(source,destination)\n"
        f" if Path({'source' if stage == 'archive' else 'destination'}) == Path({str(fixture.home / path)!r}): os._exit(97)\n"
        "os.replace=stopped\n"
        f"sys.exit(main(['apply','--plan',{str(plan)!r}]))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=fixture.env,
        cwd=fixture.source,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 97, result.stderr
    state = fixture.command("status", "--archive", str(fixture.archive))
    assert state.returncode == 8, state.stderr
    assert json.loads(state.stdout)["status"] == "incomplete"
    recovered = subprocess.run(
        [str(fixture.archive / "recover")],
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert recovered.returncode == 0, recovered.stderr
    assert snapshot(fixture.home) == before


@pytest.mark.parametrize("drift", ["target", "index", "source", "parent", "configuration"])
def test_drift_stops_before_replacements(fixture: Fixture, drift: str) -> None:
    plan = fixture.plan()
    if drift == "target":
        _ = (fixture.home / ".zshrc").write_text("later edit\n")
    elif drift == "index":
        _ = git(fixture, "reset", "-q", "--", "unrelated.txt", legacy=True)
    elif drift == "source":
        _ = (fixture.source / "bin/ai").write_text("changed source\n")
    elif drift == "configuration":
        _ = (fixture.home / ".config/dotfiles/config.conf").write_text(
            "shell.editor=later-editor\n"
        )
    else:
        directory = fixture.home / ".local/bin"
        _ = directory.rename(directory.with_name("other-bin"))
        directory.symlink_to("other-bin")
    before = snapshot(fixture.home)
    result = fixture.command("apply", "--plan", str(plan))
    assert result.returncode != 0
    assert snapshot(fixture.home) == before
    assert not fixture.archive.exists()


def test_recovery_rejects_later_edits_without_partial_restore(fixture: Fixture) -> None:
    plan = fixture.plan()
    assert fixture.command("apply", "--plan", str(plan)).returncode == 0
    _ = (fixture.home / ".zshrc").write_text("new user content\n")
    before = snapshot(fixture.home)
    result = fixture.command("recover", "--archive", str(fixture.archive))
    assert result.returncode != 0
    assert snapshot(fixture.home) == before


@pytest.mark.parametrize("invalid", ["owner", "decision", "path"])
def test_inventory_rejects_unadmitted_changes(fixture: Fixture, invalid: str) -> None:
    plan = fixture.plan()
    inventory = plan.with_name("reviewed.json")
    data = json.loads(inventory.read_text())
    if invalid == "owner":
        data["entries"][0]["owner"] = "other"
    elif invalid == "decision":
        data["decisions"]["work-dashboard"] = "unresolved"
    else:
        data["entries"][0]["path"] = ".pi/agent/auth.json"
    _ = inventory.write_text(json.dumps(data))
    before = snapshot(fixture.home)
    result = fixture.command(
        "plan", "--inventory", str(inventory), "--archive", str(fixture.archive)
    )
    assert result.returncode != 0
    assert snapshot(fixture.home) == before
    assert not fixture.archive.exists()


def test_registered_worktree_blocks_metadata_retirement(fixture: Fixture) -> None:
    checkout = fixture.home.parent / "active legacy worktree"
    _ = git(fixture, "worktree", "add", "--detach", str(checkout), "HEAD", legacy=True)
    before = snapshot(fixture.home)
    worktree_before = snapshot(checkout)
    result = fixture.command("inventory", "--home", str(fixture.home))
    assert result.returncode != 0
    assert "worktree" in result.stderr
    assert snapshot(fixture.home) == before
    assert snapshot(checkout) == worktree_before


def test_explicit_authority_preserves_both_git_directories(fixture: Fixture) -> None:
    older = fixture.home / ".local/share/config/repo.git"
    _ = git(
        fixture,
        "clone",
        "--quiet",
        "--bare",
        "--no-local",
        str(fixture.home / ".cfg/repo.git"),
        str(older),
    )
    assert not (older / "index").exists()
    before = snapshot(fixture.home)
    ambiguous = fixture.command("inventory", "--home", str(fixture.home))
    assert ambiguous.returncode != 0
    plan = fixture.plan(".cfg/repo.git")
    assert fixture.command("apply", "--plan", str(plan)).returncode == 0
    assert not older.exists()
    recovered = fixture.command("recover", "--archive", str(fixture.archive))
    assert recovered.returncode == 0, recovered.stderr
    assert snapshot(fixture.home) == before


def test_home_lock_blocks_competing_apply(fixture: Fixture) -> None:
    plan = fixture.plan()
    before = snapshot(fixture.home)
    descriptor = os.open(fixture.home, os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = fixture.command("apply", "--plan", str(plan))
    finally:
        os.close(descriptor)
    assert result.returncode != 0
    assert snapshot(fixture.home) == before
    assert not fixture.archive.exists()


@pytest.mark.parametrize("corruption", ["journal", "backup", "plan"])
def test_corrupt_archive_stops_recovery_before_writes(fixture: Fixture, corruption: str) -> None:
    plan = fixture.plan()
    assert fixture.command("apply", "--plan", str(plan)).returncode == 0
    path = (
        fixture.archive
        / {"journal": "journal.json", "backup": "before/0", "plan": "plan.json"}[corruption]
    )
    _ = path.write_text("corrupt archive\n")
    before = snapshot(fixture.home)
    result = fixture.command("recover", "--archive", str(fixture.archive))
    assert result.returncode != 0
    assert snapshot(fixture.home) == before


def test_invalid_configuration_stops_before_archive(fixture: Fixture) -> None:
    plan = fixture.plan()
    _ = (fixture.home / ".config/dotfiles/config.conf").write_text("shell.history-size=invalid\n")
    before = snapshot(fixture.home)
    result = fixture.command("apply", "--plan", str(plan))
    assert result.returncode != 0
    assert snapshot(fixture.home) == before
    assert not fixture.archive.exists()


def test_plan_parent_cannot_escape_the_inventory(fixture: Fixture) -> None:
    plan = fixture.plan()
    data = json.loads(plan.read_text())
    data["parents"][0]["path"] = "../outside"
    _ = plan.write_text(json.dumps(data))
    before = snapshot(fixture.home)
    result = fixture.command("apply", "--plan", str(plan))
    assert result.returncode == 65, result.stderr
    assert snapshot(fixture.home) == before
    assert not fixture.archive.exists()


def test_unadmitted_interpreter_is_rejected_before_read(fixture: Fixture) -> None:
    plan = fixture.plan()
    forbidden = fixture.home.parent / "unadmitted private directory"
    forbidden.mkdir()
    _ = (forbidden / "sentinel").write_text("fixture private bytes\n")
    data = json.loads(plan.read_text())
    data["interpreter"] = str(forbidden)
    _ = plan.write_text(json.dumps(data))
    before = snapshot(fixture.home)
    script = (
        "import os,sys\nfrom pathlib import Path\nimport cutover.standalone as tool\n"
        "original=tool.image\n"
        "def guarded(path):\n"
        f" if path==Path({str(forbidden)!r}): os._exit(96)\n"
        " return original(path)\n"
        "tool.image=guarded\n"
        f"sys.exit(tool.main(['apply','--plan',{str(plan)!r}]))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=fixture.source,
        env=fixture.env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 75, result.stderr
    assert snapshot(fixture.home) == before
    assert not fixture.archive.exists()


def test_failed_fresh_shell_restores_the_previous_installation(fixture: Fixture) -> None:
    # The manifest remains valid. The real startup path returns a failure.
    plugin = fixture.source / "plugins/core/shell.plugin.zsh"
    with plugin.open("a") as content:
        _ = content.write("\nreturn 17\n")
    _ = git(fixture, "add", "plugins/core/shell.plugin.zsh")
    _ = git(fixture, "commit", "-qm", "fixture runtime failure")
    before = snapshot(fixture.home)
    plan = fixture.plan()
    result = fixture.command("apply", "--plan", str(plan))
    assert result.returncode != 0
    assert "fresh-shell" in result.stderr
    assert snapshot(fixture.home) == before
