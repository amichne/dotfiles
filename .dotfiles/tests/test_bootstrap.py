from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from .conftest import ROOT, Home

ORIGIN = "https://github.com/amichne/dotfiles.git"


@pytest.fixture
def bootstrap_home(tmp_path: Path) -> Home:
    home = tmp_path / "home with spaces"
    home.mkdir()
    tools = tmp_path / "tools"
    tools.mkdir()
    uv = tools / "uv"
    _ = uv.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    uv.chmod(0o755)
    return Home(
        home,
        tools,
        {
            "HOME": str(home),
            "PATH": f"{tools}:/usr/bin:/bin",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_ALLOW_PROTOCOL": "file",
        },
    )


def bootstrap(home: Home, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/sh", "-s", "--", "--bootstrap", *args],
        input=(ROOT / "install.sh").read_text(),
        env=home.env,
        cwd=home.path,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def git(home: Home, repo: Path, *args: str) -> str:
    result = home.run("git", "-C", str(repo), *args)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture
def upstream(bootstrap_home: Home) -> Path:
    home = bootstrap_home
    repo = home.path.parent / "upstream"
    repo.mkdir()
    _ = git(home, repo, "init", "-b", "main")
    _ = git(home, repo, "config", "user.name", "Fixture")
    _ = git(home, repo, "config", "user.email", "fixture@example.invalid")
    scripts = repo / ".dotfiles/scripts"
    scripts.mkdir(parents=True)
    (scripts / "install.py").touch()
    (scripts / "install.py.lock").touch()
    _ = (repo / "install.sh").write_bytes((ROOT / "install.sh").read_bytes())
    _ = git(home, repo, "add", ".dotfiles/scripts", "install.sh")
    _ = git(home, repo, "commit", "-m", "First fixture revision")
    _ = git(home, repo, "commit", "--allow-empty", "-m", "Second fixture revision")
    home.env.update(
        GIT_CONFIG_COUNT="1",
        GIT_CONFIG_KEY_0=f"url.{repo.as_uri()}.insteadOf",
        GIT_CONFIG_VALUE_0=ORIGIN,
    )
    return repo


def test_local_launcher_forwards_installer_arguments(bootstrap_home: Home) -> None:
    result = bootstrap_home.run(
        str(ROOT / "install.sh"), "--uninstall", "--apply", "--expected-plan", "id"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "run",
        "--locked",
        "--script",
        str(ROOT / ".dotfiles/scripts/install.py"),
        "--layered",
        "--uninstall",
        "--apply",
        "--expected-plan",
        "id",
    ]


def test_remote_pin_and_dirty_checkout(bootstrap_home: Home, upstream: Path) -> None:
    home = bootstrap_home
    root = home.path / "dotfiles"
    pin = git(home, upstream, "rev-parse", "HEAD^")
    result = bootstrap(home, "--commit", pin)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[-2:] == [
        str(root / ".dotfiles/scripts/install.py"),
        "--layered",
    ]
    assert git(home, root, "rev-parse", "HEAD") == pin
    assert bootstrap(home, "--commit", pin).returncode == 0

    result = bootstrap(home)
    assert result.returncode != 0 and "requested" in result.stderr
    assert git(home, root, "rev-parse", "HEAD") == pin

    source = root / ".dotfiles/scripts/install.py"
    _ = source.write_text("local change\n")
    result = bootstrap(home, "--commit", pin)
    assert result.returncode != 0 and "local changes" in result.stderr
    assert result.stdout == "" and source.read_text() == "local change\n"


def test_remote_default_and_wrong_origin(bootstrap_home: Home, upstream: Path) -> None:
    home = bootstrap_home
    root = home.path / "dotfiles"
    result = bootstrap(home)
    assert result.returncode == 0, result.stderr
    assert git(home, root, "rev-parse", "HEAD") == git(home, upstream, "rev-parse", "HEAD")
    _ = git(home, root, "remote", "set-url", "origin", "file:///different")
    result = bootstrap(home)
    assert result.returncode != 0 and "unexpected origin" in result.stderr
    assert result.stdout == ""


def test_failed_clone_and_occupied_destination(bootstrap_home: Home) -> None:
    home = bootstrap_home
    root = home.path / "dotfiles"
    # Git permits only the file transport in this fixture. No outside network request is possible.
    assert bootstrap(home, "--commit", "invalid").returncode != 0
    assert not root.exists()
    assert bootstrap(home).returncode != 0
    assert not root.exists()
    root.mkdir()
    result = bootstrap(home)
    assert result.returncode != 0 and "ordinary checkout" in result.stderr
    assert list(root.iterdir()) == []


def test_bare_home_stops_before_clone(bootstrap_home: Home) -> None:
    home = bootstrap_home
    (home.path / ".dotfiles.git").mkdir()
    result = bootstrap(home)
    assert result.returncode != 0 and "migration required" in result.stderr
    assert not (home.path / "dotfiles").exists()
