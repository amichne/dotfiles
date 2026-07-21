---
type: Runtime Flow
title: Plugin runtime
description: Manifest-owned plugin discovery constrained by typed feature and dependency state.
resource: file://config/plugins.tsv
tags: [plugins, dependencies, trust, zsh]
timestamp: 2026-07-21T00:00:00Z
code_sources:
  - path: config/plugins.tsv
  - path: config/dependencies.tsv
  - path: lib/plugins.sh
    symbols: [dotfiles_plugins_normalize, dotfiles_plugin_physical_path, dotfiles_plugins_make_state]
  - path: lib/dependencies.sh
    symbols: [dotfiles_dependency_available, dotfiles_dependency_hint]
  - path: tests/plugins_test.sh
---

# Plugin runtime

Plugins enter the runtime only through `config/plugins.tsv` or a manifest in a
declared external root. Every row names an id, relative file, feature key,
shell, dependency list, and description.

## Trust and availability

`lib/plugins.sh` normalizes manifests, rejects duplicate ids and unsafe paths,
and resolves plugin files to physical paths inside trusted roots. Dependency
probes and install hints come from `config/dependencies.tsv` through
`lib/dependencies.sh`.

Feature state controls the result:

| State | Runtime contract |
| --- | --- |
| `on` | The plugin and every dependency are required. |
| `auto` | The plugin loads only when dependencies are available. |
| `off` | The plugin is not probed or loaded. |

The resulting state file is the only plugin list consumed by the Zsh
entrypoint; the runtime does not recursively discover shell files.

## Evidence

- `config/plugins.tsv` owns the portable plugin inventory.
- `lib/plugins.sh` validates row shape, trusted roots, physical files, and
  dependency state.
- `tests/plugins_test.sh` verifies manifest and feature-state behavior.

See the normative [behavioral contract](../behavioral-contract.md).
