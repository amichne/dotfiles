# Workstyle

- Inspect the repository, its instructions, and the current diff before changing behavior.
- Prefer the smallest correct change. Do not add compatibility, abstraction, or cleanup without a concrete requirement.
- For implementation, establish the baseline, prove RED, implement to GREEN, and run the repository's verification gate.
- Treat compiler, schema, parser, and validation failures as guidance. Strengthen types and boundaries instead of bypassing them.
- Preserve unrelated work. Never revert or rewrite changes outside the requested scope.
- Delegate independent investigation and specialist review when it shortens the critical path.
- Carry requested work through implementation and verification. Handle PR and CI delivery only when the task includes delivery.
- Communicate directly: findings and outcomes first, explicit uncertainty, no filler.
