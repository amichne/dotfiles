# Pi setup

This setup uses `~/.pi/agent` as the Pi directory.
Dotfiles tracks public Pi resources there.
Pi keeps authentication and session data private.

## Public resources

| Path under `~/.pi/agent` | Purpose |
| --- | --- |
| `deepen.md` | Instructions for the `/deepen` command |
| `extensions/deepen.ts` | One-call prompt rewrite command |
| `extensions/ask-questions.ts` | Pi adapter for timed questions |
| `lib/questions.ts` | Question parsing, deadlines, and outcomes |
| `questions.json` | Default response duration |
| `extensions/subagent/config.json` | Limits for `pi-subagents` |
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

## Delegate work

Install the reviewed package version:

```sh
pi install npm:pi-subagents@0.79.0
```

Use `/reload` after installation.
The package owns child sessions, fan-out, cancellation, retained results, and later messages.
Direct child launches default to foreground work.
Workflow scripts need `async: false` for foreground work.
The configuration sets four concurrent children per run, eight child launches per run, and 32 launches per parent session.
It limits nested delegation to one level and sets a ten-minute tool deadline.
It permits two active background runs per session and disables schedules.
These package settings are defaults, not an operating-system sandbox.
The package accepts some per-call overrides.

Ask Pi to delegate a bounded task:

```text
Use scout to find the parser entry points without file changes.
Run parallel reviewers for correctness and test coverage.
```

For scripted fan-out, the package uses `runs.all`:

```js
const results = await runs.all([
  { key: "correctness", agent: "reviewer", task: "Review correctness without file changes." },
  { key: "coverage", agent: "reviewer", task: "Review test coverage without file changes." }
]);
return results.map(result => result.output);
```

Use `/subagents-guide workflows` for the complete call format.
Use `/subagents-fleet` to inspect, message, or stop a child.
Keep the returned run ID for a later message or another turn.
Children use `contact_supervisor` for decisions.
The parent asks the user.
Assign one writer per file or a separate worktree per writer.
The local `reviewer` profile exposes only file-read and search tools.
The local `worker` profile declares the package's writer acceptance role.

The [package catalog](https://pi.dev/packages/pi-subagents) lists the delegation package.
The [package reference](https://github.com/nicobailon/pi-subagents/blob/main/docs/configuration.md) describes its settings.

## Ask timed questions

The local `ask_questions` tool accepts one to five independent questions per call.
Pi displays them in order.
Each question gets its own timer when it appears.
Unseen questions do not consume response time.
The default duration is 60 seconds in `questions.json`.
Set `timeoutMs` per question to change that duration.
Durations must be whole milliseconds from 1 through 3600000.

The model can call:

```json
{
  "questions": [
    {
      "id": "scope",
      "prompt": "Which scope fits the task?",
      "options": ["Current module", "Whole repository"],
      "timeoutMs": 60000,
      "onTimeout": "insufficient_evidence"
    },
    {
      "id": "format",
      "prompt": "Which report format do you prefer?",
      "options": ["Markdown", "JSON"],
      "timeoutMs": 30000,
      "onTimeout": "model_judgment"
    }
  ]
}
```

Options are optional.
Each question accepts a freeform response.
Selection and freeform input share one deadline for that question.
The question tool owns the timer and dismisses the dialog through its abort signal.
The dialog shows the response window when it opens.

An answer returns `answered` with the submitted value.
A timeout returns `timed_out` with the question's policy.
The default policy is `insufficient_evidence`.
It tells the model to stop dependent work when the missing answer blocks a safe choice.
The `model_judgment` policy lets the model consider a reversible choice within existing authority.
After timeout, the model must examine the evidence again.
It can state a provisional choice with its evidence or veto the guess as insufficient evidence.
Neither policy selects an answer for the user.
Silence never supplies consent for an external action.

Cancellation or interruption stops the batch and preserves earlier answers.
Later questions return `not_asked`.
A missing UI returns `ui_unavailable`.
Neither cancellation nor an error permits a guess.
Late responses cannot answer another question or a later round.
Ask dependent questions in another call after the earlier answers return.
Each result carries the tool-call ID and question IDs.

The tool enforces timers, outcome identity, and cancellation.
The instructions guide model judgment and vetoes.
They do not enforce the model's later tool choices.

## Package selection

The source review compared the published packages on October 17, 2026.

| Package | Useful behavior | Gap for this setup |
| --- | --- | --- |
| [`pi-subagents` 0.79.0](https://pi.dev/packages/pi-subagents) | Fan-out, retained children, and later messages | Selected for delegation |
| [`pi-ask-user` 0.16.0](https://pi.dev/packages/pi-ask-user) | Rich question batches | One deadline for the whole batch |
| [`@pi9/ask` 0.4.2](https://pi.dev/packages/@pi9/ask) | Per-call timeout, answer revisions | One question per call and one configured duration |
| [`pi-ask-question`](https://github.com/fitchmultz/pi-ask-question) | Question batches and an AFK result | One five-minute deadline for the whole call |

The local tool adds separate durations and explicit timeout policies without another delegation runtime.

## Kast extension

Install Pi and Kast before this step.
Register the extension in that directory:

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

`kast status` reports where Kast is set up.
A live Pi session must load the extension before it can call Kast tools.

The separate [Ayi repository](https://github.com/amichne/ayi) owns the `ayi` task commands and their installer.

Read the [native engineering guide](engineering-baseline.md)
for B0, optional skills, local validators, and native lifecycle limits.
The installer preserves existing `APPEND_SYSTEM.md` and feature extensions.
Its installed `AGENTS.md` is private and keeps text outside the managed B0 block.
