# Repository instructions

Type safety is king. Treat configuration parsing, schema validation, dependency
checks, and shell lint as compiler boundaries. Do not cast, override, bypass, or
silence those boundaries.

Assume intention does not imply outcome. Verify base cases before changing
behavior, add executable checks for every contract, and encode information in
validated types instead of unstructured strings or ambient environment state.

Additional project rules:

- `cutover/` owns whole-path replacement and guarded recovery.
  The normal installer owns the marked entrypoint that cutover renders.

- `config/schema.tsv` is the public configuration authority.
- Configuration files are data, never sourced shell code.
- Shell startup must not perform network access, install software, prompt, or
  export credentials globally.
- A feature explicitly set to `on` must fail clearly when its dependency is
  missing. `auto` may skip an unavailable optional dependency; `off` must do
  nothing.
- Plugins are loaded only from validated manifests and trusted physical roots.
- Tests use disposable `HOME` and XDG directories. Never read or mutate live
  credentials, host files, or shell startup files from a test.
- Preserve unrelated user work and keep migration actions previewable,
  idempotent, and reversible.
