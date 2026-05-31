# System Transparency Risk Audit - 2026-05-31

This audit converts the current Markdown and codebase state into a risk register
for making TeaAgent more transparent, controllable, and systematically
engineered.

## Scope

- Reviewed product and governance Markdown: `README.md`, `docs/product-contract.md`,
  `docs/acceptance.md`, `docs/maturity-matrix.md`, `docs/threat-model.md`,
  `docs/use-cases.md`, `docs/use-case-matrix.md`, `docs/backlog-priority.md`,
  `docs/plans/remediation-roadmap.md`, and `docs/plans/governance-hardening.md`.
- Reviewed core governance code paths around tool registration, policy, audit,
  hooks, MCP adapters, plugins, code-analysis tools, and external code-analysis
  backends.
- Used `cx` to inspect the local symbol graph for `teaagent`, including
  `ToolRegistry`, `policy`, and code-analysis tool surfaces.
- Ran lightweight checks for acceptance collection, documentation consistency,
  competitive documentation refresh, and tool linting.

## Verification Snapshot

| Check | Result | Notes |
| --- | --- | --- |
| `python3 -m pytest tests/acceptance --collect-only -q` | Pass | 273 acceptance tests collected. |
| `teaagent tool lint --root .` | Pass with warnings | Two warnings remain around workspace read tool metadata. |
| `python3 scripts/validate_docs_consistency.py` | Failed before this audit patch | `docs/use-cases.md` survey marker did not match the script regex. |
| `python3 scripts/refresh_competitive_docs.py --check` | Failed before this audit patch | Same survey marker issue blocked the check. |
| `cx overview teaagent` | Pass with escalation | `cx` needed access to its local database outside the sandbox. |

## Evidence Summary

| Evidence | Source | Risk Signal |
| --- | --- | --- |
| Hook registry supports argument and result mutation, but registry execution ignored returned values. | `teaagent/hooks.py`, `teaagent/tools.py` | Hook lifecycle may appear to work in direct tests while not affecting real tool execution. |
| Code-analysis graph ingestion was keyed to a process-global `__default__` graph (mitigated 2026-05-31: per-root `scope_key`). | `teaagent/code_analysis/_tools.py` | Cross-workspace contamination risk reduced; unbounded dict growth remains (see O-NEW1). |
| External `cx` and `qmd` subprocess adapters run without an explicit timeout. | `teaagent/external_backends.py` | Long-running or wedged external tools can stall an agent run. |
| Code-parse actions rely on action-specific keys after generic schema acceptance. | `teaagent/external_backends.py` | Missing fields can become implementation exceptions instead of classified, actionable tool errors. |
| `AuditLevel.L3` is documented as encrypted at rest in code comments, while the implementation stores payloads as-is. | `teaagent/audit.py` | Evidence claim and privacy behavior are misaligned. |
| Remote MCP annotations are trusted when present; unknown destructive intent is not fail-closed by default. | `teaagent/mcp_tool_adapter.py` | Unannotated remote tools can be treated as non-destructive depending on policy mode. |
| Plugin source audit strict mode is opt-in through `TEAAGENT_PLUGINS_STRICT=1`. | `teaagent/plugins.py` | Development convenience can leak into release posture unless the runtime profile forces strict mode. |
| Package classifier says Alpha while docs describe multiple stable surfaces. | `pyproject.toml`, `docs/maturity-matrix.md`, `README.md` | External maturity messaging can drift and overpromise or undercut trust. |
| CI runs docs consistency checks before acceptance tiers. | `.github/workflows/ci.yml` | Documentation drift can block all verification, which is good, but the current broken marker showed the gate was red. |

## Ranked Findings

### F-001 - Hook mutation contract is not wired through `ToolRegistry.execute`

Severity: High

`HookRegistry.run_pre_hooks` returns possibly modified arguments, and
`HookRegistry.run_post_hooks` returns a possibly modified result. `ToolRegistry`
currently calls both methods but continues with the original arguments and
result. This creates a split-brain contract: hook unit tests can pass while real
tool execution ignores hook transformations.

Required outcome: real tool execution must use the pre-hook arguments, return
the post-hook result, and record hook changes in audit-friendly form.

### F-002 - Documentation consistency gate was red

Severity: High

The use-case survey marker combined "reviewed" and "last refreshed" in one
parenthetical phrase, while the consistency script expected the reviewed date to
stand alone. The scripts are release-gate style checks, so this kind of drift
can block verification before code tests run.

Required outcome: generated or hand-maintained docs must use canonical markers,
and the docs validator should report the exact expected pattern.

### F-003 - Code-analysis graph state is global and underspecified

Severity: High (partially mitigated 2026-05-31)

`code_relations_to_graph` ingests data into an in-memory graph keyed through
`__default__`. The tool is stateful and non-idempotent but is not classified as
destructive. The main risk is not file damage; it is hidden shared state that can
pollute later answers.

**Mitigation shipped:** graphs are keyed by workspace `scope_key` (config root),
`stateful=True` on the tool, `stateful_without_governance` lint, and
`test_graph_isolation_by_root`.

**Remaining:** LRU eviction for `_GRAPH_BY_ROOT` (see O-NEW1 in
`new-risk-findings-2026-05-31.md`).

### F-004 - External code-analysis backends need timeouts and classified errors

Severity: High

The `cx` and `qmd` adapters call subprocesses without explicit timeouts. Several
actions also assume required action-specific keys after a broad input schema has
accepted the request.

Required outcome: every external backend invocation has a bounded timeout,
classified failure, and action-specific validation before execution.

### F-005 - Remote MCP tool trust policy should fail closed for unknown mutation

Severity: High

MCP hints are useful, but remote servers are a trust boundary. A remote tool with
missing or weak annotations should not silently inherit a non-destructive posture
when the name or schema suggests mutation.

Required outcome: unknown remote tools need explicit trust profile approval,
capability manifest review, or conservative mutation classification.

### F-006 - Audit privacy claim is stronger than implementation

Severity: Medium

The code describes `AuditLevel.L3` as encrypted at rest. The current
implementation stores the payload directly with HMAC chaining and file
permission controls, but no encryption layer.

Required outcome: either implement encryption for L3, or rename/reword the level
so operators understand the actual privacy property.

### F-007 - Release maturity claims need one canonical source

Severity: Medium

The maturity matrix presents stable surfaces, while package metadata still uses
the Alpha classifier. This may be intentional, but it needs a canonical release
channel model so docs, package metadata, README, and acceptance gates do not tell
different stories.

Required outcome: define channel status once, generate or validate downstream
claims from it, and tie promotions to evidence.

### F-008 - Plugin strict mode must be part of release profiles

Severity: Medium

Third-party plugin audit can warn but continue unless strict mode is enabled.
That is acceptable for local experimentation, but release, CI, and managed
runtime profiles should fail closed.

Required outcome: release profiles set strict plugin audit by default, and tests
prove unknown plugin sources are blocked in strict profiles.

### F-009 - Tool lint warnings need an explicit warning budget

Severity: Medium

`teaagent tool lint --root .` passes, but warning-level issues still exist. A
warning budget is acceptable if owned and justified; otherwise warnings become
background noise.

Required outcome: every warning is either fixed, documented as intentional, or
bound to an expiry task.

## Risk Register

| ID | Risk | Impact | Likelihood | Owner Surface | Control |
| --- | --- | --- | --- | --- | --- |
| RSK-001 | Hook transformations are silently ignored in real tool execution. | High | Medium | Tools, hooks | Add registry integration tests and wire returned values. |
| RSK-002 | Docs consistency blocks CI before useful test feedback. | Medium | Medium | Docs, CI | Canonical markers plus pre-commit docs check. |
| RSK-003 | Process-global code graph leaks context across workspaces. | High | Medium | Code analysis | Scope graph by root/run and clear on run boundary. |
| RSK-004 | Stateful tool is not obviously classified as stateful. | Medium | High | Tool governance | Add stateful annotation or destructive/capability gate. |
| RSK-005 | External backend hangs consume run budget. | High | Medium | Backends | Add timeout and timeout-specific error class. |
| RSK-006 | Missing backend args surface as raw exceptions. | Medium | Medium | Backends | Validate per action before subprocess calls. |
| RSK-007 | Remote MCP server underreports destructive behavior. | High | Medium | MCP adapter, policy | Unknown remote tools require explicit trust. |
| RSK-008 | Audit privacy documentation overstates encryption. | High | Medium | Audit | Align level names, docs, and tests. |
| RSK-009 | Plugin strictness differs between local and release runs. | Medium | Medium | Plugins, runtime profiles | Profile-driven strict defaults. |
| RSK-010 | Warning-level tool lint issues become normalized. | Medium | High | Tool registry | Warning budget file and release gate. |
| RSK-011 | Package maturity metadata conflicts with docs. | Medium | Medium | Release docs | Single release-status source. |
| RSK-012 | Multi-writer audit behavior is not proven for shared filesystems. | High | Low | Audit storage | Document unsupported modes or add locking probe. |
| RSK-013 | Acceptance count can look strong while high-risk flows lack targeted tests. | High | Medium | QA | Map risks to acceptance IDs. |
| RSK-014 | Generated competitive docs drift from manually edited docs. | Medium | Medium | Docs generation | Treat generator output as source-controlled evidence. |
| RSK-015 | Policy decisions are hard to explain after the fact. | High | Low | Policy, audit | Add decision reason fields to denial/approval audit records. |
| RSK-016 | Capability manifests do not cover all remote/local tool trust edges. | High | Medium | Tool governance | Add manifest coverage report. |
| RSK-017 | Release gates differ across local, CI, and managed runtime. | High | Medium | CI, runtime | Define named verification profiles. |
| RSK-018 | Operator cannot see which risks are accepted vs open. | Medium | High | Project management | Maintain risk register with status and due date. |
| RSK-019 | Large safety claims are not traceable to tests. | High | Medium | Docs, QA | Claim-to-evidence matrix. |
| RSK-020 | Sandbox-specific local tooling failures hide real dependency needs. | Medium | Medium | Developer experience | Add diagnostics for `cx` database and permissions. |

## Human Review Gates

Human review is required before:

- Enabling remote MCP tools from an untrusted server.
- Promoting a release channel or changing public maturity claims.
- Relaxing destructive-tool approval policy.
- Disabling audit logging, HMAC chaining, or docs consistency gates.
- Accepting warning budgets for release blockers.
- Changing plugin trust defaults for managed or CI profiles.

## Residual Unknowns

- The audit did not execute the full acceptance suite; it collected the acceptance
  tests and inspected existing gate documentation.
- The `cx` local database path required escalation in this environment, so local
  reproducibility should be documented.
- This audit did not test multi-process audit writers on NFS or networked
  filesystems.
- The audit did not compare every public README claim to every acceptance test;
  that is assigned to the engineering plan.
