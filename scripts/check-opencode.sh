#!/usr/bin/env bash

set -euo pipefail

SLOPSENTRAL_ROOT="${SLOPSENTRAL_ROOT:-$HOME/code/slopsentral}"

command -v opencode >/dev/null 2>&1 || {
    printf 'check-opencode: required command missing: opencode\n' >&2
    exit 69
}

while IFS= read -r skill_name; do
    [ -f "$SLOPSENTRAL_ROOT/source/skills/$skill_name/SKILL.md" ] || {
        printf 'check-opencode: missing Slopsentral skill: %s\n' "$skill_name" >&2
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
OPENCODE_PURE=1 opencode debug skill >/dev/null
OPENCODE_PURE=1 opencode debug agent kotlin-review-captain >/dev/null

printf 'OpenCode checks passed.\n'
