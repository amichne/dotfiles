"""Check public B0 sources. Install private resources with agent-check install."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument(
        "--check",
        action="store_true",
        help="Retained compatibility flag; this command never overwrites private resources.",
    )
    _ = parser.parse_args()
    source = ROOT / ".config/agent-engineering"
    baseline = (source / "B0.md").read_bytes()
    if baseline.count(b"# Engineering baseline B0") != 1 or len(baseline.split()) >= 250:
        return 1
    hooks = json.loads((source / "codex-hooks.json").read_bytes())
    if set(hooks["hooks"]) != {"SessionStart", "Stop"}:
        return 1
    if not (source / "pi-extension.ts").is_file():
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
