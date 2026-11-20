# Home guidance

These are the user-scoped instructions for every agent session.
`~/.codex/AGENTS.md` and `~/.claude/CLAUDE.md` link to this file.
Resolve each path below against `$HOME`, not the project.

## Route the task

Read only the row that matches the intended action, before acting.

| Intended action | Read |
| --- | --- |
| Produce or revise original prose | `~/.dotfiles/writing.md` |
| Design, change, or review software | Slopsentral's Software Engineering session context; without it, the [global instructions](https://raw.githubusercontent.com/amichne/slopsentral/refs/heads/main/docs/examples/global/AGENTS.md) |
| Change a tracked home path or a file under `~/.dotfiles/` | The home dotfiles section below |

If a required file is unavailable, name the gap and complete independent
authorized work without claiming compliance.

## Respond

- Lead with the result, decision, or requested information.
- State each point once. Omit filler, narration of routine commands, and a closing recap.
- Report each check as passed, failed, skipped, or not run.

## Personal repository delivery

- Treat repositories under the GitHub account `amichne` as personal. Treat an
  organization repository as personal only when the user says so.
- After an implementation task completes in a personal repository, commit its
  changes, push the task branch, and open or update a pull request. This is
  standing authorization for those three actions.
- For work repositories or unknown ownership, keep publication authorization
  specific to the task. Obey a request for local-only work.
- Merges, deployments, and release publication need separate explicit authorization.

## Home dotfiles

Apply this section only when the request changes a tracked home path or a file
under `~/.dotfiles/`, or adds a path to the bare repository. The current
directory or workspace does not activate it. For a read-only task or a task
outside these paths, stop applying this file after this paragraph; do not
inspect or use this repository workflow.

- Git metadata lives at `~/.dotfiles.git`; the work tree is `$HOME`. Support
  files, guidance, scripts, and tests live under `~/.dotfiles/`.
- Use the `dotfiles` command, or `git --git-dir=$HOME/.dotfiles.git --work-tree=$HOME`.
- Use tracked-only status; `dotfiles status` does. Do not scan `$HOME` for
  untracked files. Examine an untracked path only with a narrow path argument.
- Read `~/.dotfiles/repository.md` and the files the change affects before editing.
- Stage each path explicitly with `dotfiles add <path>`; never stage all of HOME.
- Run `~/.dotfiles/scripts/check.sh` before handoff. Never point a test at live HOME.
