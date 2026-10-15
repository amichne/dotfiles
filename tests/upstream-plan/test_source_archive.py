from __future__ import annotations

import gzip
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest


def test_original_change_remains_inspectable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path(__file__).resolve().parents[2]
    source = root / "docs/cutover/source"
    archive = (source / "config-pr16.patch.gz").read_bytes()
    patch = gzip.decompress(archive)
    metadata = json.loads((source / "provenance.json").read_text())
    assert metadata["sourceCommit"] == "1cbcb524a2a1723e3de9ed57635874b6b4a781ed"
    assert metadata["sourceBase"] == "2dd7998b973735353b9099ea23d9098c5a6ce239"
    assert hashlib.sha256(archive).hexdigest() == metadata["archiveSha256"]
    assert hashlib.sha256(patch).hexdigest() == metadata["patchSha256"]
    caller = tmp_path / "caller-home"
    caller.mkdir()
    config = caller / ".gitconfig"
    _ = config.write_text("[invalid caller configuration\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(caller))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(caller / ".config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    home = tmp_path / "git-home"
    home.mkdir()
    summary = subprocess.run(
        ["/usr/bin/git", "apply", "--numstat", "-"],
        input=patch,
        cwd=tmp_path,
        capture_output=True,
        check=False,
        env={
            "HOME": str(home),
            "PATH": os.defpath,
            "LC_ALL": "C",
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local/share"),
            "XDG_STATE_HOME": str(home / ".local/state"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
        },
    )
    assert summary.returncode == 0, summary.stderr
    paths = [line.split("\t", 2)[2] for line in summary.stdout.decode().splitlines()]
    assert paths == metadata["originalPaths"]
    assert ".cfg/shell/tests/configure.py" in paths
    assert b"python.sh" in patch
    assert config.read_text() == "[invalid caller configuration\n"
