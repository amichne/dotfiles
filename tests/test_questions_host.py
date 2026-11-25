from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
from pathlib import Path

import pytest


def test_native_pi_questions_use_rpc_dialogs_and_keep_rounds_separate(tmp_path: Path) -> None:
    pi = shutil.which("pi")
    if pi is None:
        pytest.skip("needs an installed Pi host")
    root = Path(__file__).resolve().parents[1]
    home = tmp_path / "home"
    agent = home / ".pi/agent"
    (agent / "extensions").mkdir(parents=True)
    for name in ("extensions/ask-questions.ts", "lib/questions.ts", "questions.json"):
        source = root / ".pi/agent" / name
        (agent / name).parent.mkdir(parents=True, exist_ok=True)
        _ = shutil.copy2(source, agent / name)
    _ = (agent / "extensions/probe.ts").write_text(
        """
import register from "./ask-questions.ts";
export default function(pi) {
  let definition;
  register({ ...pi, registerTool: tool => { definition = tool; pi.registerTool(tool); } });
  pi.registerCommand("questions-probe", {
    handler: async (mode, ctx) => {
      const questions = mode === "batch" ? [
        { id: "expired", prompt: "Leave unanswered", timeoutMs: 100, onTimeout: "model_judgment" },
        { id: "choice", prompt: "Choose value", options: ["A", "B"], timeoutMs: 1000 },
        { id: "cancel", prompt: "Cancel question", timeoutMs: 1000 },
        { id: "not-asked", prompt: "Must stay hidden", timeoutMs: 1000 }
      ] : [{ id: "expired", prompt: "Later round", timeoutMs: 1000 }];
      const result = await definition.execute(mode, { questions }, undefined, undefined,
        mode === "headless" ? { ...ctx, hasUI: false } : ctx);
      ctx.ui.notify(JSON.stringify({ mode, details: result.details, isError: result.isError }), "info");
    }
  });
}
"""
    )
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
    process = subprocess.Popen(
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
            "--no-extensions",
            "-e",
            str(agent / "extensions/probe.ts"),
        ],
        cwd=home,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    output: queue.Queue[str] = queue.Queue()

    def read_output() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            output.put(line)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    dialogs: list[dict[str, object]] = []
    results: dict[str, dict[str, object]] = {}
    try:
        for mode in ("headless", "batch", "later"):
            _ = process.stdin.write(
                json.dumps({"id": mode, "type": "prompt", "message": f"/questions-probe {mode}"})
                + "\n"
            )
            process.stdin.flush()
            while True:
                event = json.loads(output.get(timeout=15))
                assert event.get("type") != "agent_start", event
                if event.get("method") in ("select", "input"):
                    assert mode != "headless", event
                    dialogs.append(event)
                    title = event["title"].split("\n")[0]
                    if title == "Leave unanswered":
                        continue
                    response = {"type": "extension_ui_response", "id": event["id"]}
                    if title == "Cancel question":
                        response["cancelled"] = True
                    else:
                        response["value"] = "2. B" if title == "Choose value" else "Later answer"
                    _ = process.stdin.write(json.dumps(response) + "\n")
                    process.stdin.flush()
                if event.get("method") == "notify":
                    result = json.loads(event["message"])
                    assert result["mode"] == mode
                    results[mode] = result
                    break
        process.stdin.close()
        _ = process.wait(timeout=15)
        assert process.returncode == 0, process.stderr.read()
    finally:
        if process.poll() is None:
            process.kill()
            _ = process.wait(timeout=5)
        reader.join(timeout=5)
        process.stdin.close()
        process.stdout.close()
        process.stderr.close()
    assert results["headless"]["details"] == {"status": "ui_unavailable"}
    assert results["headless"]["isError"] is True
    assert results["batch"]["details"] == {
        "toolCallId": "batch",
        "outcomes": [
            {"id": "expired", "status": "timed_out", "next": "model_judgment"},
            {"id": "choice", "status": "answered", "answer": {"kind": "selection", "text": "B"}},
            {"id": "cancel", "status": "cancelled"},
            {"id": "not-asked", "status": "not_asked"},
        ],
    }
    assert results["later"]["details"] == {
        "toolCallId": "later",
        "outcomes": [
            {
                "id": "expired",
                "status": "answered",
                "answer": {"kind": "freeform", "text": "Later answer"},
            }
        ],
    }
    assert [str(dialog["title"]).split("\n")[0] for dialog in dialogs] == [
        "Leave unanswered",
        "Choose value",
        "Cancel question",
        "Later round",
    ]
