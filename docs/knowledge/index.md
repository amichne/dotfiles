---
okf_version: "1.0"
---

# Source-backed concepts

This Open Knowledge Format bundle gives agents and maintainers a compact route
from project concepts to the files that enforce them.

## Concepts

- [Runtime architecture](runtime-architecture.md) maps CLI dispatch to the Zsh
  entrypoint and runtime libraries.
- [Configuration model](configuration-model.md) records the typed schema and
  layer precedence.
- [Plugin runtime](plugin-runtime.md) describes manifest validation, dependency
  state, and trusted-root loading.
- [Safe operations](safe-operations.md) covers installer ownership, static-home
  deployment, and command-scoped secrets.

## Validation

From the repository root, run:

```sh
python3 /Users/amichne/.codex/plugins/cache/slopsentral/code-knowledge-base/0.1.0/skills/code-knowledge-base/scripts/code_kb.py \
  check --repo . --docs docs/knowledge --strict
zensical build --clean
```
