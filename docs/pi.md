# Pi setup

This setup uses `~/.pi/agent` as the Pi configuration directory.
Dotfiles tracks public Pi resources there.
Pi keeps authentication and session data private.

## Public resources

| Path under `~/.pi/agent` | Purpose |
| --- | --- |
| `APPEND_SYSTEM.md` | Instructions for Pi sessions |
| `deepen.md` | Instructions for the `/deepen` command |
| `extensions/deepen.ts` | One-call prompt rewrite command |
| `agents/*.md` | Agent definitions |
| `prompts/*.md` | Reusable prompts |
| `pi-lsp.json` | Settings for language servers |

Use `df` to review and commit changes to these files:

```sh
df diff -- .pi/agent
df add .pi/agent/APPEND_SYSTEM.md
df diff --cached
df commit -m "docs: refine Pi instructions"
```

## Rewrite a prompt

Use `/deepen` with the original task:

```text
/deepen Add a read-only report of unused CSS selectors.
```

Pi sends the supplied text and `deepen.md` in one model completion.
The command uses Pi's selected model with high reasoning.
Sign in to the selected provider through Pi before use.
The request excludes the chat history and tools.

The response gives four short assessments, then the rewritten prompt.
Pi displays the result and waits for your next message.
Each request has a two-minute deadline.
A session change or shutdown cancels a pending rewrite.
Incomplete responses produce an error.

After a change to the extension, use `/reload` in Pi.

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
