# external_backends — Behavior Specification

## Purpose

`external_backends` provides adapter contracts and registration helpers for knowledge-search and code-parse backends while keeping callers backend-agnostic.

## Current State

- Lifecycle registry lives in `teaagent/backend_registry.py` (`BackendRegistry`, `get_default_backend_registry`).
- `teaagent/external_backends.py` defines protocols, adapters, validator/factory helpers, and wrapper registration/getters.
- Default registrations are installed at import time (`local` knowledge backend and `cx_cli` code-parse backend).

## Behavior Contract

1. Registration requires non-empty names; blank names raise `ValueError`.
2. Lookup is strict; unknown backend names raise `ValueError`.
3. Health checks are best-effort: prefer `check_health()`, else `health(root=...)`, else report nohealthcheckavailable.
4. Lifecycle operations are non-fatal across registry entries: one backend failure is logged and does not stop iteration.
5. `FallbackKnowledgeBackend` calls primary first; on failure it calls fallback and annotates result with `fallback_used` and `primary_error`.
6. Validation-enabled registry variants enforce protocol method presence before accepting registration.

## Invariants

- Registry state is keyed by backend name and returns the latest binding.
- `is_initialized()` reflects lifecycle transition points (`initialize()` true, `shutdown()` false).
- Wrapper APIs (`register_*`, `get_*`) dispatch through a singleton default registry.
- Backend integration failures are surfaced as explicit exceptions or structured unhealthy states, never silently ignored.
