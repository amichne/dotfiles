---
type: Runtime Flow
title: Runtime architecture
description: How the management CLI and interactive Zsh runtime share validated libraries.
resource: file://bin/dotfiles
tags: [bash, zsh, cli, runtime]
timestamp: 2026-07-21T00:00:00Z
code_sources:
  - path: bin/dotfiles
    lines: "1-98"
    symbols: [dotfiles_main, dotfiles_usage]
  - path: shell/zsh/entrypoint.zsh
    lines: "1-65"
    symbols: [dotfiles_runtime_load]
  - path: lib/status.sh
    symbols: [dotfiles_status_command, dotfiles_doctor_command]
---

# Runtime architecture

`bin/dotfiles` is the management entrypoint. It resolves the repository root,
loads the portable Bash libraries in a fixed order, and dispatches each public
subcommand through `dotfiles_main`.

The interactive boundary is `shell/zsh/entrypoint.zsh`. It imports resolved
configuration and plugin state into Zsh without making the management CLI a
second runtime owner.

## Command flow

```mermaid
flowchart LR
  CLI[bin/dotfiles] --> Libraries[lib/*.sh]
  Schema[config/schema.tsv] --> Libraries
  Libraries --> State[validated state]
  State --> Doctor[status and doctor]
  State --> Zsh[shell/zsh/entrypoint.zsh]
  Zsh --> Plugins[validated plugins]
```

The split keeps configuration parsing and validation in shared libraries while
leaving interactive shell behavior at the Zsh boundary.

## Evidence

- `bin/dotfiles:8-29` fixes library load order; `bin/dotfiles:50-95` owns public
  command dispatch.
- `shell/zsh/entrypoint.zsh` consumes validated runtime state before sourcing
  plugins.
- `lib/status.sh` exposes effective state through `status` and `doctor`.

See the broader [architecture guide](../architecture.md).
