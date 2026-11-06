# OpenCode Slopsentral Setup

## Purpose

Provide a global OpenCode setup that follows established Codex work patterns,
offers Claude Code-like interaction and subagent flow, and consumes the
canonical skills composed by the published Slopsentral plugins without copying
their content.

The setup belongs in this dotfiles repository and deploys through the existing
previewable, idempotent home adapter.

## Architecture

Use a declarative live adapter. Slopsentral plugin manifests define the curated
composition while OpenCode reads the selected canonical skill directories from
`~/code/slopsentral/source/skills/`. Dotfiles owns only OpenCode-native
configuration, agent wrappers, workstyle guidance, and visual settings.

The history-curated default plugin set is engineering baseline, Kotlin
engineering, Git and CI operations, agent platform authoring, code knowledge,
controlled technical writing, Pkl engineering, and IntelliJ plugin engineering.
Other published Slopsentral capabilities remain available for later opt-in.

## Tracked Components

Store the managed source under `home/dot_config/opencode/` so the existing
chezmoi adapter deploys it to `~/.config/opencode/`.

The tracked boundary contains:

- `opencode.json` for credential-free runtime settings, Slopsentral skill
  paths, agent defaults, permissions, compaction, and subagent depth;
- `tui.json` for interaction and child-session navigation;
- `themes/claude-dracula.json` for Claude-like hierarchy using the established
  Dracula palette;
- `agents/*.md` for thin specialist definitions with role-specific authority;
- `rules/workstyle.md` for stable operating preferences derived from local
  Codex history.

No Slopsentral skill body, Codex history record, credential, cache, session, or
generated runtime state is copied into the repository.

## Runtime Flow

OpenCode loads the tracked workstyle rule and advertises skills from the live
Slopsentral source tree. Build and Plan remain the primary agents. General,
Explore, and Scout retain their native roles. Thin specialist agents route
Kotlin review, delivery, platform authoring, code-knowledge, and IntelliJ work
to the corresponding Slopsentral source profiles and skills.

Explore, Scout, and review agents are read-only. General and implementation
specialists may edit files and execute commands. Primary agents may delegate to
appropriate specialists. Subagent nesting is limited to depth two.

## Workstyle Profile

The workstyle rule captures stable patterns observed in Codex configuration and
history without loading raw history into prompts: inspect before changing,
prefer the smallest correct change, use red and green proof, preserve unrelated
work, treat types and schemas as executable boundaries, delegate independent
investigation, continue through verification, and communicate directly.

Repository-specific instructions and invoked skills remain authoritative for
narrower work.

## Visual Design

The interface retains Dracula's dark surface, bright foreground, pink accent,
green additions, and red removals. Agent colors and restrained panel contrast
create a Claude Code-like hierarchy between conversation, tool activity,
planning, and delegated work. OpenCode's native session-child navigation keeps
the result compatible with future OpenCode releases.

## Migration And Proof

Consolidate the current global `opencode.json` and `opencode.jsonc` into one
tracked, credential-free `opencode.json`. Preserve provider and model overrides.
Keep Context7 configured through environment interpolation. Remove the obsolete
live `opencode.jsonc` only after the consolidated configuration validates.

Tests use a disposable home and assert that all managed targets deploy without
credentials or history. Live verification uses `opencode debug config`,
`opencode debug skill`, and `opencode debug agent`, followed by a restart smoke
test. Missing Slopsentral source paths are a named live-verification failure.
