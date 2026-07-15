# Configuration guide

## Resolution order

Effective values resolve from lowest to highest precedence:

1. typed defaults in `config/schema.tsv`;
2. persisted checked-in profiles, left to right;
3. external data-only profile files from `DOTFILES_PROFILE_FILES`, left to
   right;
4. the machine-local file at
   `${XDG_CONFIG_HOME:-$HOME/.config}/dotfiles/config.conf`;
5. the per-key process override named by the schema.

`dotfiles config list` shows the effective value, owning layer, and
description. `secret-ref` values are rendered as `<configured>` or `<unset>`.
Internal runtime export receives the real reference, not the secret value.

## Profile selection

The default profile is `portable`. Persist the current-machine behavior with:

```sh
dotfiles profile set personal
dotfiles profile get
```

The selection is a 0600 data file at
`~/.config/dotfiles/profiles`. A process override is useful for a one-off clean
shell:

```sh
DOTFILES_PROFILES=portable zsh -f
```

Multiple checked-in profiles are comma-separated and compose left to right.
External enterprise profile files use a colon-separated
`DOTFILES_PROFILE_FILES` value. They are still parsed against this repository's
schema; an enterprise layer cannot invent an unvalidated key.

## Data-file grammar

```text
# comments and blank lines are allowed
feature.zoxide=auto
git.commit-stage=tracked
path.append=${HOME}/.local/bin:${HOME}/enterprise/bin
```

Rules:

- one `key=value` per line;
- duplicate keys in one file fail;
- unknown keys fail;
- shell syntax, command substitution, `export`, and arbitrary interpolation are
  not accepted;
- only `${HOME}`, `${XDG_CONFIG_HOME}`, and `${DOTFILES_ROOT}` are expanded;
- paths must be absolute after expansion;
- URL values must be unauthenticated HTTP(S) URLs.

## Feature states

- `on`: the plugin is required; a missing dependency fails startup and doctor.
- `auto`: load when the dependency is available, otherwise report and skip.
- `off`: do not probe or load the plugin.

Portable Git and search helpers default to `on`. Atuin, zoxide, GitHub CLI,
Starship, and SDKMAN default to `auto`. Warp and Jira default to `off`.
SDKMAN initialization is lazy: the integration is registered at startup and is
sourced only on first `sdk`, Java, Kotlin, Gradle, or Maven command.

## Important knobs

| Area | Keys |
| --- | --- |
| shell | `shell.editor`, `shell.locale`, `shell.history-file`, `shell.history-size`, `shell.save-history` |
| paths | `path.prepend`, `path.append` |
| features | every `feature.*` row in the schema |
| Git | `git.remote`, `git.default-branch`, `git.branch-prefix`, `git.commit-stage`, `git.ticket-regex`, `git.enforce-ticket-remote` |
| search | `search.command=auto|rg|grep` |
| proxy | `proxy.mode`, `proxy.scope`, `proxy.url`, `proxy.no-proxy`, `proxy.username` |
| credentials | `credential.github-provider`, provider reference keys, and proxy provider/reference keys |
| enterprise | `enterprise.ca-bundle`, `plugins.external-roots` |
| tool homes | `tools.codex-home`, `tools.sdkman-dir`, `tools.java-home` |

The schema is the exhaustive, executable authority:

```sh
dotfiles config list
```

## Git identity and hosts

The optional home adapter installs a portable `.gitconfig` that includes
`~/.config/git/local.ini`. Create that local file yourself or through enterprise
device management:

```ini
[user]
    name = Your Name
    email = you@example.test
[credential]
    helper = osxkeychain
```

Choose the credential helper appropriate to the operating system and company
policy. Git identity is deliberately not in this repository.

Run `gh auth login` for GitHub hosts. Active `~/.config/gh/hosts.yml` remains
owned by GitHub CLI. Keep SSH private keys and active SSH host configuration out
of this repository; use `Include` files or enterprise-managed snippets when
host policy must be composed.

## Credentials and proxy

GitHub credentials are child-scoped:

```sh
dotfiles credential exec github -- gh api user
# In Zsh after startup:
with-github-token gh api user
```

Supported providers are `gh`, `env`, macOS `security`, `op`, and Linux `pass`.
Machine config stores only the provider and logical reference. A raw value is
never printed by status or doctor.

Proxy modes are `inherit`, `off`, and `explicit`. Authenticated use is always
command-scoped:

```ini
proxy.mode=explicit
proxy.url=https://proxy.example.test:8443
proxy.username=enterprise-user
proxy.credential-provider=op
proxy.credential-reference=op://Vault/Proxy/password
proxy.no-proxy=localhost,127.0.0.1,.internal.example.test
enterprise.ca-bundle=/absolute/path/to/enterprise-ca.pem
```

Then run:

```sh
with-proxy curl https://service.example.test
```

The credential is percent-encoded into proxy variables only for that child.
The CA path is verified before execution and scoped to common TLS variables for
Git, curl, Python requests, Node, and OpenSSL consumers.

## External enterprise plugins

An external trusted root is an absolute, non-symlink directory containing a
required `plugins.tsv` and optional `dependencies.tsv`:

```ini
plugins.external-roots=/opt/company/dotfiles:/Users/me/company-shell
```

`plugins.tsv` rows use:

```text
id<TAB>relative-path<TAB>feature-key-or--<TAB>zsh<TAB>dependency-ids-or--<TAB>description
```

`dependencies.tsv` rows use:

```text
id<TAB>command|file|directory<TAB>probe<TAB>platforms<TAB>install hint
```

IDs must be unique across portable and every external root. Plugin files and
manifests must be regular non-symlink files whose physical paths remain inside
the declared root. This lets an enterprise repository extend behavior without
forking or copying the portable core.
