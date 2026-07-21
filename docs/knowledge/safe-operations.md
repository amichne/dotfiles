---
type: Operations Contract
title: Safe operations
description: Previewable home changes and child-scoped credentials and proxies.
resource: file://lib/install.sh
tags: [installation, home, credentials, proxy, safety]
timestamp: 2026-07-21T00:00:00Z
code_sources:
  - path: lib/install.sh
    symbols: [dotfiles_install_plan, dotfiles_install_apply, dotfiles_install_uninstall]
  - path: lib/home.sh
    symbols: [dotfiles_home_command]
  - path: lib/credentials.sh
    symbols: [dotfiles_credential_resolve, dotfiles_credential_exec_github]
  - path: lib/proxy.sh
    symbols: [dotfiles_proxy_authenticated_url, dotfiles_proxy_exec]
  - path: scripts/check.sh
---

# Safe operations

Home-directory changes are explicit operations. `dotfiles install plan` reports
ownership before `apply` writes one marked Zsh block through a same-directory
temporary file. `uninstall` removes only that managed block. Static dotfiles are
a separate chezmoi adapter with `plan`, `apply`, and `status` actions.

## Secret scope

Credential providers resolve a value only for the child command that requests
it. GitHub tokens are assigned to the child environment in
`dotfiles_credential_exec_github`; proxy credentials are encoded and applied
inside `dotfiles_proxy_exec`. The persistent configuration stores provider
names and references, not resolved secret values.

## Verification

`scripts/check.sh` runs disposable-home behavior tests, shell syntax checks,
ShellCheck, whitespace and secret-shaped source scans, production registry
validation, and `git diff --check`.

```sh
./scripts/check.sh
./bin/dotfiles install plan
./bin/dotfiles home plan
```

The two plan commands inspect different ownership boundaries and neither is an
implicit prerequisite for shell startup.

See [migration](../migration.md) and [operations](../operations.md) for the
operator workflows.
