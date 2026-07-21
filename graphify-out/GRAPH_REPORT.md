# Graph Report - .  (2026-07-21)

## Corpus Check
- Corpus is ~16,069 words - fits in a single context window. You may not need a graph.

## Summary
- 282 nodes · 335 edges · 33 communities (29 shown, 4 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 14 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Architecture and Configuration
- Migration and Operations
- Credential Proxy Tests
- Installer Runtime
- Plugin Runtime
- Dependency Registry
- Apollo Migration
- Zsh Runtime Tests
- Plugin Tests
- Test Assertions
- Agent Instructions
- Configuration Resolver
- Profile Selection
- Configuration Resolution Tests
- Status Doctor Tests
- Compatibility Tests
- Configuration Validation Tests
- SDKMAN Lazy Tests
- Proxy Execution
- Status and Doctor
- External Plugin Tests
- Git Workflow Tests
- Core Guards
- Credential Providers
- Home Adapter
- Home Adapter Tests
- Profile Selection Tests
- CLI Dispatch
- Installer Tests
- Apollo Container Validation
- Repository Check
- Apollo Remote Validation
- Apollo Conversion Tests

## God Nodes (most connected - your core abstractions)
1. `Configuration Guide` - 8 edges
2. `Migration from Apollo and Artemis` - 8 edges
3. `Operations and Maintenance` - 8 edges
4. `Dotfiles` - 7 edges
5. `Target Architecture` - 7 edges
6. `Behavioral and Parity Contract` - 7 edges
7. `dotfiles_plugins_validate()` - 6 edges
8. `Dotfiles Knowledge Base` - 6 edges
9. `Source-Backed Concepts` - 6 edges
10. `Safe Operations` - 6 edges

## Surprising Connections (you probably didn't know these)
- `Compiler as Verification Boundary` --semantically_similar_to--> `Type Safety as a Boundary`  [INFERRED] [semantically similar]
  home/private_dot_codex/AGENTS.md → AGENTS.md
- `Management CLI` --semantically_similar_to--> `Dotfiles Management CLI`  [INFERRED] [semantically similar]
  docs/knowledge/runtime-architecture.md → README.md
- `Dotfiles` --references--> `Configuration Guide`  [EXTRACTED]
  README.md → docs/configuration.md
- `Separate Static File Adoption` --conceptually_related_to--> `Static Home Adapter`  [INFERRED]
  docs/migration.md → README.md
- `Codex Configuration Boundary` --references--> `Codex Agent Instructions`  [INFERRED]
  docs/operations.md → home/private_dot_codex/AGENTS.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Validated Configuration Pipeline** — docs_architecture_typed_configuration, docs_configuration_resolution_order, docs_configuration_data_file_grammar, docs_knowledge_configuration_model_schema_authority, docs_knowledge_configuration_model_deterministic_precedence [INFERRED 0.95]
- **Trusted Plugin Runtime Contract** — docs_configuration_feature_states, docs_configuration_external_enterprise_plugins, docs_knowledge_plugin_runtime_manifest_owned_discovery, docs_knowledge_plugin_runtime_trusted_root_loading, docs_knowledge_plugin_runtime_feature_state_machine [INFERRED 0.95]
- **Safe Machine Change Workflow** — docs_knowledge_safe_operations_previewable_home_changes, docs_migration_migration_validation, docs_migration_atomic_ownership_transfer, docs_migration_static_file_adoption, docs_migration_explicit_rollback, docs_operations_repository_gate [INFERRED 0.85]

## Communities (33 total, 4 thin omitted)

### Community 0 - "Architecture and Configuration"
Cohesion: 0.09
Nodes (30): Command-Scoped Credentials, Dependency Doctor, Deployment Adapter Boundary, Enterprise Composition, Target Architecture, Typed Configuration, Validated Shell Runtime, Behavior-First Migration (+22 more)

### Community 1 - "Migration and Operations"
Cohesion: 0.10
Nodes (26): Apollo Runtime, Artemis Runtime, Baseline Evidence, Verified Legacy Risks, Behavioral and Parity Contract, Compatibility Ledger, Configuration Ownership, Core Behavior (+18 more)

### Community 2 - "Credential Proxy Tests"
Cohesion: 0.10
Nodes (19): DOTFILES_CA_BUNDLE, DOTFILES_CONFIG_FILE, DOTFILES_GITHUB_CREDENTIAL_PROVIDER, DOTFILES_GITHUB_CREDENTIAL_REFERENCE, DOTFILES_PROXY_CREDENTIAL_PROVIDER, DOTFILES_PROXY_CREDENTIAL_REFERENCE, DOTFILES_PROXY_MODE, DOTFILES_PROXY_NO_PROXY (+11 more)

### Community 3 - "Installer Runtime"
Cohesion: 0.23
Nodes (12): dotfiles_install_apply(), dotfiles_install_atomic_replace(), dotfiles_install_command(), dotfiles_install_filter_blocks(), dotfiles_install_has_marker(), dotfiles_install_has_unmanaged_apollo(), dotfiles_install_legacy_blocks(), dotfiles_install_plan() (+4 more)

### Community 4 - "Plugin Runtime"
Cohesion: 0.35
Nodes (10): dotfiles_plugin_physical_path(), dotfiles_plugins_command(), dotfiles_plugins_list(), dotfiles_plugins_make_state(), dotfiles_plugins_normalize(), dotfiles_plugins_normalize_manifest(), dotfiles_plugins_paths(), dotfiles_plugins_validate() (+2 more)

### Community 5 - "Dependency Registry"
Cohesion: 0.25
Nodes (7): dotfiles_dependencies_normalize(), dotfiles_dependencies_normalize_file(), dotfiles_dependency_available(), dotfiles_dependency_exists(), dotfiles_dependency_platform_matches(), dotfiles_dependency_row(), dependencies.sh script

### Community 6 - "Apollo Migration"
Cohesion: 0.31
Nodes (9): dotfiles_migrate_apollo_collect(), dotfiles_migrate_apollo_command(), dotfiles_migrate_apollo_emit_toggle(), dotfiles_migrate_apollo_emit_value(), dotfiles_migrate_apollo_parse_file(), dotfiles_migrate_apollo_render_records(), dotfiles_migrate_apollo_with_records(), dotfiles_migrate_command() (+1 more)

### Community 7 - "Zsh Runtime Tests"
Cohesion: 0.20
Nodes (9): DOTFILES_CONFIG_FILE, DOTFILES_DEPENDENCIES_FILE, DOTFILES_PATH_APPEND, DOTFILES_PATH_PREPEND, DOTFILES_PLUGIN_MANIFEST_FILE, DOTFILES_SCHEMA_FILE, HOME, zsh_runtime_test.sh script (+1 more)

### Community 8 - "Plugin Tests"
Cohesion: 0.22
Nodes (8): DOTFILES_CONFIG_FILE, DOTFILES_DEPENDENCIES_FILE, DOTFILES_FEATURE_DEMO, DOTFILES_PLUGIN_MANIFEST_FILE, DOTFILES_SCHEMA_FILE, HOME, plugins_test.sh script, XDG_CONFIG_HOME

### Community 9 - "Test Assertions"
Cohesion: 0.44
Nodes (7): assert_failure_contains(), assert_output_contains(), assert_output_empty(), assert_success(), testlib.sh script, test_fail(), test_pass()

### Community 10 - "Agent Instructions"
Cohesion: 0.29
Nodes (8): Repository Instructions, Safe Runtime Contract, Type Safety as a Boundary, Codex Configuration Boundary, Codex Agent Instructions, Compiler as Verification Boundary, Pull Request Follow-Through, Validated Red-Green Checkpoints

### Community 11 - "Configuration Resolver"
Cohesion: 0.32
Nodes (4): dotfiles_config_collect_layers(), dotfiles_config_command(), dotfiles_config_resolve(), config.sh script

### Community 12 - "Profile Selection"
Cohesion: 0.39
Nodes (5): dotfiles_profile_command(), dotfiles_profile_selected(), dotfiles_profile_set(), dotfiles_profile_validate_list(), profile.sh script

### Community 13 - "Configuration Resolution Tests"
Cohesion: 0.25
Nodes (7): DOTFILES_CONFIG_FILE, DOTFILES_EDITOR, DOTFILES_PROFILE_FILES, DOTFILES_SCHEMA_FILE, HOME, config_resolution_test.sh script, XDG_CONFIG_HOME

### Community 14 - "Status Doctor Tests"
Cohesion: 0.25
Nodes (7): DOTFILES_CONFIG_FILE, DOTFILES_FEATURE_ZOXIDE, DOTFILES_GITHUB_CREDENTIAL_REFERENCE, DOTFILES_PROFILES, HOME, status_doctor_test.sh script, XDG_CONFIG_HOME

### Community 15 - "Compatibility Tests"
Cohesion: 0.33
Nodes (6): assert_surface(), DOTFILES_CONFIG_FILE, DOTFILES_PROFILES, HOME, compatibility_surface_test.sh script, XDG_CONFIG_HOME

### Community 16 - "Configuration Validation Tests"
Cohesion: 0.29
Nodes (6): DOTFILES_CONFIG_FILE, DOTFILES_PROFILE_FILES, DOTFILES_SCHEMA_FILE, HOME, config_validation_test.sh script, XDG_CONFIG_HOME

### Community 17 - "SDKMAN Lazy Tests"
Cohesion: 0.29
Nodes (6): DOTFILES_CONFIG_FILE, DOTFILES_FEATURE_SDKMAN, DOTFILES_PROFILES, HOME, sdkman_lazy_test.sh script, XDG_CONFIG_HOME

### Community 18 - "Proxy Execution"
Cohesion: 0.40
Nodes (3): dotfiles_proxy_command(), dotfiles_proxy_exec(), proxy.sh script

### Community 19 - "Status and Doctor"
Cohesion: 0.40
Nodes (3): dotfiles_doctor_command(), dotfiles_doctor_run(), status.sh script

### Community 20 - "External Plugin Tests"
Cohesion: 0.33
Nodes (5): DOTFILES_CONFIG_FILE, DOTFILES_PROFILES, HOME, external_plugin_test.sh script, XDG_CONFIG_HOME

### Community 21 - "Git Workflow Tests"
Cohesion: 0.33
Nodes (5): DOTFILES_CONFIG_FILE, DOTFILES_PROFILES, HOME, git_workflow_test.sh script, XDG_CONFIG_HOME

### Community 22 - "Core Guards"
Cohesion: 0.60
Nodes (4): dotfiles_error(), dotfiles_require_file(), dotfiles_require_safe_profile_name(), core.sh script

### Community 23 - "Credential Providers"
Cohesion: 0.50
Nodes (3): dotfiles_credential_command(), dotfiles_credential_exec_github(), credentials.sh script

### Community 24 - "Home Adapter"
Cohesion: 0.60
Nodes (4): dotfiles_home_chezmoi(), dotfiles_home_command(), dotfiles_home_require_chezmoi(), home.sh script

### Community 25 - "Home Adapter Tests"
Cohesion: 0.40
Nodes (4): HOME, PATH, home_adapter_test.sh script, XDG_CONFIG_HOME

### Community 26 - "Profile Selection Tests"
Cohesion: 0.40
Nodes (4): DOTFILES_CONFIG_FILE, HOME, profile_selection_test.sh script, XDG_CONFIG_HOME

### Community 27 - "CLI Dispatch"
Cohesion: 0.83
Nodes (3): dotfiles script, dotfiles_main(), dotfiles_usage()

### Community 28 - "Installer Tests"
Cohesion: 0.50
Nodes (3): HOME, install_test.sh script, XDG_CONFIG_HOME

## Knowledge Gaps
- **119 isolated node(s):** `config.sh script`, `core.sh script`, `credentials.sh script`, `dependencies.sh script`, `home.sh script` (+114 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Operations and Maintenance` connect `Migration and Operations` to `Architecture and Configuration`, `Agent Instructions`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Why does `Dotfiles Knowledge Base` connect `Architecture and Configuration` to `Migration and Operations`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Why does `Migration from Apollo and Artemis` connect `Migration and Operations` to `Architecture and Configuration`?**
  _High betweenness centrality (0.013) - this node is a cross-community bridge._
- **What connects `config.sh script`, `core.sh script`, `credentials.sh script` to the rest of the system?**
  _119 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Architecture and Configuration` be split into smaller, more focused modules?**
  _Cohesion score 0.08505747126436781 - nodes in this community are weakly interconnected._
- **Should `Migration and Operations` be split into smaller, more focused modules?**
  _Cohesion score 0.09538461538461539 - nodes in this community are weakly interconnected._
- **Should `Credential Proxy Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.1 - nodes in this community are weakly interconnected._