# Operations and maintenance

## Verification

Run the repository gate before migration and after every change:

```sh
./scripts/check.sh
```

It runs every disposable-home behavior suite, Bash and Zsh syntax checks,
warning-level ShellCheck, schema validation, plugin/dependency validation, and
Git whitespace checks.

## Update

The managed `.zshrc` block points at this checkout, so code updates do not copy
runtime files into the home directory.

```sh
git pull --ff-only
./scripts/check.sh
./bin/dotfiles doctor
exec zsh -l
```

Re-run `install apply` only when installer ownership changes. Run `home plan`
before `home apply` whenever static home files change.

## Update Codex configuration

The `home/private_dot_codex` source owns durable, credential-free Codex
preferences: `config.toml`, global `AGENTS.md`, keybindings, browser and
computer-use preferences, and automation definitions. Keep `config.toml`
private on disk because Codex or a local operator may add credential-backed
settings later.

Do not copy `auth.json`, history, sessions, memories, caches, generated plugin
contents, marketplace snapshots, native-host state, or automation memory into
the repository. Static MCP headers that contain credentials are also excluded;
configure those locally or through an environment-backed header after applying
the tracked configuration on another machine.

Preview and apply updates with:

```sh
./bin/dotfiles home plan
./bin/dotfiles home apply
```

## Add a configuration key

1. Add one typed row to `config/schema.tsv`.
2. Add a failing public behavior test for validation and runtime use.
3. Implement the consumer without sourcing or evaluating config data.
4. Document the knob and run the full gate.

Do not read undeclared ambient variables from plugins. A process override must
be named in the schema.

## Add a plugin

1. Decide whether it is portable, optional integration, or enterprise-owned.
2. Declare every capability in `config/dependencies.tsv`.
3. Add the plugin to `config/plugins.tsv` with a `feature.*` toggle or `-`.
4. Keep startup offline and idempotent.
5. Test `on`, `auto`, `off`, missing dependency, and repeated source behavior.

External enterprise roots follow the same manifest contract and cannot
override built-in IDs.

## Secrets and hosts

- Keep secret values in `gh`, an OS keychain, 1Password, `pass`, or an
  enterprise provider.
- Keep only provider references in machine config.
- Never add active `gh/hosts.yml`, SSH private keys, auth databases, tokens, or
  company host inventories to `home/`, `config/`, or `profiles/`. This includes
  static credential headers in Codex `config.toml`.
- Prefer command-scoped `with-github-token` and `with-proxy` wrappers.
- Run `dotfiles status` and `dotfiles doctor`; neither prints secret references.

## Performance

On the source machine, the current Apollo+Artemis login shell measured about
0.89–0.92 seconds. This runtime with the personal profile measured about
0.52–0.57 seconds warm after SDKMAN became lazy. Treat these as local comparison
numbers, not cross-machine thresholds. The runtime test enforces idempotence;
future performance gates should use a report-only percentile benchmark to avoid
hardware-specific false failures.
