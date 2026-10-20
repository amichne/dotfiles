"""Project B0 into native instruction files without touching installed settings."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".config/agent-engineering/B0.md"
TARGETS = (ROOT / ".codex/AGENTS.md", ROOT / ".pi/agent/AGENTS.md")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = SOURCE.read_bytes()
    for target in TARGETS:
        if args.check:
            if not target.is_file() or target.read_bytes() != content:
                print(f"baseline drift: {target.relative_to(ROOT)}")
                return 1
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            _ = target.write_bytes(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
