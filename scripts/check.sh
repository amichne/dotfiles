#!/bin/sh
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd -P)
exec uv run --locked --project "$root" python "$root/scripts/check.py"
