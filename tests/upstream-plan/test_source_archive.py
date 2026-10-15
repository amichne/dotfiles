from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
from pathlib import Path


def test_original_change_remains_inspectable(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    source = root / "docs/cutover/source"
    archive = (source / "config-pr16.patch.gz").read_bytes()
    patch = gzip.decompress(archive)
    metadata = json.loads((source / "provenance.json").read_text())
    assert metadata["sourceCommit"] == "1cbcb524a2a1723e3de9ed57635874b6b4a781ed"
    assert metadata["sourceBase"] == "2dd7998b973735353b9099ea23d9098c5a6ce239"
    assert hashlib.sha256(archive).hexdigest() == metadata["archiveSha256"]
    assert hashlib.sha256(patch).hexdigest() == metadata["patchSha256"]
    summary = subprocess.run(
        ["/usr/bin/git", "apply", "--numstat", "-"],
        input=patch,
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )
    assert summary.returncode == 0, summary.stderr
    paths = [line.split("\t", 2)[2] for line in summary.stdout.decode().splitlines()]
    assert paths == metadata["originalPaths"]
    assert ".cfg/shell/tests/configure.py" in paths
    assert b"python.sh" in patch
