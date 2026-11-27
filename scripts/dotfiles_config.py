"""Reconcile the user's TOML with the defaults shipped in the checkout."""

from __future__ import annotations

import json
import tomllib
from typing import TypeGuard


def table(value: object) -> TypeGuard[dict[str, object]]:
    return isinstance(value, dict)


def array(value: object) -> TypeGuard[list[object]]:
    return isinstance(value, list)


def literal(value: object) -> str:
    # The config supports strings, integers, booleans and arrays of strings.
    # JSON uses compatible escapes for these values except a literal DEL.
    if not isinstance(value, (str, int)) and not (
        array(value) and all(isinstance(item, str) for item in value)
    ):
        raise ValueError("unsupported value for a dotfiles setting")
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f")


def reconcile(defaults: bytes, previous: bytes | None) -> bytes:
    schema: dict[str, object] = json.loads(defaults)
    current: dict[str, object] = tomllib.loads(previous.decode()) if previous is not None else {}
    sections: list[str] = []

    def visit(path: tuple[str, ...], keys: dict[str, object], values: dict[str, object]) -> None:
        lines = ["[" + ".".join(path) + "]"] if path else []
        children: list[tuple[str, dict[str, object], dict[str, object]]] = []
        for key, default in keys.items():
            value = values.get(key, default)
            if table(default):
                if not table(value):
                    raise ValueError(f"expected a table at {'.'.join((*path, key))}")
                children.append((key, default, value))
            elif value is not None:
                lines.append(f"{key} = {literal(value)}")
        if lines:
            sections.append("\n".join(lines))
        for key, child_keys, child_values in children:
            visit((*path, key), child_keys, child_values)

    visit((), schema, current)
    rendered = "\n\n".join(sections) + "\n"
    if previous is not None and tomllib.loads(rendered) == current:
        return previous
    return rendered.encode()
