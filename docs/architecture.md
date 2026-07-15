# Target architecture

## Design

The project is a small validated shell runtime, not a package manager and not a
credential store. Static dotfile deployment is an adapter boundary; the shell
must remain usable if chezmoi, Homebrew, SDKMAN, Atuin, or an enterprise network
is unavailable.

```text
schema defaults
    + selected tracked profiles
    + machine-local data file
    + declared process overrides
                |
                v
      validated resolved values
                |
       +--------+---------+
       |                  |
  dependency doctor   plugin manifest
                          |
               trusted physical files
                          |
             idempotent Zsh runtime
```

## Repository boundaries

```text
bin/dotfiles                 management CLI
config/schema.tsv            typed public configuration authority
config/plugins.tsv           trusted plugin registry
config/dependencies.tsv      capability and install-hint registry
profiles/*.conf              tracked, data-only compositions
lib/*.sh                     portable CLI implementation
shell/zsh/entrypoint.zsh     minimal Zsh boundary
plugins/core                 dependency-free UX
plugins/integrations         optional public tools
plugins/enterprise           generic enterprise seams, no private values
home                         optional dotfile-manager source
tests                        disposable-home behavior tests
docs                         contracts, configuration, and migration guidance
```

## Typed configuration

Each schema row declares a key, type, default, runtime variable, optional
process override variable, and description. Supported types are deliberately
small:

- `bool`: `0` or `1`;
- `toggle`: `on`, `off`, or `auto`;
- `enum:<values>`: one declared literal;
- `uint`: a non-negative integer;
- `command`: one executable name, not shell text;
- `path` and `path-list`: absolute after expansion of an allowlisted placeholder;
- `string`, `csv`, and `url`: single-line data with type-specific validation.

Profiles use `key=value`. They cannot contain `export`, command substitution,
quotes with shell meaning, or arbitrary interpolation. Only documented
placeholders such as `${HOME}`, `${XDG_CONFIG_HOME}`, and `${DOTFILES_ROOT}` are
expanded by the parser.

Resolved values cross into Zsh as name/value records. The runtime does not
`eval` profile content or source generated configuration code.

## Profiles and enterprise composition

`DOTFILES_PROFILES` selects tracked profiles in order, for example
`personal,work`. `DOTFILES_CONFIG_FILE` may point to one machine-local data
file, normally `${XDG_CONFIG_HOME}/dotfiles/config.conf`. A separate enterprise
repository can supply an additional profile and plugin manifest through a
trusted root without forking portable core.

Examples of enterprise-owned values include proxy endpoints, certificate
bundle paths, package mirrors, Git/Jira host policy, ticket formats, and logical
credential references. Raw secret values remain in an OS keychain, `gh`,
1Password, `pass`, or another credential-provider adapter.

## Dependencies

The runtime never installs software. `dotfiles doctor` evaluates declared
capabilities and prints platform-aware install hints. `dotfiles bootstrap`
produces a plan; an explicit adapter may apply it later. This keeps proxy,
mirror, device-management, and enterprise package-policy decisions outside
startup.

## Secret and proxy scope

Credential lookup is command-scoped:

```sh
dotfiles credential exec github -- gh api user
dotfiles proxy exec -- curl https://example.test
```

The resolver obtains the value, places it only in the child process
environment, and never prints it. Shell startup may apply an unauthenticated
proxy only when configured to do so; authenticated proxy material is always
command-scoped.

Active `gh/hosts.yml`, SSH private keys, auth databases, and token files are not
managed by this repository. Portable config should use include files and
provider references so private host state can be supplied locally or by an
enterprise overlay.

## Deployment adapter

The core installer owns only its marked Zsh block. Static application config
can be rendered by an optional chezmoi source under `home/`, but adoption is a
separate preview/apply decision. This avoids repeating the historical mistake
of coupling shell availability to a dotfile manager or copying an entire config
tree over active machine state.
