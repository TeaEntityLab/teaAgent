# TeaAgent Standards and Principles

## Governance Philosophy

TeaAgent is a **governance-first agent harness**. Every architectural decision subordinates raw capability to auditability, confinement, and human oversight. The harness is intentionally thin: orchestration, tool governance, state boundaries, audit, and validation belong here; domain reasoning belongs in the model or reviewed skills.

The project's classification in `pyproject.toml` is **Development Status :: 3 - Alpha**. Breaking changes are expected; stability guarantees are per-ADR.

---

## Design Principles

### 1. Explicit over implicit

Tool permissions are declared at registration, not inferred at runtime. Approval gates are hard code paths, not soft suggestions. Every destructive action must be explicitly approved or pre-authorised; no tool silently assumes permission.

### 2. Audit-first

Every tool call, approval decision, iteration, and final result is written to a JSONL audit log (mode `0600`, `fcntl.LOCK_EX`, `fsync` after each append) before the next action proceeds. Audit records are append-only and cannot be modified by normal harness operation.

### 3. Confinement as invariant

Workspace tools reject `../` escapes, absolute paths, and symlink escapes unconditionally — not as a configurable option. Shell commands are classified `inspect` or `mutate` before execution; `inspect` commands run with `shell=False`.

### 4. Fail closed on unknown state

An unregistered tool must be denied, not allowed. Unknown policy combinations default to denial. When a classifier cannot determine the safety of an input, it must treat the input as unsafe.

### 5. Harness stays thin

The harness provides primitives: registry, budget, approval, audit, sandbox. It does not encode task-domain knowledge. If a change to the harness requires reasoning about what a specific task does, the change is probably in the wrong layer.

### 6. Observable security

Security properties must be testable, not aspirational. Every security invariant defined in `SECURITY.md` has corresponding property tests (see `tests/test_workspace_tools.py:ShellClassifierPropertyTests`).

---

## Quality Standards

| Standard | Threshold | Enforced by |
|---|---|---|
| Test coverage (unit) | ≥ 75% lines | `pytest --cov-fail-under=75` (CI `test` job) |
| Skill test coverage | ≥ 80% lines | `docs/skill-governance.md` manual gate |
| Type coverage | All production code annotated | `mypy --disallow-untyped-defs` (CI `lint` job) |
| Lint | Zero errors | `ruff check .` (CI `lint` job) |
| Format | Canonical | `ruff format --check .` (CI `lint` job) |
| Dependency CVEs | Zero known CVEs in base PR gate; optional-extra CVEs governed separately | `pip-audit` lanes in CI `security` job |
| Acceptance suite | Count matches `docs/acceptance.md` | `acceptance-p0` / `acceptance-p1` CI jobs |
| Docs consistency | Scripts pass | `validate_docs_consistency.py` (CI `use-case-matrix` job) |

Thresholds are hard failures in CI. There are no exceptions for in-flight work — raise coverage or fix lint before merging.

---

## Versioning Scheme

TeaAgent uses **Semantic Versioning 2.0** (`MAJOR.MINOR.PATCH`):

- `PATCH` — backwards-compatible bug fixes that do not change tool schemas, audit event shapes, or permission semantics.
- `MINOR` — backwards-compatible additions: new tools, new optional config keys, new audit event types, new permission modes.
- `MAJOR` — breaking changes to the public API, tool schema, audit format, or permission model. Requires an ADR.

The `version` field in `pyproject.toml` is the single source of truth. Tags are `v{MAJOR}.{MINOR}.{PATCH}`.

---

## Architecture Decision Records

Significant decisions — tool governance changes, audit semantics, OAuth, MCP transport, Code Mode isolation, async patterns — are recorded as ADRs in `docs/adr/`. The current range is ADR 0001–0020. When a PR changes one of these domains, it must either cite an existing ADR or create a new one.

Format: `docs/adr/NNNN-short-title.md` with `Status`, `Decision`, `Rationale`, and `Implementation` sections.

---

## Language and Runtime

- Python ≥ 3.10 (tested on 3.10, 3.11, 3.12)
- No runtime dependencies by default; optional extras declared in `pyproject.toml`
- `py.typed` marker is present — downstream consumers can rely on type information

---

## Code Standards

### File header

Every production module starts with:

```python
from __future__ import annotations
```

This enables postponed evaluation of annotations (PEP 563) and is required for forward-reference type hints on Python 3.10.

### Formatting (enforced by `ruff format`)

- **Quotes**: single (`'`), not double. Exception: docstrings use triple-double (`"""`).
- **Indent**: 4 spaces, no tabs.
- **Line length**: soft limit of 88 characters; `E501` (line too long) is suppressed in ruff — prefer shorter lines but don't break for it.
- **Import sorting**: isort-compatible (`I` ruff rules). Standard library, then third-party, then local.

### Naming conventions

| Kind | Convention | Example |
|---|---|---|
| Module | `snake_case` | `audit.py`, `tool_call_context.py` |
| Class | `PascalCase` | `ApprovalPolicy`, `AuditLogger` |
| Function / method | `snake_case` | `check_tool_access`, `resolve_workspace_path` |
| Private function / method | `_snake_case` | `_apply_audit_level`, `_validate_relay_url` |
| Constant (module-level) | `UPPER_SNAKE_CASE` | `AUDIT_FILE_MODE`, `MAX_AUDIT_STRING_LENGTH` |
| Type alias | `PascalCase` | `AuditLevel`, `PermissionMode` |
| Test function | `test_<unit>_<scenario>_<outcome>` | `test_check_tool_access_unregistered_tool_denied` |

### Type annotations

All production code (everything under `teaagent/`, excluding paths in `[tool.coverage.run] omit`) must have complete type annotations enforced by:

```
mypy --disallow-untyped-defs --disallow-incomplete-defs --check-untyped-defs
```

- Use `Optional[X]` (not bare `X | None`) for Python 3.10 compatibility, or use `from __future__ import annotations` and write `X | None`.
- Use `from __future__ import annotations` to avoid circular import issues with type hints.
- Prefer `from collections.abc import Callable, Iterator` over `typing.Callable`, `typing.Iterator`.
- Use `TYPE_CHECKING` guard for imports needed only for type hints.
- Do not add `# type: ignore` without an explanatory comment on the same line.

### Dataclasses

Use `@dataclass(frozen=True)` for value objects and policy objects. Use `@dataclass` (mutable) only when the object has meaningful lifecycle state. Use `field(default_factory=...)` for mutable default values.

### Logging

Every module that emits log output declares:

```python
logger = logging.getLogger(__name__)
```

Use `logger.debug/info/warning/error/exception` — never `print()` in production code. Do not log credential values; the audit logger's redaction applies to audit events, not Python logger output.

### Comments and docstrings

- Default: no comments. Add a comment only when the **why** is non-obvious (hidden constraint, workaround for a specific bug, invariant that would surprise a reader).
- Do not comment what the code does — well-named identifiers do that.
- Do not reference the current task, ticket number, or caller in comments — those belong in the commit message or PR description.
- Public classes should have a one-line docstring stating the class's invariant or purpose. Public methods need a docstring only if their contract is non-obvious from the signature.
- Never write multi-paragraph docstrings for internal helpers.

### Error handling

- Raise `AgentHarnessError` subclasses (defined in `teaagent/errors.py`) for harness-layer errors. Do not raise bare `Exception` or `RuntimeError` from governance code.
- Do not silently swallow exceptions in governance, audit, or approval code paths.
- Only validate at system boundaries (user input, LLM output, external API responses). Trust internal invariants — do not add defensive checks for states that cannot occur.

---

## Documentation Standards

### What must be documented

| Change type | Required doc update |
|---|---|
| New CLI command or flag | `docs/cli.md` |
| New audit event type or shape change | `docs/audit-events.md` |
| New permission mode or approval semantic | `SECURITY.md` + relevant ADR |
| New acceptance flow test | `docs/acceptance.md` (count + description) |
| New optional extra / dependency | `docs/USAGE.md` or `README.md` extras table |
| Breaking API change | `CHANGELOG.md` `### Breaking` section + migration note |
| New ADR | `docs/adr/NNNN-short-title.md` |

### What does not need a doc update

- Bug fixes with no observable API change.
- Internal refactors with no user-visible effect.
- Test additions that don't introduce new acceptance flows.

### Doc currency

Documentation must describe the code as it currently works, not as it was planned to work. If you change behaviour, update the relevant doc in the same PR. Stale docs are treated as bugs.

Docs with `Last reviewed: YYYY-MM-DD` headers must be updated when the content they describe changes. The `scripts/validate_docs_consistency.py` script checks a subset of these.

### Format

- Markdown, GitHub-flavoured (`*.md`).
- One blank line between sections.
- Use fenced code blocks with language tags (`python`, `bash`, `json`).
- Tables for structured comparisons (permission matrices, job listings, etc.).
- No trailing whitespace. No "smart" quotes — use ASCII `'` and `"`.
- ADR format: `Status`, `Decision`, `Rationale`, `Implementation` sections, in that order.
