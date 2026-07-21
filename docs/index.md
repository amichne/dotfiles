# Dotfiles knowledge base

This site explains how the validated Zsh runtime resolves configuration, loads
trusted plugins, scopes credentials, and changes a home directory safely.

## Choose a path

- Start with the [target architecture](architecture.md) for repository
  boundaries and data flow.
- Use the [configuration guide](configuration.md) to select profiles and set
  typed values.
- Read the [behavioral contract](behavioral-contract.md) for compatibility and
  safety requirements.
- Follow [migration](migration.md) or [operations](operations.md) when changing
  a machine.
- Browse the [source-backed knowledge bundle](knowledge/index.md) for compact
  concepts tied to implementation files.

## Verify the repository

Run the project gate from the repository root:

```sh
./scripts/check.sh
```

The knowledge bundle is separately checked for valid Open Knowledge Format
frontmatter and existing source references.
