from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/sandbox.py"


def invoke(source: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "snapshot", str(output)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def source(tmp_path: Path) -> Path:
    root = tmp_path / "source with spaces"
    root.mkdir()
    _ = (root / ".gitignore").write_text("*\n!/.gitignore\n!/public*\n")
    _ = (root / "public").write_text("original\n")
    for args in (("init", "--quiet"), ("add", ".gitignore", "public")):
        _ = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    return root


def test_snapshot_copies_public_edits_without_private_state(source: Path, tmp_path: Path) -> None:
    _ = (source / "public").write_text("edited\n")
    executable = source / "public command"
    _ = executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    (source / ".ssh").mkdir()
    _ = (source / ".ssh/id_ed25519").write_text("private sentinel\n")
    _ = (source / "private.env").write_text("credential sentinel\n")
    index = source / ".git/index"
    before = index.read_bytes()
    archive = tmp_path / "snapshot.tar"
    result = invoke(source, archive)
    assert result.returncode == 0, result.stderr
    with tarfile.open(archive) as bundle:
        assert set(bundle.getnames()) == {"src/.gitignore", "src/public", "src/public command"}
        content = bundle.extractfile("src/public")
        assert content is not None
        assert content.read() == b"edited\n"
        assert bundle.getmember("src/public command").mode == 0o755
    assert index.read_bytes() == before
    assert (source / "public").read_text() == "edited\n"
    assert b"sentinel" not in archive.read_bytes()


@pytest.mark.parametrize("escape", [False, True])
def test_snapshot_rejects_selected_symlinks_before_archive_creation(
    source: Path, tmp_path: Path, escape: bool
) -> None:
    target = tmp_path / "private" if escape else source / "public"
    if escape:
        _ = target.write_text("secret\n")
    (source / "public link").symlink_to(target)
    output = tmp_path / "rejected.tar"
    result = invoke(source, output)
    assert result.returncode != 0
    assert "unsafe-source" in result.stderr
    assert not output.exists()


def test_snapshot_ignores_inherited_git_selection(source: Path, tmp_path: Path) -> None:
    output = tmp_path / "snapshot.tar"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "snapshot", str(output)],
        env={**os.environ, "GIT_DIR": str(tmp_path / "missing"), "GIT_INDEX_FILE": "/missing"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert output.is_file()


def test_snapshot_does_not_replace_an_existing_output(source: Path, tmp_path: Path) -> None:
    output = tmp_path / "existing.tar"
    _ = output.write_bytes(b"keep me")
    result = invoke(source, output)
    assert result.returncode != 0
    assert output.read_bytes() == b"keep me"


def test_snapshot_excludes_ignored_files_even_when_git_tracks_them(
    source: Path, tmp_path: Path
) -> None:
    _ = (source / "private.env").write_text("private sentinel\n")
    _ = subprocess.run(
        ["git", "-C", str(source), "add", "--force", "private.env"],
        check=True,
        capture_output=True,
    )
    index = source / ".git/index"
    before = index.read_bytes()
    output = tmp_path / "tracked-private.tar"
    result = invoke(source, output)
    assert result.returncode == 0, result.stderr
    with tarfile.open(output) as bundle:
        assert set(bundle.getnames()) == {"src/.gitignore", "src/public"}
    assert b"private sentinel" not in output.read_bytes()
    assert index.read_bytes() == before


def test_snapshot_supports_a_bare_home_without_its_metadata(source: Path, tmp_path: Path) -> None:
    shutil.rmtree(source / ".git")
    metadata = source / ".dotfiles.git"
    _ = subprocess.run(
        ["git", "init", "--quiet", "--bare", str(metadata)], check=True, capture_output=True
    )
    _ = subprocess.run(
        ["git", f"--git-dir={metadata}", f"--work-tree={source}", "add", ".gitignore", "public"],
        cwd=source,
        check=True,
        capture_output=True,
    )
    output = tmp_path / "bare.tar"
    result = invoke(source, output)
    assert result.returncode == 0, result.stderr
    with tarfile.open(output) as bundle:
        assert set(bundle.getnames()) == {"src/.gitignore", "src/public"}
