from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_native_projections_have_one_baseline() -> None:
    source = (ROOT / ".config/agent-engineering/B0.md").read_bytes()
    for name in (".codex/AGENTS.md", ".pi/agent/AGENTS.md"):
        assert (ROOT / name).read_bytes() == source
        assert source.count(b"# Engineering baseline B0") == 1
    assert len(source.split()) < 250
