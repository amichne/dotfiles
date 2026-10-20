"""Preserve private native resources while installing the explicitly selected B0."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast

BEGIN = b"<!-- agent-engineering:B0 begin -->\n"
END = b"<!-- agent-engineering:B0 end -->\n"
HEADER = b"# Engineering baseline B0"
LIMIT = 16 * 1024 * 1024


def sha(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest() if data is not None else None


def object_data(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("invalid-resource-object")
    data = cast(dict[object, object], value)
    if any(not isinstance(key, str) for key in data):
        raise ValueError("invalid-resource-key")
    return cast(dict[str, object], data)


def read(path: Path) -> bytes | None:
    if path.is_symlink():
        raise ValueError("symlink-install-target")
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > LIMIT:
        raise ValueError("invalid-install-target")
    return path.read_bytes()


def block(data: bytes) -> bytes | None:
    if BEGIN not in data and END not in data:
        return None
    if data.count(BEGIN) != 1 or data.count(END) != 1:
        raise ValueError("ambiguous-baseline-markers")
    prefix, rest = data.split(BEGIN)
    content, suffix = rest.split(END)
    if HEADER in prefix + suffix:
        raise ValueError("duplicate-baseline-outside-managed-block")
    return content


def instructions(existing: bytes | None, source: bytes) -> bytes:
    data = existing or b""
    managed = BEGIN + source + END
    content = block(data)
    if content is not None:
        prefix, rest = data.split(BEGIN)
        _, suffix = rest.split(END)
        return prefix + managed + suffix
    if data == source:
        return managed
    if HEADER in data:
        raise ValueError("unmanaged-baseline-requires-migration")
    return data + (b"\n\n" if data else b"") + managed


def merge_hooks(existing: bytes | None, template: bytes) -> bytes:
    data: dict[str, object] = object_data(json.loads(existing)) if existing else {"hooks": {}}
    hooks = object_data(data.get("hooks"))
    additions = object_data(object_data(json.loads(template))["hooks"])
    for event, value in additions.items():
        groups = cast(list[object], value)
        current = hooks.get(event, [])
        if not isinstance(current, list):
            raise ValueError("invalid-existing-hook-event")
        entries = cast(list[object], current)
        for group in groups:
            expected = object_data(group)
            owned = object_data(cast(list[object], expected["hooks"])[0])["command"]
            matches: list[object] = []
            for candidate in entries:
                definition = object_data(candidate)
                commands = definition.get("hooks")
                if not isinstance(commands, list):
                    raise ValueError("invalid-existing-hook-definition")
                if any(
                    object_data(item).get("command") == owned
                    for item in cast(list[object], commands)
                ):
                    matches.append(candidate)
            if matches and (len(matches) != 1 or matches[0] != group):
                raise ValueError("modified-engineering-hook")
            if not matches:
                entries.append(group)
        hooks[event] = entries
    data["hooks"] = hooks
    # Preserve the original bytes on a semantic no-op, including formatting.
    if existing and data == json.loads(existing):
        return existing
    return (json.dumps(data, indent=2, ensure_ascii=True) + "\n").encode()


@dataclass(frozen=True)
class Change:
    path: Path
    before: bytes | None
    after: bytes
    mode: int

    def report(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "beforeSha256": sha(self.before),
            "afterSha256": sha(self.after),
            "mode": self.mode,
        }


@dataclass(frozen=True)
class Plan:
    identity: str
    changes: tuple[Change, ...]
    files: dict[str, str]
    baseline_sha256: str

    def report(self) -> dict[str, object]:
        return {
            "status": "install-planned",
            "planId": self.identity,
            "changes": [change.report() for change in self.changes],
            "trust": "unchanged; review new Codex hooks through native controls",
        }


def build_plan(
    home: Path, source: Path, state: Path, tools: dict[str, str], signature: str
) -> Plan:
    baseline = (source / "B0.md").read_bytes()
    if not baseline.endswith(b"\n") or baseline.count(HEADER) != 1:
        raise ValueError("invalid-baseline-source")
    codex = Path(os.environ.get("CODEX_HOME", str(home / ".codex")))
    pi = Path(os.environ.get("PI_CODING_AGENT_DIR", str(home / ".pi/agent")))
    if any(not root.resolve().is_relative_to(home.resolve()) for root in (codex, pi)):
        raise ValueError("native-home-outside-HOME; explicit migration required")
    if any(parent.is_symlink() for root in (codex, pi, state) for parent in (root, *root.parents)):
        raise ValueError("symlink-install-parent")
    previous_path = state / "installation.json"
    previous_bytes = read(previous_path)
    previous = object_data(json.loads(previous_bytes)) if previous_bytes else {}
    known = object_data(previous.get("files", {}))
    baseline_hash = cast(str, sha(baseline))
    for path in (codex / "AGENTS.md", pi / "AGENTS.md"):
        raw = read(path)
        managed = block(raw) if raw is not None else None
        if managed is not None and sha(managed) not in (
            baseline_hash,
            previous.get("baselineSha256"),
        ):
            raise ValueError("modified-managed-baseline")
    extension = pi / "extensions/engineering-checks.ts"
    extension_source = (source / "pi-extension.ts").read_bytes()
    extension_before = read(extension)
    if extension_before not in (None, extension_source) and sha(extension_before) != known.get(
        str(extension)
    ):
        raise ValueError("unowned-pi-extension")
    targets = {
        state / "tools.json": (json.dumps(tools, sort_keys=True) + "\n").encode(),
        codex / "AGENTS.md": instructions(read(codex / "AGENTS.md"), baseline),
        pi / "AGENTS.md": instructions(read(pi / "AGENTS.md"), baseline),
        codex / "hooks.json": merge_hooks(
            read(codex / "hooks.json"), (source / "codex-hooks.json").read_bytes()
        ),
        extension: extension_source,
    }
    changes: list[Change] = []
    files: dict[str, str] = {}
    for path, content in targets.items():
        # Reject symlinked parents too. Keep all effects in the declared homes/state.
        if any(parent.is_symlink() for parent in path.parents if parent != Path("/")):
            raise ValueError("symlink-install-parent")
        before = read(path)
        files[str(path)] = cast(str, sha(content))
        if before != content:
            mode = stat.S_IMODE(path.stat().st_mode) if before is not None else 0o600
            changes.append(Change(path, before, content, mode))
    identity = hashlib.sha256(
        json.dumps(
            [signature, [change.report() for change in changes], files], sort_keys=True
        ).encode()
    ).hexdigest()
    return Plan(identity, tuple(changes), files, baseline_hash)


def atomic_bytes(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            os.fchmod(handle.fileno(), mode)
            _ = handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            _ = temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def apply_plan(plan: Plan, expected: str, state: Path) -> dict[str, object]:
    if plan.identity != expected:
        raise ValueError("stale-install-plan; inspect a fresh plan")
    for change in plan.changes:
        if read(change.path) != change.before:
            raise ValueError("install-target-changed")
    backup = state / "installation-backups" / plan.identity
    # Complete every backup before the first live resource write.
    for index, change in enumerate(plan.changes):
        if change.before is not None:
            atomic_bytes(backup / str(index), change.before, 0o600)
    if plan.changes:
        atomic_bytes(
            backup / "manifest.json",
            (
                json.dumps(
                    [
                        {
                            "backup": str(index) if change.before is not None else None,
                            **change.report(),
                        }
                        for index, change in enumerate(plan.changes)
                    ],
                    sort_keys=True,
                )
                + "\n"
            ).encode(),
            0o600,
        )
    changed: list[str] = []
    receipt = state / "installation.json"
    try:
        for change in plan.changes:
            if read(change.path) != change.before:
                raise ValueError("install-target-changed")
            atomic_bytes(change.path, change.after, change.mode)
            changed.append(str(change.path))
    finally:
        # A partial/cancelled application never claims completion. Retry is preserving.
        report = {
            "baselineSha256": plan.baseline_sha256,
            "status": "installed" if len(changed) == len(plan.changes) else "partial-install",
            "planId": plan.identity,
            "changed": changed,
            "files": {
                name: digest
                for name, digest in plan.files.items()
                if sha(read(Path(name))) == digest
            },
            "backup": str(backup),
            "trust": "unchanged; native Codex hook review may be required",
        }
        atomic_bytes(receipt, (json.dumps(report, sort_keys=True) + "\n").encode(), 0o600)
    return {**report, "receipt": str(receipt)}


def inventory(home: Path, source: Path) -> list[dict[str, object]]:
    expected = (source / "B0.md").read_bytes()
    resources: list[dict[str, object]] = []
    for directory in (home / ".codex", home / ".pi/agent"):
        path = directory / "AGENTS.md"
        raw = read(path)
        managed = block(raw) if raw is not None else None
        resources.append(
            {
                "path": str(path),
                "sha256": sha(raw),
                "managedSha256": sha(managed),
                "matchesSource": managed == expected,
                "baselineOccurrences": raw.count(HEADER) if raw else 0,
                "overridePresent": (directory / "AGENTS.override.md").exists(),
            }
        )
    return resources
