from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def public_files() -> tuple[tuple[str, bytes, int], ...]:
    # Reuse the owning public-inventory reader. Never copy private HOME trees.
    with tempfile.TemporaryDirectory(prefix="dotfiles-public-fixture-") as directory:
        archive = Path(directory) / "source.tar"
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/sandbox.py"),
                "--source",
                str(ROOT),
                "snapshot",
                str(archive),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        files: list[tuple[str, bytes, int]] = []
        with tarfile.open(archive) as stream:
            for member in stream.getmembers():
                content = stream.extractfile(member)
                assert content is not None and member.name.startswith("src/")
                files.append((member.name.removeprefix("src/"), content.read(), member.mode))
        return tuple(files)


@dataclass(frozen=True)
class Home:
    path: Path
    tools: Path
    env: dict[str, str]

    def run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            arguments,
            cwd=self.path,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )


@pytest.fixture
def home(tmp_path: Path, public_files: tuple[tuple[str, bytes, int], ...]) -> Home:
    path = tmp_path / "home with spaces"
    path.mkdir()
    selected = (
        ".gitignore",
        "Brewfile",
        ".zshrc",
        ".zshenv",
        ".zprofile",
        ".config",
        ".local",
        ".pi",
    )
    for name, content, mode in public_files:
        if any(name == prefix or name.startswith(prefix + "/") for prefix in selected):
            target = path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            _ = target.write_bytes(content)
            target.chmod(mode)
    tools = tmp_path / "tools"
    tools.mkdir()
    brew_bin = tmp_path / "brew prefix/bin"
    brew_bin.mkdir(parents=True)
    (brew_bin / "brew").symlink_to("/usr/bin/false")
    uv = os.environ.get("DOTFILES_TEST_UV") or shutil.which("uv")
    assert uv is not None
    (tools / "uv").symlink_to(Path(uv).resolve())
    node = os.environ.get("DOTFILES_TEST_NODE")
    if node:
        (tools / "node").symlink_to(node)
    env = {
        "HOME": str(path),
        "HOMEBREW_PREFIX": str(brew_bin.parent),
        "ZDOTDIR": str(path),
        "XDG_CONFIG_HOME": str(path / ".config"),
        "XDG_DATA_HOME": str(path / ".local/share"),
        "XDG_STATE_HOME": str(path / ".local/state"),
        "XDG_CACHE_HOME": str(path / ".cache"),
        "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
        "UV_PYTHON": sys.executable,
        "UV_PYTHON_DOWNLOADS": "never",
        "UV_OFFLINE": "1",
        "PATH": f"{tools}:/usr/bin:/bin",
        "TERM": "dumb",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
    }
    return Home(path, tools, env)


ORIGIN = "git@github.com:amichne/dotfiles.git"


def git(home: Home, directory: Path, *args: str) -> subprocess.CompletedProcess[str]:
    if (directory / ".dotfiles.git").is_dir():
        return home.run(
            "/usr/bin/git",
            "-C",
            str(directory),
            f"--git-dir={directory / '.dotfiles.git'}",
            f"--work-tree={directory}",
            *args,
        )
    return home.run("/usr/bin/git", "-C", str(directory), *args)


def commit(home: Home, source: Path, message: str) -> str:
    assert git(home, source, "add", "--all").returncode == 0
    result = git(
        home,
        source,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "--quiet",
        "-m",
        message,
    )
    assert result.returncode == 0, result.stderr
    return git(home, source, "rev-parse", "HEAD").stdout.strip()
