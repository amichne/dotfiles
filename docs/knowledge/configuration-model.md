---
type: Configuration Contract
title: Configuration model
description: Typed schema validation and deterministic configuration precedence.
resource: file://config/schema.tsv
tags: [configuration, schema, profiles, validation]
timestamp: 2026-07-21T00:00:00Z
code_sources:
  - path: config/schema.tsv
  - path: lib/config.sh
    lines: "3-350"
    symbols: [dotfiles_config_collect_layers, dotfiles_config_resolve]
  - path: lib/profile.sh
    symbols: [dotfiles_profile_selected, dotfiles_profile_command]
  - path: tests/config_validation_test.sh
---

# Configuration model

`config/schema.tsv` is the public authority for configuration keys. Each row
declares the key, value type, default, runtime variable, optional process
override, and description.

## Resolution boundary

`dotfiles_config_collect_layers` selects tracked profiles, external profile
files, and the machine-local file. `dotfiles_config_resolve` parses those files
as data and rejects unknown keys, duplicate layer entries, invalid types, and
unsupported placeholders before values reach runtime code.

Precedence runs from schema defaults through selected profiles and local data
to declared process overrides. Profile selection is itself validated and
stored separately by `lib/profile.sh`.

## Supported value families

The resolver implements a small set of explicit types: booleans, feature
toggles, unsigned integers, commands, enums, paths, path lists, URLs, CSV,
strings, and secret references. Only `${HOME}`, `${XDG_CONFIG_HOME}`, and
`${DOTFILES_ROOT}` placeholders are expanded.

## Evidence

- `config/schema.tsv` enumerates every supported public key and override.
- `lib/config.sh:65-260` validates schema rows and profile data before emitting
  effective values.
- `tests/config_validation_test.sh` exercises invalid and valid boundary cases.

See the task-oriented [configuration guide](../configuration.md).
