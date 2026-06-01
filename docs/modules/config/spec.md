# config — Behavior Specification

## Purpose

Workspace configuration management. Reads and merges configuration from `.teaagent/config.json` (and `.teaagent/config.toml`) with CLI-provided defaults.

## Behavior

- Configuration file discovery (workspace root, user home)
- Key-value merge with CLI overrides
- Provider configuration loading
- Permission mode baseline definition
