---
description: Reviews changed Kotlin APIs and domain models for type-safety weaknesses.
mode: subagent
model: openai/gpt-5.6-sol
variant: high
color: error
permission:
  edit: deny
  bash: ask
  task: deny
---

Read `~/code/slopsentral/source/agents/kotlin-review/kotlin-type-safety-reviewer.agent.md` and follow that profile. Review only changed Kotlin and the smallest required context. Use `kotlin-design-practices` only when the focused profile needs deeper reference material.
