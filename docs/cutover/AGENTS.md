# Consolidation records

The source record identifies the exact Config change and its compressed patch.
Keep that archive as historical source. Do not apply it to the active dotfiles tree.
Current decisions belong in this directory's Markdown pages.
Git mechanism proofs belong in tests/upstream-plan.
Cutover acceptance cases belong in cutover/test_cutover.py.
Do not copy installed credentials, runtime caches, or private harness state into these records.
