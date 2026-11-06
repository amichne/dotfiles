# OpenCode Slopsentral Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deploy a credential-free OpenCode configuration from dotfiles with a Claude-like Dracula interface, history-derived workstyle guidance, and role-based subagents backed by curated Slopsentral source skills.

**Architecture:** The existing chezmoi home adapter owns static OpenCode files under `home/dot_config/opencode`. OpenCode loads selected canonical Slopsentral skill directories directly from `~/code/slopsentral/source/skills`; thin local agent wrappers preserve OpenCode permissions and delegate domain behavior to source-owned profiles and skills.

**Tech Stack:** Bash behavior tests, chezmoi, OpenCode 1.18.10 JSON configuration, Markdown agent definitions, JSON Schema-backed OpenCode debug commands.

### Task 1: Prove The Static Deployment Contract

**Files:**
- Modify: `tests/home_adapter_test.sh:42-65`

**Step 1: Write the failing test**

Extend the managed-target assertion with:

```bash
if [ -f "$HOME/.config/opencode/opencode.json" ] \
    && [ -f "$HOME/.config/opencode/tui.json" ] \
    && [ -f "$HOME/.config/opencode/themes/claude-dracula.json" ] \
    && [ -f "$HOME/.config/opencode/rules/workstyle.md" ] \
    && [ -f "$HOME/.config/opencode/agents/kotlin-review-captain.md" ] \
    && [ -f "$HOME/.config/opencode/agents/kotlin-type-safety-reviewer.md" ] \
    && [ -f "$HOME/.config/opencode/agents/kotlin-boundary-contract-reviewer.md" ] \
    && [ -f "$HOME/.config/opencode/agents/kotlin-package-cohesion-reviewer.md" ] \
    && [ -f "$HOME/.config/opencode/agents/delivery-engineer.md" ] \
    && [ -f "$HOME/.config/opencode/agents/agent-platform-author.md" ] \
    && [ -f "$HOME/.config/opencode/agents/code-knowledge-engineer.md" ] \
    && [ -f "$HOME/.config/opencode/agents/intellij-plugin-engineer.md" ]; then
    test_pass "home apply writes the OpenCode configuration set"
else
    test_fail "home apply writes the OpenCode configuration set" "one or more OpenCode targets are missing"
fi
```

Extend the excluded-state assertion with:

```bash
&& [ ! -e "$HOME/.config/opencode/history.jsonl" ] \
&& [ ! -e "$HOME/.config/opencode/auth.json" ]
```

Add a secret and composition assertion:

```bash
if grep -qF '"subagent_depth": 2' "$HOME/.config/opencode/opencode.json" \
    && grep -qF '"model": "openai/gpt-5.6-sol"' "$HOME/.config/opencode/opencode.json" \
    && grep -qF '~/code/slopsentral/source/skills/intellij-plugin-delivery' "$HOME/.config/opencode/opencode.json" \
    && ! grep -Eq 'ctx7sk-|sk-[A-Za-z0-9_-]{20,}' "$HOME/.config/opencode/opencode.json"; then
    test_pass "managed OpenCode config is curated and credential-free"
else
    test_fail "managed OpenCode config is curated and credential-free" "composition or credential boundary is incorrect"
fi
```

**Step 2: Run the test to verify it fails**

Run: `bash tests/home_adapter_test.sh`

Expected: FAIL with `one or more OpenCode targets are missing`.

**Step 3: Inspect the diff checkpoint**

Run: `git diff -- tests/home_adapter_test.sh`

Expected: only the new OpenCode deployment assertions appear.

### Task 2: Add The Core OpenCode Configuration And Workstyle

**Files:**
- Create: `home/dot_config/opencode/opencode.json`
- Create: `home/dot_config/opencode/rules/workstyle.md`

**Step 1: Add the schema-valid core configuration**

Create `opencode.json` with these top-level contracts:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "openai/gpt-5.6-sol",
  "small_model": "openai/gpt-5.4-mini",
  "default_agent": "build",
  "subagent_depth": 2,
  "share": "manual",
  "autoupdate": "notify",
  "snapshot": true,
  "instructions": ["~/.config/opencode/rules/*.md"],
  "skills": {
    "paths": [
      "~/code/slopsentral/source/skills/repository-onboarding",
      "~/code/slopsentral/source/skills/semantic-ratchet",
      "~/code/slopsentral/source/skills/tdd",
      "~/code/slopsentral/source/skills/kotlin-agentic-correctness",
      "~/code/slopsentral/source/skills/kotlin-review",
      "~/code/slopsentral/source/skills/kotlin-design-practices",
      "~/code/slopsentral/source/skills/negative-capability-proof",
      "~/code/slopsentral/source/skills/kotlin-gradle-validation",
      "~/code/slopsentral/source/skills/github-ci-operations",
      "~/code/slopsentral/source/skills/define-goal",
      "~/code/slopsentral/source/skills/pull-request-lifecycle",
      "~/code/slopsentral/source/skills/shell-script-safety",
      "~/code/slopsentral/source/skills/git-change-flow",
      "~/code/slopsentral/source/skills/skill-primitive-authoring",
      "~/code/slopsentral/source/skills/local-repository-navigation",
      "~/code/slopsentral/source/skills/primitive-quality-audit",
      "~/code/slopsentral/source/skills/plugin-composition-authoring",
      "~/code/slopsentral/source/skills/primitive-routing-evaluation",
      "~/code/slopsentral/source/skills/source-graph-consolidation",
      "~/code/slopsentral/source/skills/repo-instruction-topology",
      "~/code/slopsentral/source/skills/agent-profile-authoring",
      "~/code/slopsentral/source/skills/hook-primitive-authoring",
      "~/code/slopsentral/source/skills/reference-doc-workflow",
      "~/code/slopsentral/source/skills/site-docs-authoring",
      "~/code/slopsentral/source/skills/code-knowledge-base",
      "~/code/slopsentral/source/skills/repository-signature-indexing",
      "~/code/slopsentral/source/skills/controlled-technical-writing",
      "~/code/slopsentral/source/skills/pkl-pattern-catalogs",
      "~/code/slopsentral/source/skills/pkl-tooling-setup",
      "~/code/slopsentral/source/skills/pkl-specification",
      "~/code/slopsentral/source/skills/pkl-engineering",
      "~/code/slopsentral/source/skills/intellij-plugin-delivery"
    ]
  },
  "permission": {
    "read": "allow",
    "edit": "allow",
    "glob": "allow",
    "grep": "allow",
    "list": "allow",
    "bash": "allow",
    "task": "allow",
    "external_directory": {
      "*": "ask",
      "~/code/**": "allow"
    },
    "todowrite": "allow",
    "question": "allow",
    "webfetch": "allow",
    "websearch": "allow",
    "lsp": "allow",
    "skill": "allow"
  },
  "agent": {
    "build": {"color": "accent", "variant": "xhigh"},
    "plan": {"color": "warning", "variant": "high"},
    "general": {"color": "success", "variant": "high"},
    "explore": {"color": "info"},
    "scout": {"color": "secondary"}
  },
  "tool_output": {"max_lines": 500, "max_bytes": 51200},
  "compaction": {"auto": true, "prune": true, "tail_turns": 15},
  "mcp": {
    "context7": {
      "type": "remote",
      "url": "https://mcp.context7.com/mcp",
      "enabled": false,
      "headers": {"CONTEXT7_API_KEY": "{env:CONTEXT7_API_KEY}"}
    }
  },
  "lsp": {
    "kotlin-lsp": {"command": ["kotlin-lsp"], "extensions": [".kt", ".kts"]}
  }
}
```

Before final verification, merge the existing credential-free OpenAI provider
options and model overrides into this object unchanged. Do not copy any literal
MCP credential from the live configuration.

**Step 2: Add the concise workstyle rule**

Create `rules/workstyle.md`:

```markdown
# Workstyle

- Inspect the repository, its instructions, and the current diff before changing behavior.
- Prefer the smallest correct change. Do not add compatibility, abstraction, or cleanup without a concrete requirement.
- For implementation, establish the baseline, prove RED, implement to GREEN, and run the repository's verification gate.
- Treat compiler, schema, parser, and validation failures as guidance. Strengthen types and boundaries instead of bypassing them.
- Preserve unrelated work. Never revert or rewrite changes outside the requested scope.
- Delegate independent investigation and specialist review when it shortens the critical path.
- Carry requested work through implementation and verification. Handle PR and CI delivery only when the task includes delivery.
- Communicate directly: findings and outcomes first, explicit uncertainty, no filler.
```

**Step 3: Run the focused test**

Run: `bash tests/home_adapter_test.sh`

Expected: the test still fails only because theme and agent targets are absent.

### Task 3: Add Role-Based Specialist Agents

**Files:**
- Create: `home/dot_config/opencode/agents/kotlin-review-captain.md`
- Create: `home/dot_config/opencode/agents/kotlin-type-safety-reviewer.md`
- Create: `home/dot_config/opencode/agents/kotlin-boundary-contract-reviewer.md`
- Create: `home/dot_config/opencode/agents/kotlin-package-cohesion-reviewer.md`
- Create: `home/dot_config/opencode/agents/delivery-engineer.md`
- Create: `home/dot_config/opencode/agents/agent-platform-author.md`
- Create: `home/dot_config/opencode/agents/code-knowledge-engineer.md`
- Create: `home/dot_config/opencode/agents/intellij-plugin-engineer.md`

**Step 1: Add the coordinating Kotlin reviewer**

Use this frontmatter and routing body:

```markdown
---
description: Coordinates focused Kotlin review and returns one prioritized finding list.
mode: subagent
model: openai/gpt-5.6-sol
variant: high
color: warning
permission:
  edit: deny
  bash: ask
  task:
    "*": deny
    "kotlin-type-safety-reviewer": allow
    "kotlin-boundary-contract-reviewer": allow
    "kotlin-package-cohesion-reviewer": allow
---

Read `~/code/slopsentral/source/agents/kotlin-review/kotlin-review-captain.agent.md` and follow that profile. Use the `kotlin-review` skill. Delegate only the review axes triggered by the changed Kotlin code, then deduplicate findings.
```

**Step 2: Add the three read-only Kotlin reviewers**

Each file uses `mode: subagent`, `model: openai/gpt-5.6-sol`, `variant: high`,
`edit: deny`, `bash: ask`, and `task: deny`. Its body reads the matching profile
under `~/code/slopsentral/source/agents/kotlin-review/` and invokes
`kotlin-design-practices` only when deeper reference material is required.

**Step 3: Add four thin implementation specialists**

Use `mode: subagent`, `variant: high`, `edit: allow`, `bash: allow`, and
`task: deny` for:

- `delivery-engineer`: route through `define-goal`, `git-change-flow`,
  `pull-request-lifecycle`, and `github-ci-operations`;
- `agent-platform-author`: route through the source-owned primitive authoring,
  composition, routing-evaluation, and quality-audit skills;
- `code-knowledge-engineer`: route through `code-knowledge-base`,
  `repository-signature-indexing`, and documentation workflow skills;
- `intellij-plugin-engineer`: route through `intellij-plugin-delivery`, Kotlin
  correctness, Gradle validation, and delivery skills.

Keep each body under 120 words and do not duplicate skill procedures.

**Step 4: Run the focused test**

Run: `bash tests/home_adapter_test.sh`

Expected: the test still fails only because `tui.json` or the theme is absent.

### Task 4: Add The Claude-Dracula Interface

**Files:**
- Create: `home/dot_config/opencode/tui.json`
- Create: `home/dot_config/opencode/themes/claude-dracula.json`

**Step 1: Add TUI navigation**

Create:

```json
{
  "$schema": "https://opencode.ai/tui.json",
  "theme": "claude-dracula",
  "leader_timeout": 2000,
  "keybinds": {
    "leader": "ctrl+x",
    "command_list": "ctrl+p",
    "agent_list": "<leader>a",
    "agent_cycle": "tab",
    "agent_cycle_reverse": "shift+tab",
    "session_new": "<leader>n",
    "session_list": "<leader>l",
    "session_compact": "<leader>c",
    "session_child_first": "<leader>down",
    "session_child_cycle": "right",
    "session_child_cycle_reverse": "left",
    "session_parent": "up",
    "tool_details": "<leader>d",
    "display_thinking": "<leader>r"
  }
}
```

**Step 2: Add the custom theme**

Define the Dracula palette in `defs`: background `#282A36`, panel `#21222C`,
element `#343746`, foreground `#F8F8F2`, muted `#6272A4`, pink `#FF79C6`,
purple `#BD93F9`, cyan `#8BE9FD`, green `#50FA7B`, orange `#FFB86C`, yellow
`#F1FA8C`, and red `#FF5555`. Map every required theme key and all diff,
Markdown, and syntax keys from `https://opencode.ai/theme.json`. Use `none` for
the terminal background only if a direct smoke test confirms readable contrast;
otherwise use `#282A36`.

**Step 3: Run the focused test to verify GREEN**

Run: `bash tests/home_adapter_test.sh`

Expected: `Passed: 13  Failed: 0` or the updated equivalent.

### Task 5: Add Live OpenCode Verification

**Files:**
- Create: `scripts/check-opencode.sh`
- Modify: `docs/operations.md:30-49`
- Modify: `README.md:31-44`

**Step 1: Write the live verifier**

The script must:

```bash
#!/usr/bin/env bash
set -euo pipefail

CHECK_OPENCODE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SLOPSENTRAL_ROOT="${SLOPSENTRAL_ROOT:-$HOME/code/slopsentral}"

command -v opencode >/dev/null 2>&1 || {
    printf 'check-opencode: required command missing: opencode\n' >&2
    exit 69
}

while IFS= read -r skill_path; do
    [ -f "$SLOPSENTRAL_ROOT/source/skills/$skill_path/SKILL.md" ] || {
        printf 'check-opencode: missing Slopsentral skill: %s\n' "$skill_path" >&2
        exit 66
    }
done <<'SKILLS'
repository-onboarding
semantic-ratchet
tdd
kotlin-agentic-correctness
kotlin-review
kotlin-design-practices
negative-capability-proof
kotlin-gradle-validation
github-ci-operations
define-goal
pull-request-lifecycle
shell-script-safety
git-change-flow
skill-primitive-authoring
local-repository-navigation
primitive-quality-audit
plugin-composition-authoring
primitive-routing-evaluation
source-graph-consolidation
repo-instruction-topology
agent-profile-authoring
hook-primitive-authoring
reference-doc-workflow
site-docs-authoring
code-knowledge-base
repository-signature-indexing
controlled-technical-writing
pkl-pattern-catalogs
pkl-tooling-setup
pkl-specification
pkl-engineering
intellij-plugin-delivery
SKILLS

OPENCODE_PURE=1 opencode debug config >/dev/null
OPENCODE_PURE=1 opencode debug skill | grep -q '"name": "kotlin-review"'
OPENCODE_PURE=1 opencode debug agent kotlin-review-captain >/dev/null
printf 'OpenCode checks passed.\n'
```

Use a shared checked-in skill list or derive the list from the config without
duplicating it if a dependency-free parser is available. Do not use `eval` or
source JSON as shell.

**Step 2: Document preview, apply, and restart**

Add the operator flow:

```sh
./scripts/check.sh
./bin/dotfiles home plan
./bin/dotfiles home apply
./scripts/check-opencode.sh
```

State that `~/code/slopsentral` must exist, Context7 credentials stay local,
the obsolete `~/.config/opencode/opencode.jsonc` is removed only after
validation, and OpenCode must be quit and restarted.

**Step 3: Verify script quality**

Run: `bash -n scripts/check-opencode.sh`

Expected: exit 0.

Run: `shellcheck -S warning -x -s bash scripts/check-opencode.sh`

Expected: exit 0 with no findings.

### Task 6: Run Repository And Live Proof

**Files:**
- Verify all files changed in Tasks 1-5.

**Step 1: Run the full repository gate**

Run: `./scripts/check.sh`

Expected: all behavior tests and static gates pass.

**Step 2: Preview the real deployment**

Run: `./bin/dotfiles home plan`

Expected: a diff limited to the tracked OpenCode files and any already-known
dotfiles drift. Inspect rather than applying if unrelated live files would be
changed.

**Step 3: Apply the managed home files**

Run: `./bin/dotfiles home apply`

Expected: exit 0.

**Step 4: Validate the live OpenCode setup**

Run: `./scripts/check-opencode.sh`

Expected: `OpenCode checks passed.`

Run: `./bin/dotfiles home status`

Expected: no output and exit 0.

**Step 5: Remove ambiguous legacy config only after validation**

If `~/.config/opencode/opencode.jsonc` still exists, compare its provider and
LSP settings with the resolved output from `opencode debug config`. Remove it
only after every required field is present in the tracked `opencode.json`, then
rerun `./scripts/check-opencode.sh`.

**Step 6: Inspect final scope**

Run: `git status --short && git diff --check && git diff --stat`

Expected: only the OpenCode setup, tests, and its design/operation docs changed;
no credentials, Codex history, generated Slopsentral payloads, or unrelated
profile files appear.

**Step 7: Restart smoke test**

Quit and restart OpenCode. Confirm `claude-dracula` loads, `@` autocomplete
shows the specialist agents, `opencode debug skill` shows the curated skills,
and the parent/child session navigation works after one delegated Explore task.
