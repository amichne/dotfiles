#!/usr/bin/env -S uv run --locked --script
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["pydantic==2.12.3", "pytest==8.4.2"]
# [tool.uv]
# no-build = true
# required-version = ">=0.12.9"
# [[tool.uv.index]]
# name = "pypi"
# url = "https://pypi.org/simple"
# default = true
# ///
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import signal
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Literal

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.install import links_for
from cutover.recovery import (
    PATHS,
    Entry,
    Image,
    Journal,
    Kind,
    Observation,
    Parent,
    Phase,
    Refused,
    Restored,
    admissible,
    admit_parents,
    image,
    locked,
    parents,
    phase,
    read_journal,
    recover,
    restore_locked,
    save_journal,
    status,
    sync_directory,
    write_json,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
)

ROOT = Path(__file__).resolve().parent.parent
DECISIONS = ("cfg-inspect", "pi-shell-edit", "work-dashboard")
type Sha = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{40}$")]
type Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
type LegacyGit = Literal[".cfg/repo.git", ".local/share/config/repo.git"]


class Data(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Admission(Data):
    path: str
    kind: Kind
    digest: Digest
    owner: Literal["absent", "unreviewed", "legacy-config", "dotfiles"]

    @field_validator("path")
    @classmethod
    def admitted_path(cls, value: str) -> str:
        if value not in PATHS:
            raise ValueError("path outside the replacement inventory")
        return value

    def before(self) -> Image:
        return Image(self.kind, self.digest)


class GitIdentity(Data):
    root: str
    git_dir: str
    bare: Literal["true", "false"]
    head: Sha
    tree: Sha
    refs: Digest
    index: Image
    worktrees: Digest
    registered_worktrees: Annotated[int, Field(ge=1)]


class ReadInput(Data):
    path: str
    resolved: str
    link: Image
    content: Image


class Inventory(Data):
    version: Literal[1] = 1
    home: str
    selected_git: LegacyGit
    legacy: GitIdentity
    entries: tuple[Admission, ...]
    decisions: Mapping[str, Literal["unresolved", "retire"]]


class Text(Data):
    kind: Literal["text"] = "text"
    content: str
    mode: Literal[384] = 0o600


class Link(Data):
    kind: Literal["link"] = "link"
    target: str


class Retire(Data):
    kind: Literal["retire"] = "retire"


type Replacement = Annotated[Text | Link | Retire, Field(discriminator="kind")]


class Change(Admission):
    replacement: Replacement
    after: Image


class Plan(Data):
    version: Literal[1] = 1
    home: str
    archive: str
    source: GitIdentity
    interpreter: str
    interpreter_image: Image
    legacy: GitIdentity
    selected_git: LegacyGit
    decisions: Mapping[str, Literal["retire"]]
    parents: tuple[Parent, ...]
    inputs: tuple[ReadInput, ...]
    entries: tuple[Change, ...]


def environment(home: Path) -> dict[str, str]:
    return {
        "HOME": str(home),
        "PATH": os.environ.get("PATH", os.defpath),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "XDG_STATE_HOME": str(home / ".local/state"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
    }


def inputs(home: Path) -> tuple[ReadInput, ...] | Refused:
    selected: list[str] = []
    for arguments in (["config", "validate"], ["plugins", "paths"]):
        result = subprocess.run(
            [str(ROOT / "bin/dotfiles"), *arguments],
            env=environment(home),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            return Refused("native configuration or plugin admission failed")
        if arguments == ["plugins", "paths"]:
            selected = result.stdout.splitlines()
    paths = [
        str(home / ".config/dotfiles/config.conf"),
        str(home / ".config/dotfiles/profiles"),
        *selected,
    ]
    guarded: list[ReadInput] = []
    for name in sorted(set(paths)):
        path = Path(name)
        resolved = path.resolve()
        guarded.append(
            ReadInput(
                path=name,
                resolved=str(resolved),
                link=image(path),
                content=image(resolved),
            )
        )
    return tuple(guarded)


def git_identity(
    root: Path, metadata: Path | None = None, *, clean: bool = False
) -> GitIdentity | Refused:
    prefix = ["git", "--no-optional-locks", "-C", str(root), "-c", "core.fsmonitor=false"]
    if metadata is not None:
        prefix += [f"--git-dir={metadata}", f"--work-tree={root}"]
    outputs: list[bytes] = []
    commands = [
        ["rev-parse", "--absolute-git-dir"],
        ["config", "--get", "core.bare"],
        ["rev-parse", "HEAD"],
        ["rev-parse", "HEAD^{tree}"],
        ["show-ref"],
        ["worktree", "list", "--porcelain", "-z"],
    ]
    if clean:
        commands.append(["status", "--porcelain=v1", "--untracked-files=all"])
    for arguments in commands:
        result = subprocess.run(
            [*prefix, *arguments],
            env=environment(root),
            capture_output=True,
            check=False,
        )
        if result.returncode:
            return Refused(f"Git identity unavailable at {root}")
        outputs.append(result.stdout)
    if clean and outputs[-1]:
        return Refused("source must be a clean committed checkout")
    git_dir, bare, head, tree = (value.decode().strip() for value in outputs[:4])
    return GitIdentity.model_validate_json(
        json.dumps(
            {
                "root": str(root),
                "git_dir": git_dir,
                "bare": bare,
                "head": head,
                "tree": tree,
                "refs": hashlib.sha256(outputs[4]).hexdigest(),
                "worktrees": hashlib.sha256(outputs[5]).hexdigest(),
                "registered_worktrees": sum(
                    field.startswith(b"worktree ") for field in outputs[5].split(b"\0")
                ),
                "index": asdict(image(Path(git_dir) / "index")),
            }
        )
    )


def physical(path: Path) -> bool:
    return (
        path.is_absolute()
        and path.resolve() == path
        and "\n" not in str(path)
        and "\r" not in str(path)
    )


def inventory(home: Path, selected: str | None) -> Inventory | Refused:
    if not physical(home) or not home.is_dir() or home == Path("/"):
        return Refused("HOME must name an existing physical absolute directory")
    candidates = [
        name for name in (".cfg/repo.git", ".local/share/config/repo.git") if (home / name).is_dir()
    ]
    if selected is None:
        if len(candidates) != 1:
            return Refused("select one legacy Git directory with --legacy-git")
        selected = candidates[0]
    if selected not in candidates:
        return Refused("selected legacy Git directory is unavailable")
    if (home / selected).is_symlink():
        return Refused("legacy Git metadata must use a physical directory")
    guarded = parents(home, PATHS)
    if isinstance(guarded, Refused):
        return guarded
    legacy = git_identity(home, home / selected)
    if isinstance(legacy, Refused):
        return legacy
    if legacy.registered_worktrees != 1:
        return Refused("registered legacy worktrees must be retired separately")
    for name in candidates:
        if (home / name).is_symlink():
            return Refused("legacy Git metadata must use physical directories")
        identity = git_identity(home, home / name)
        if isinstance(identity, Refused):
            return identity
        if identity.registered_worktrees != 1:
            return Refused("registered legacy worktrees must be retired separately")
    entries: list[Admission] = []
    for name in PATHS:
        before = image(home / name)
        entries.append(
            Admission(
                path=name,
                kind=before.kind,
                digest=before.digest,
                owner="absent" if before.kind == Kind.ABSENT else "unreviewed",
            )
        )
    return Inventory.model_validate_json(
        json.dumps(
            {
                "home": str(home),
                "selected_git": selected,
                "legacy": legacy.model_dump(),
                "entries": [entry.model_dump() for entry in entries],
                "decisions": dict.fromkeys(DECISIONS, "unresolved"),
            }
        )
    )


def replacements(home: Path) -> dict[str, Replacement] | Refused:
    with tempfile.TemporaryDirectory(prefix="dotfiles-render-") as temporary:
        staging = Path(temporary)
        result = subprocess.run(
            [str(ROOT / "bin/dotfiles"), "install", "apply"],
            env=environment(staging),
            capture_output=True,
            check=False,
        )
        if result.returncode:
            return Refused("normal installer could not render the entrypoint")
        result_map: dict[str, Replacement] = dict.fromkeys(PATHS, Retire())
        result_map[".zshrc"] = Text(content=(staging / ".zshrc").read_text())
    for link in links_for(home, home / ".config"):
        result_map[link.destination.relative_to(home).as_posix()] = Link(target=str(link.source))
    result_map[".local/bin/dotfiles"] = Link(target=str(ROOT / "bin/dotfiles"))
    return result_map


def materialize(path: Path, replacement: Replacement) -> None:
    match replacement:
        case Text(content=content, mode=mode):
            with path.open("x", encoding="utf-8") as output:
                _ = output.write(content)
                output.flush()
                os.fsync(output.fileno())
            path.chmod(mode)
        case Link(target=target):
            path.symlink_to(target)
        case Retire():
            pass


def make_plan(admitted: Inventory, archive: Path) -> Plan | Refused:
    home = Path(admitted.home)
    actual = inventory(home, admitted.selected_git)
    if isinstance(actual, Refused):
        return actual
    if actual.legacy != admitted.legacy or tuple(
        (entry.path, entry.before()) for entry in actual.entries
    ) != tuple((entry.path, entry.before()) for entry in admitted.entries):
        return Refused("inventory preimages or Git identity changed")
    if set(admitted.decisions) != set(DECISIONS) or set(admitted.decisions.values()) != {"retire"}:
        return Refused("resolve every legacy feature decision before the cutover")
    if (
        not physical(archive)
        or not archive.parent.is_dir()
        or archive.exists()
        or archive.is_symlink()
    ):
        return Refused("archive must be a new physical path with an existing parent")
    if archive == home or archive.is_relative_to(ROOT) or ROOT.is_relative_to(archive):
        return Refused("archive overlaps HOME or the source")
    for name in PATHS:
        target = home / name
        if (
            archive.is_relative_to(target)
            or target.is_relative_to(archive)
            or ROOT.is_relative_to(target)
        ):
            return Refused("inventory overlaps the archive or selected source")
        if (
            target.exists() or target.is_symlink()
        ) and target.lstat().st_dev != archive.parent.stat().st_dev:
            return Refused("archive and preimages must use the same filesystem")
    source = git_identity(ROOT, clean=True)
    if isinstance(source, Refused):
        return source
    consumed = inputs(home)
    if isinstance(consumed, Refused):
        return consumed
    python = Path(sys.executable).resolve()
    if (
        not physical(python)
        or python.is_relative_to(ROOT)
        or any(python.is_relative_to(home / name) for name in PATHS)
    ):
        return Refused("recovery needs a shared Python interpreter outside the retired source")
    intended = replacements(home)
    if isinstance(intended, Refused):
        return intended
    guarded = parents(home, PATHS)
    if isinstance(guarded, Refused):
        return guarded
    for name, replacement in intended.items():
        if not isinstance(replacement, Retire) and not (home / name).parent.is_dir():
            return Refused(
                f"create the replacement parent before inventory: {(home / name).parent}"
            )
    for name, replacement in intended.items():
        if (
            not isinstance(replacement, Retire)
            and (home / name).parent.stat().st_dev != archive.parent.stat().st_dev
        ):
            return Refused("replacement parents and archive must use the same filesystem")
    changes: list[Change] = []
    with tempfile.TemporaryDirectory(prefix="dotfiles-images-") as temporary:
        for index, entry in enumerate(admitted.entries):
            target = Path(temporary) / str(index)
            replacement = intended[entry.path]
            materialize(target, replacement)
            after = image(target)
            if (
                entry.owner == "unreviewed"
                or (entry.kind == Kind.ABSENT and entry.owner != "absent")
                or (entry.kind != Kind.ABSENT and entry.owner not in ("legacy-config", "dotfiles"))
                or (entry.owner == "dotfiles" and entry.before() != after)
            ):
                return Refused(f"ownership is not admitted: {entry.path}")
            changes.append(
                Change(
                    path=entry.path,
                    kind=entry.kind,
                    digest=entry.digest,
                    owner=entry.owner,
                    replacement=replacement,
                    after=after,
                )
            )
    return Plan.model_validate_json(
        json.dumps(
            {
                "home": str(home),
                "archive": str(archive),
                "source": source.model_dump(),
                "interpreter": str(python),
                "interpreter_image": asdict(image(python)),
                "legacy": admitted.legacy.model_dump(),
                "selected_git": admitted.selected_git,
                "decisions": admitted.decisions,
                "parents": [asdict(parent) for parent in guarded],
                "inputs": [item.model_dump(mode="json") for item in consumed],
                "entries": [change.model_dump(mode="json") for change in changes],
            }
        )
    )


def journal_for(plan: Plan) -> Journal:
    return Journal(
        Path(plan.home),
        plan.parents,
        tuple(Entry(change.path, change.before(), change.after) for change in plan.entries),
        hashlib.sha256(plan.model_dump_json().encode()).hexdigest(),
    )


def preflight(plan: Plan) -> Refused | None:
    if plan.source.root != str(ROOT):
        return Refused("plan belongs to another source")
    rejected = admit_parents(Path(plan.home), plan.parents)
    if rejected:
        return rejected
    if Path(plan.interpreter) != Path(sys.executable).resolve():
        return Refused("plan names an unadmitted recovery interpreter")
    source = git_identity(ROOT, clean=True)
    if source != plan.source:
        return Refused("source identity or committed contents changed")
    if image(Path(plan.interpreter)) != plan.interpreter_image:
        return Refused("recovery interpreter changed")
    if inputs(Path(plan.home)) != plan.inputs:
        return Refused("configuration or selected plugin inputs changed")
    return None


def fresh_shell(plan: Plan) -> Refused | None:
    home = Path(plan.home)
    child = environment(home)
    child["PATH"] = f"{home / '.local/bin'}:{child['PATH']}"
    child["DOTFILES_EXPECTED_ROOT"] = plan.source.root
    probe = (
        "unset HISTFILE; "
        '[[ "$DOTFILES_RUNTIME_LOADED" == 1 && "$DOTFILES_RUNTIME_ROOT" == "$DOTFILES_EXPECTED_ROOT" '
        '&& "$(whence -p ai)" == "$HOME/.local/bin/ai" '
        '&& "$(whence -p dotfiles)" == "$HOME/.local/bin/dotfiles" ]]'
    )
    result = subprocess.run(
        ["zsh", "-dlic", probe],
        env=child,
        cwd=home,
        capture_output=True,
        check=False,
    )
    write_json(
        Path(plan.archive) / "acceptance.json",
        {
            "source": plan.source.head,
            "shell": "zsh -dlic",
            "exit": result.returncode,
        },
    )
    return Refused("fresh-shell acceptance failed") if result.returncode else None


def apply(plan: Plan) -> Literal[Observation.APPLIED] | Refused:
    archive = Path(plan.archive)
    journal = journal_for(plan)
    with locked(journal.home):
        rejected = preflight(plan)
        if rejected:
            return rejected
        if archive.exists():
            if read_journal(archive) != journal:
                return Refused("archive belongs to another plan")
            rejected = admissible(archive, journal)
            if rejected:
                return rejected
            if phase(archive) == Phase.APPLIED and all(
                image(journal.home / entry.path) == entry.after for entry in journal.entries
            ):
                return Observation.APPLIED
            return Refused(
                "incomplete or recovered cutover. Use archive recovery and create a new plan."
            )
        admitted = Inventory(
            home=plan.home,
            selected_git=plan.selected_git,
            legacy=plan.legacy,
            decisions=plan.decisions,
            entries=tuple(
                Admission(
                    path=change.path, kind=change.kind, digest=change.digest, owner=change.owner
                )
                for change in plan.entries
            ),
        )
        regenerated = make_plan(admitted, archive)
        if isinstance(regenerated, Refused):
            return regenerated
        if regenerated != plan:
            return Refused("plan contents differ from the admitted source")
        archive.mkdir(mode=0o700)
        for name in ("before", "after", "discard"):
            (archive / name).mkdir(mode=0o700)
        _ = (archive / "recovery.py").write_bytes((ROOT / "cutover/recovery.py").read_bytes())
        launcher = f"#!/bin/sh\nexec {shlex.quote(plan.interpreter)} -I -S {shlex.quote(str(archive / 'recovery.py'))}\n"
        _ = (archive / "recover").write_text(launcher)
        (archive / "recover").chmod(0o700)
        for name in ("recovery.py", "recover"):
            with (archive / name).open("rb") as content:
                os.fsync(content.fileno())
        for index, change in enumerate(plan.entries):
            materialize(archive / "after" / str(index), change.replacement)
        with (archive / "plan.json").open("x", encoding="utf-8") as approved:
            _ = approved.write(plan.model_dump_json())
            approved.flush()
            os.fsync(approved.fileno())
        save_journal(archive, journal)
        for name in ("before", "after", "discard"):
            sync_directory(archive / name)
        sync_directory(archive.parent)
        try:
            for index, entry in enumerate(journal.entries):
                if entry.before == entry.after:
                    continue
                rejected = preflight(plan)
                if rejected:
                    return rejected
                for earlier, candidate in enumerate(journal.entries):
                    expected = candidate.after if earlier < index else candidate.before
                    if image(journal.home / candidate.path) != expected:
                        return Refused(f"path drift before replacement: {candidate.path}")
                target = journal.home / entry.path
                if entry.before.kind != Kind.ABSENT:
                    os.replace(target, archive / "before" / str(index))
                    sync_directory(target.parent)
                    sync_directory(archive / "before")
                if entry.after.kind != Kind.ABSENT:
                    rejected = preflight(plan) or admissible(archive, journal)
                    if rejected:
                        return rejected
                    if image(archive / "after" / str(index)) != entry.after:
                        return Refused(f"staged replacement changed: {entry.path}")
                    os.replace(archive / "after" / str(index), target)
                    sync_directory(target.parent)
                    sync_directory(archive / "after")
            rejected = preflight(plan) or fresh_shell(plan)
            if rejected:
                restored = restore_locked(archive, journal)
                if isinstance(restored, Refused):
                    return Refused(
                        f"fresh-shell failed. Recovery needed: {restored.detail}. Archive: {archive}"
                    )
                return rejected
            if not all(
                image(journal.home / entry.path) == entry.after for entry in journal.entries
            ):
                return Refused("postimages changed before completion")
            write_json(archive / "state.json", {"status": Phase.APPLIED})
            return Observation.APPLIED
        except (OSError, KeyboardInterrupt):
            restored = restore_locked(archive, journal)
            if isinstance(restored, Refused):
                print(
                    f"cutover: recovery needed: {restored.detail}. Archive: {archive}",
                    file=sys.stderr,
                )
            raise


def main(arguments: list[str]) -> int:
    if arguments == ["--self-test"]:
        import pytest

        return int(
            pytest.main(
                [
                    str(ROOT / "cutover/test_cutover.py")
                    + "::test_inventory_and_plan_are_read_only",
                    str(ROOT / "cutover/test_cutover.py") + "::test_apply_and_independent_recovery",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                ]
            )
        )
    parser = argparse.ArgumentParser(
        description="Reviewable Zsh cutover with guarded local recovery"
    )
    sub = parser.add_subparsers(dest="action", required=True)
    discover = sub.add_parser("inventory")
    _ = discover.add_argument("--home", type=Path, required=True)
    _ = discover.add_argument(
        "--legacy-git", choices=(".cfg/repo.git", ".local/share/config/repo.git")
    )
    planning = sub.add_parser("plan")
    _ = planning.add_argument("--inventory", type=Path, required=True)
    _ = planning.add_argument("--archive", type=Path, required=True)
    installing = sub.add_parser("apply")
    _ = installing.add_argument("--plan", type=Path, required=True)
    for name in ("recover", "status"):
        command = sub.add_parser(name)
        _ = command.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args(arguments)
    try:
        result: Inventory | Plan | Refused | Restored | Observation
        match args.action:
            case "inventory":
                result = inventory(args.home, args.legacy_git)
            case "plan":
                result = make_plan(
                    Inventory.model_validate_json(args.inventory.read_text()), args.archive
                )
            case "apply":
                result = apply(Plan.model_validate_json(args.plan.read_text()))
            case "recover":
                result = recover(args.archive)
            case "status":
                result = status(args.archive)
            case _:
                return 64
        if isinstance(result, Refused):
            print(f"cutover: {result.detail}", file=sys.stderr)
            print(json.dumps({"status": "rejected", "detail": result.detail}))
            return 75
        if isinstance(result, (Inventory, Plan)):
            print(result.model_dump_json(indent=2))
        else:
            print(json.dumps({"status": "recovered" if isinstance(result, Restored) else result}))
        return 75 if result == Observation.DRIFTED else 8 if result == Observation.INCOMPLETE else 0
    except (ValidationError, ValueError) as error:
        print(f"cutover: invalid input: {error}", file=sys.stderr)
        return 65
    except OSError as error:
        print(f"cutover: local operation stopped: {error}", file=sys.stderr)
        return 74
    except KeyboardInterrupt:
        print("cutover: interrupted. Examine the recovery archive.", file=sys.stderr)
        return 130


def interrupted(_signal: int, _frame: object) -> None:
    raise KeyboardInterrupt


if __name__ == "__main__":
    _ = signal.signal(signal.SIGTERM, interrupted)
    raise SystemExit(main(sys.argv[1:]))
