# Pi setup

This setup uses `~/.pi/agent` as the Pi configuration directory.
Dotfiles tracks public Pi resources there.
Pi keeps authentication and session data private.

## Public resources

| Path under `~/.pi/agent` | Purpose |
| --- | --- |
| `AGENTS.md` | Generated engineering baseline B0 |
| `agents/*.md` | Agent definitions |
| `prompts/*.md` | Reusable prompts |
| `pi-lsp.json` | Settings for language servers |

Use `df` to review and commit changes to these files:

```sh
df diff -- .pi/agent
df add .config/agent-engineering/B0.md
df diff --cached
df commit -m "docs: refine Pi instructions"
```

## Kast extension

Install Pi and Kast before this step.
Register the extension in the Pi configuration directory:

```sh
kast connect pi --destination "$HOME/.pi/agent"
kast status --json
```

The status report must contain a `PI` entry under `registrations.value`.
Its `directory` must resolve to `~/.pi/agent`.
Its `destination` must resolve to `~/.pi/agent/extensions/kast.ts`.

Start a fresh Pi session after registration:

```sh
pi
```

Kast owns the installed extension and its registration.
The Git ignore rules exclude `extensions/kast.ts` from the public inventory.
Use Kast commands to manage that file.

`kast status` reports installation and registration state.
A live Pi session must load the extension before it can call Kast tools.

The separate [Ayi repository](https://github.com/amichne/ayi) owns the `ayi` task commands and their installer.

Read the [native engineering guide](https://slopsentral.michne.com/guides/engineering-baseline)
for B0, optional skills, local validators, and native lifecycle limits.
