# Dotfiles

A validated, portable Zsh environment derived from the checked-in Apollo and
Artemis implementations, their history, and sanitized evidence from real CLI
usage.

The project keeps the short workflow (`l`, `zs`, `rr`, `f`, `main`, `push`, and
`commit`) while replacing ambient shell code with typed data, manifest-owned
plugins, explicit dependency checks, atomic migration, and command-scoped
credentials.

## Start safely

Nothing in this repository automatically changes the live home directory.

```sh
./scripts/check.sh
./bin/dotfiles profile set personal
./bin/dotfiles doctor
./bin/dotfiles install plan
```

The current machine has both Apollo and Artemis startup blocks. After reviewing
the plan and backing up `~/.zshrc`, migrate explicitly:

```sh
./bin/dotfiles install apply --migrate
exec zsh -l
```

Static public files are a separate opt-in step:

```sh
./bin/dotfiles home plan
./bin/dotfiles home apply
```

`home apply` manages only public Git defaults, the global ignore file, Atuin
behavior, Vim, and IdeaVim. It does not manage `gh/hosts.yml`, SSH keys, auth
databases, tokens, Git identity, or enterprise host state.

## Commands

```text
dotfiles config validate|list|export
dotfiles profile get|set
dotfiles plugins validate|list|paths
dotfiles status
dotfiles doctor [--strict]
dotfiles install plan|apply|uninstall
dotfiles credential exec github -- <command>
dotfiles proxy exec -- <command>
dotfiles home plan|apply|status
dotfiles migrate apollo plan|render --source <path>
```

Use `doctor` for normal operation: unavailable `auto` integrations are
explained and skipped. Use `doctor --strict` when provisioning a machine and
every selected optional dependency must be present.

## Design boundaries

- Configuration is `key=value` data validated by
  [`config/schema.tsv`](config/schema.tsv); profile files are never sourced.
- Feature state is `on`, `off`, or `auto`.
- Startup is offline, non-interactive, idempotent, and performs no credential
  lookup.
- Plugins must appear in a validated manifest and remain inside a trusted
  physical root.
- Authenticated proxies, GitHub tokens, and enterprise CA variables exist only
  in the child command that requests them.
- The shell does not install dependencies. It reports approved-provider hints.
- Chezmoi is an optional static deployment adapter, not a runtime dependency.

See [configuration](docs/configuration.md), [migration](docs/migration.md),
[operations](docs/operations.md), and the
[behavioral contract](docs/behavioral-contract.md).
