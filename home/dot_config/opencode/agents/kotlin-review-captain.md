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
