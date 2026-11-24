# Home guidance

These are the user-scoped instructions for every agent session.
`~/.codex/AGENTS.md` and `~/.claude/CLAUDE.md` link to this file.
Paths that start with `~/` refer to the user's home directory.

## Route the task

Read only the row that matches the intended action, before acting.

| Intended action | Read |
| --- | --- |
| Produce or revise original prose | `~/.dotfiles/writing.md` |
| Design, change, or review software | Slopsentral's Software Engineering session context; without it, the [global instructions](https://raw.githubusercontent.com/amichne/slopsentral/refs/heads/main/docs/examples/global/AGENTS.md) |
| Change the dotfiles checkout | `.dotfiles/repository.md` in that checkout |

If a required file is unavailable, name the gap and complete independent
authorized work without claiming compliance.

## Respond

- Lead with the result, decision, or requested information.
- State each point once. Omit filler, narration of routine commands, and a closing recap.
- Report each check as passed, failed, skipped, or not run.

## Work

- Change tracked files with the host's file-edit tool, not shell or Python
  rewrites.
- End a turn on pending CI, a build, or another process only when a background
  task or monitor will resume you. Otherwise keep checking, or state what is
  pending and that you are stopping.

## Personal repository delivery

- Treat repositories under the GitHub account `amichne` as personal. Treat an
  organization repository as personal only when the user says so.
- After an implementation task completes in a personal repository, commit its
  changes, push the task branch, and open or update a pull request. This is
  standing authorization for those three actions.
- For work repositories or unknown ownership, keep publication authorization
  specific to the task. Obey a request for local-only work.
- Merges, deployments, and release publication need separate explicit authorization.
