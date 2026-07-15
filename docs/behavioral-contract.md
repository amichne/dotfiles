# Behavioral and parity contract

This ledger is the migration authority. A legacy behavior is not carried into
the new runtime merely because it exists; it must have an explicit disposition.

## Core behavior

Core is always loaded and has no optional third-party dependency.

| Capability | Contract |
| --- | --- |
| Configuration | Parse data-only files against a declared schema before applying any value. Unknown keys, duplicate keys in one layer, invalid types, and invalid enum values fail. |
| Precedence | Schema default, selected profiles from left to right, machine-local config, then a declared per-key process environment override. |
| Startup | Deterministic, idempotent, offline, non-interactive, and free of writes except an explicit cache contract. No credential lookup. |
| Feature state | `on`, `off`, or `auto`. `on` requires its declared dependencies, `auto` loads only when available, and `off` never loads. |
| Plugins | Load only entries from validated manifests whose physical files remain inside declared trusted roots. |
| Diagnostics | `dotfiles status`, `dotfiles doctor`, `dotfiles config list`, and `dotfiles plugins list` explain effective state and ownership without revealing secrets. |
| Installation | Previewable and idempotent. One managed Zsh block, one owner, preserved surrounding user content, atomic replacement, and explicit uninstall. |

## Compatibility ledger

| Existing surface | Disposition | New contract |
| --- | --- | --- |
| `l` | preserve | `ls -lah`; no optional dependency. |
| `zs` | preserve, repair | Reload only this runtime, return meaningful status, and never duplicate `PATH`, hooks, or widgets. |
| `main` | preserve, repair | Fetch and switch to the repository's configured default branch; refuse destructive surprises and preserve Git exit status. |
| `push` | preserve | Push the current branch with upstream to the configured remote. |
| `commit` | preserve behind personal UX pack | Prefix a detected ticket when configured. Staging policy is typed as `none`, `tracked`, or `all`; portable default is `none`, personal profile may select `all` for legacy behavior. |
| repository-root navigation | preserve, repair | `rr` changes to the Git worktree root instead of executing the path. |
| `f` search helper | preserve, repair | Prefer `rg`, fall back to `grep`, validate arity, and preserve tool exit status. |
| Atuin `Ctrl-R` | preserve as `auto` integration | Load once when available; native Zsh history remains configured when absent. |
| zoxide | preserve as `auto` integration | Load once when available; never call a missing command during startup. |
| SDKMAN, Warp, Starship | optional integrations | Each has its own typed feature and dependency check. No hard-coded enablement. |
| Git/PR/Gradle/Jira helpers | split into packs | Portable Git helpers, personal developer helpers, and enterprise ticket/host helpers have separate ownership. |
| Apollo asset/provider management | out of shell runtime | Keep in a dedicated agent/tooling project or a separately installed plugin. Shell startup does not sync it. |
| Apollo/Artemis management commands | replace | `dotfiles` is the only management CLI. No dual runtime ownership. |

## Retired behavior

- globally exported GitHub or other access tokens;
- credential prompts during startup;
- credentialed proxy URLs inherited by every child process;
- sourcing machine profiles as arbitrary code;
- recursive plugin discovery during startup;
- copying all of `config/` into the active home;
- tracking active `gh/hosts.yml`, auth databases, SSH keys, tokens, receipts,
  caches, or enterprise host state;
- hard-coded personal checkout paths, Homebrew prefixes, Java homes, identities,
  ticket hosts, or corporate URLs in portable defaults;
- `curl | sh`, ignored installer failures, or automatic dependency installs;
- unconditional command overrides such as `git`, `rmdir`, `branch`, and
  `rebase --no-verify`.

## Configuration ownership

| Layer | May contain | Must not contain |
| --- | --- | --- |
| portable repository | schema, safe defaults, plugin code, static public config, examples | identities, hostnames, credentials, enterprise endpoints |
| tracked personal profile | feature choices and non-secret preferences that are safe to publish | tokens, passwords, private host data |
| tracked enterprise example or separate enterprise repository | key names, capability contracts, redacted examples | usable credentials or private values in this repository |
| machine-local config | paths, identities, host selections, provider references | raw secrets when a credential provider can hold them |
| credential provider | secret values | shell startup behavior or portable policy |

## Acceptance priorities

1. Invalid configuration cannot reach plugin code.
2. Re-sourcing is idempotent and preserves the short-command workflow.
3. A clean home with only Zsh and standard POSIX tools receives a usable core.
4. Explicitly enabled missing features fail; optional features degrade cleanly.
5. Secrets are scoped to one child command and never printed by diagnostics.
6. Personal and enterprise layers plug in without changing portable core files.
