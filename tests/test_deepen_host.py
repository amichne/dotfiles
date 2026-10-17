from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


def test_native_pi_discovers_and_dispatches_deepen_without_a_model_request(tmp_path: Path) -> None:
    pi = shutil.which("pi")
    if pi is None:
        pytest.skip("needs an installed Pi host")
    root = Path(__file__).resolve().parents[1]
    home = tmp_path / "home with spaces"
    agent = home / ".pi/agent"
    (agent / "extensions").mkdir(parents=True)
    for name in ("deepen.md", "extensions/deepen.ts"):
        _ = shutil.copy2(root / ".pi/agent" / name, agent / name)
    node = os.environ.get("DOTFILES_TEST_NODE") or shutil.which("node")
    assert node is not None
    environment = {
        "HOME": str(home),
        "PI_CODING_AGENT_DIR": str(agent),
        "PI_OFFLINE": "1",
        "PI_TELEMETRY": "0",
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "XDG_STATE_HOME": str(home / ".local/state"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "PATH": f"{Path(node).resolve().parent}:/usr/bin:/bin",
        "TERM": "dumb",
    }
    messages = [
        {"id": "commands", "type": "get_commands"},
        {"id": "empty", "type": "prompt", "message": "/deepen"},
    ]
    result = subprocess.run(
        [
            pi,
            "--offline",
            "--mode",
            "rpc",
            "--no-session",
            "--no-mcp",
            "--no-context-files",
            "--no-skills",
            "--no-prompt-templates",
            "--no-themes",
        ],
        cwd=home,
        env=environment,
        input="".join(json.dumps(message) + "\n" for message in messages),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    # Split only LF. Unicode paragraph separators are legal inside JSON strings.
    records = [json.loads(line) for line in result.stdout.split("\n") if line.strip()]
    responses = {record["id"]: record for record in records if record.get("type") == "response"}
    commands = responses["commands"]
    assert commands["success"] is True, commands
    selected = [command for command in commands["data"]["commands"] if command["name"] == "deepen"]
    assert len(selected) == 1
    assert selected[0]["source"] == "extension"
    assert responses["empty"]["success"] is True, responses["empty"]
    assert responses["empty"]["data"]["disposition"] == "handled"
    assert not any(record.get("type") == "agent_start" for record in records)
