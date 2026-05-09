# Changelog

All notable changes to TeaAgent are tracked here.

## Unreleased

- Updated README, SECURITY, and P2 scope docs so Code Mode backend limitations and optional dependency groups match the current implementation.
- Added MCP HTTP boundary tests for malformed `Content-Length`, oversized JSON-RPC bodies, and scalar JSON payloads; oversized MCP JSON-RPC requests now return `413` consistently.
- Hardened `SQLiteOAuthStore` client-secret storage with PBKDF2-SHA256 hashes, per-client random salts, schema-version metadata, and server-side validation through the store instead of plaintext retrieval.
- Cleaned repo agent instructions by removing embedded session-memory context from `AGENTS.md`.
- Added a dedicated telemetry CI job that installs `.[dev,telemetry]` and runs telemetry tests without relying on skipped optional imports.
- Extended release automation with PyPI Trusted Publishing and GitHub artifact provenance attestation for tagged releases.
- Added `release` and `security` optional dependency groups for local build/twine and `pip-audit` workflows.
- Removed the remaining package-level mypy strictness overrides; all `teaagent/` modules now run with `disallow_untyped_defs` and `disallow_incomplete_defs` enabled.
- Added packaging and contribution hygiene: `MANIFEST.in`, `CONTRIBUTING.md`, and a pull request template with validation/governance checklist.
- Added audit redaction for secret-like patterns inside otherwise non-sensitive strings (Bearer tokens, `sk-...` keys, and URL/query-style `token=...`/`api_key=...` values).
- Added `SQLiteOAuthStore`, a durable OAuth 2.1 store for clients, one-time authorization codes, and DPoP nonces. It uses SQLite WAL mode and an immediate transaction for consume-and-delete authorization-code semantics.
- Added `configure_metrics()` and a new `metrics_otlp_endpoint` field on `TelemetryConfig` so OpenTelemetry counters and histograms have a real `MeterProvider` with OTLP/console exporters; previously only an in-memory metrics path existed.
- Fixed the `TracingHTTPTransport` docstring example to match the actual two-argument constructor.
- Hardened OAuth resource-server verification: `OAuth21ResourceServer` and `OAuth21AuthorizationServer.introspect_token` now resolve the verification key by JWT `kid` via `OAuthKeyRing`, so rotated signing keys keep verifying without losing trust in older tokens.
- Added Dependabot configuration (`pip` + `github-actions`, weekly) and a Security workflow that runs `pip-audit` and CodeQL on every push, pull request, and weekly schedule.
- Restricted the release workflow to least-privilege permissions (`contents: read`).
- Re-licensed the project under the MIT License and added the matching PyPI classifier.
- Marked the package as typed by shipping `teaagent/py.typed` and configuring setuptools `package-data`.
- Hardened `ContainerCodeModeBackend`: rejects empty images at construction, enforces `--read-only`, `--cap-drop=ALL`, `--security-opt=no-new-privileges`, non-root `--user`, `--tmpfs /tmp`, `--memory-swap`, and a separate `--ulimit cpu` for CPU time. The `--cpus` flag now reflects an explicit CPU-share field instead of reusing the CPU-time budget.
- Added `CodeModeSandbox.max_output_bytes` and switched the container backend to `subprocess.Popen` so oversized stdout is rejected instead of buffered without bound.
- Updated `SECURITY.md` to reflect the storage-layer file locking that audit and memory writes already use, and added `docs/p3-scope.md` to mirror the existing P0/P1/P2 scope notes.
- Added a pluggable Code Mode backend boundary with the existing child-process backend and a Docker/Podman-style container backend.
- Added audit-driven metrics sinks for run and tool lifecycle counters plus basic histogram samples.
- Added release packaging basics: license file, changelog, and distribution build workflow.
