from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


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
def home(tmp_path: Path) -> Home:
    path = tmp_path / "home with spaces"
    path.mkdir()
    for name in (
        ".gitignore",
        ".zshrc",
        ".zprofile",
        ".config",
        ".local",
        ".pi",
        "scripts/df.py",
        "scripts/df.py.lock",
    ):
        source = ROOT / name
        if source.is_dir():
            _ = shutil.copytree(source, path / name)
        elif source.is_file():
            (path / name).parent.mkdir(parents=True, exist_ok=True)
            _ = shutil.copy2(source, path / name)
    tools = tmp_path / "tools"
    tools.mkdir()
    uv = os.environ.get("DOTFILES_TEST_UV") or shutil.which("uv")
    assert uv is not None
    (tools / "uv").symlink_to(Path(uv).resolve())
    node = os.environ.get("DOTFILES_TEST_NODE")
    if node:
        (tools / "node").symlink_to(node)
    env = {
        "HOME": str(path),
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
