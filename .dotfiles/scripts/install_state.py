"""Plan identities, private recovery state and the shared HOME installer lock."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(data: object) -> bytes:
    return (json.dumps(data, sort_keys=True, ensure_ascii=True) + "\n").encode()


@contextmanager
def apply_lock(state: Path) -> Iterator[None]:
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(
        os.open(
            state / "apply.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600
        ),
        "r+",
    ) as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise OSError("expected a regular installer lock")
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield
