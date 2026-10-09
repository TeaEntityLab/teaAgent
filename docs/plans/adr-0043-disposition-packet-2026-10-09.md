# ADR-0043 Disposition Evidence Packet — 2026-10-09

> **Claim class:** Prepared evidence packet for the ADR-0043 expiry review. It records measurements and proposed steps. It is not a disposition, not an approval of any deletion plan, and not a scheduling authority.
> **Status:** Prepared packet; no disposition taken.
> **Owner:** docs (packet preparation). Disposition authority: project owner under ADR-0043 and DR-006.
> **Last reviewed:** 2026-10-09
> **Review trigger:** ADR-0043 expiry review (2026-12-09); any `owner-override` decision on a surface; any importer found by the falsifier checks in section 5.
> **Authority:** [ADR-0043](../adr/0043-legacy-competitive-surface-quarantine.md) (register and expiry); [ADR-0029](../adr/0029-consensus-validation-deferred.md) and its [disposition spec](../specs/consensus-validation-disposition-spec-2026-07-11.md) (deletion procedure precedent); [ADR-0041](../adr/0041-execution-surface-unification-and-harness-thinning.md) (domain-module scope); [Roadmap review 2026-10-09](../reviews/roadmap-review-and-improvement-plan-2026-10-09.md) section 4 Phase 3 (the request this packet answers).
> **Action register:** G-P2-21 ([06-action-register](../retrospective/06-action-register.md), line 75).
> **Measured at:** HEAD `67a9b97675e173c2583e3ba04ed182e1e5c8eb35`, 2026-10-09. The first `git status --short` of the session was clean. During the session, 17 tracked files outside this packet became modified (section 7); this packet did not edit them, and its counts were rechecked against that state with no change.

## 0. What changes versus the ADR-0043 table

Terms used below:

- **Import-time** means the module object is loaded by `import teaagent.cli`. The `teaagent` console script is `teaagent.cli:main` (`pyproject.toml:136`), so this happens on every CLI invocation.
- **Executed** means the module's behaviour runs on a daily command. Only import-time was measured at runtime; execution was not traced (section 7).

Findings that differ from ADR-0043:

1. **"Daily-path reachable: No" is wrong for import-time.** After `import teaagent.cli` the following are in `sys.modules`: `teaagent.federated_sync`; `teaagent.consensus` and its submodules; `teaagent.cli._handlers._consensus`; `teaagent.cli._handlers._sync`; `teaagent.jit_approval_server`; `teaagent.approval` and `teaagent.approval.server`; `teaagent.control_plane_api`; `teaagent.skill_router`; `teaagent.skill_executor` (command in section 5, F1). `import teaagent` alone loads none of the eight surfaces.
2. **`consensus/` has production importers.** `RiskLevel` is imported at module level by `teaagent/skill_executor.py:14`, `teaagent/skill_router.py:15`, and `teaagent/governance/review_gate.py:20`. `VoteDecision` and `ConsensusEngine` are imported by `teaagent/vote_relay.py:16`, and `teaagent/swarm.py:23` imports from the package. A deletion of `consensus/` needs `RiskLevel` relocated first. The statement "zero production importers" does not hold for this row.
3. **Coupled modules missing from the register.** A deletion must also change these: `teaagent/vote_relay.py` (380 lines); `teaagent/control_plane_api.py` (447 lines; imports `JITApprovalServer` at module level, `:26`); `teaagent/cli/_handlers/_sync.py` (294); `teaagent/cli/_handlers/_control_plane.py` (50); `teaagent/cli/_consensus_parsers.py` (347); `teaagent/cli/_control_plane_parsers.py` (63). Non-quarantined modules that import from quarantined code are `skill_router.py`, `skill_executor.py`, `swarm.py`, `policy.py`, and `approval/manager.py`.
4. **Size figures.** ADR-0043 "Consequences" says "roughly 3,500 LOC" of quarantined surface. The seven rows that are default-delete, excluding `context_bus.py`, total 4,920 lines (section 6). The roadmap review's 4,920 reproduces exactly for those rows. Its 11,622 test-line figure does not reproduce (section 6, note N2).
5. **ANP date.** `teaagent/anp_adapter.py` was first added 2026-05-18 (`ddcd61f5`). The register's "added 2026-09-15" is the date the quarantine row was written, not the file's creation date.
6. **Guards missing from the register** are listed in section 2.0. The largest are `tests/test_root_module_count.py`, `scripts/validate_wiring.py` (`ENTRY_ROOTS` includes `teaagent.jit_approval_server`), and CI `governance-gate` (`.github/workflows/ci.yml:300, :303`).

## 1. Method and exact commands

**Interpreter.** `/tmp/claude-0/-home-user-teaAgent/85b3f922-99e2-589b-9c9a-2f4fb7529027/scratchpad/venv/bin/python` (Python 3.12.3, pytest 9.1.1), run from `/home/user/teaAgent`.

**Importer sweep (C1).** Exact form from the request, run for each module token `<m>`:

```
grep -rn "import <m>\|from teaagent.<m>\|from teaagent import .*<m>" teaagent/ scripts/ --include=*.py
```

Additional forms run for every token: relative imports (`grep -rn "from \.\+\(federated_sync\|signature_relay\|workflow_engine\|jit_approval_server\|anp_adapter\|context_bus\|consensus\)\b" teaagent/ scripts/ --include=*.py`, zero hits); string and importlib references (`grep -rn "['\"]teaagent\.\(...\)" teaagent/ scripts/ --include=*.py`).

**Lazy and compat tables (C2).** `grep -n "<m>" teaagent/_lazy_exports.py teaagent/_compat_modules.py`. The `approval` package's lazy map is at `teaagent/approval/__init__.py:35` with `__getattr__` at `:94`.

**CLI registration (C3).** `grep -rn "<cli-token>" teaagent/cli/ --include=*.py`, plus the `add_parser` sites listed per surface.

**Runtime import check (C4).**

```
python -c "import sys, teaagent.cli; print([m for m in sys.modules if m.startswith('teaagent') and any(t in m for t in ('federated_sync','signature_relay','workflow_engine','consensus','jit_approval_server','approval.server','control_plane_api','anp_adapter','context_bus','swarm','skill_router','skill_executor'))])"
python -c "import sys, teaagent; ..."   # same membership test, import teaagent only
python -X importtime -c "import teaagent.cli"   # cross-check with import timing
```

**Static reachability (C5).** An AST import graph of `teaagent/` (502 modules, 3,964 import edges). Module-level and function-level imports are both edges. `if TYPE_CHECKING:` blocks are excluded. Parent-package edges are included. Breadth-first search runs from the daily handler modules: `cli/_handlers/_agent/run.py`, `runs.py`, `preflight.py`, `resume.py`, `cli/_handlers/agent_misc.py`, `cli/_handlers/_chat.py`, `cli/_handlers/_ergonomics/approval.py`. This is an over-approximation: function-level imports count regardless of runtime gating. It does not model `__getattr__` lazy exports (section 5, F2). The script is in the session scratchpad and is not committed.

**Test matrix.** Each test file under `tests/` and `tests/acceptance/` was matched against per-surface import patterns. Counts come from `python -m pytest --collect-only -q -p no:cacheprovider -o addopts="" <files>`. LOC comes from `wc -l`.

## 2. Shared guards and per-surface evidence

### 2.0 Shared guards (measured at HEAD)

- `scripts/check_root_module_count.py`: `ROOT_BASELINE = 184` (`:9`). Measured output: `Root module count OK: 177 <= 184`. `tests/test_root_module_count.py:10` asserts `count_root_modules() <= ROOT_BASELINE`. The root-level targets are `federated_sync.py`, `signature_relay.py`, `workflow_engine.py`, `jit_approval_server.py`, and `anp_adapter.py` (5); with `context_bus.py`, 6. Count after deletion: 172 (171 with `context_bus.py`). ADR-0030 records the baseline at 184.
- `scripts/check_god_modules.py`: 18 exemptions (measured `exemptions=18`). None of the eight targets is exempt. `teaagent/swarm.py` is exempt (`:41`) and imports `consensus` (`swarm.py:23`) and `context_bus` (`swarm.py:32`).
- `scripts/validate_wiring.py`: `ENTRY_ROOTS` includes `teaagent.jit_approval_server` (`:24`); optional-root handling at `:185`. Measured: `Wiring validation passed.`
- `scripts/validate_event_spine_wiring.py:80`: table entry `teaagent.context_bus:ContextBus` ("unwired in production"). Measured: `Event-spine wiring check passed.`
- `scripts/run_test_tier.py:34`: smoke target `test_phase5_context_bus.py`.
- `scripts/run_acceptance_tier.py:31`: p1 tier lists `test_anp_adapter_flow.py`.
- `.github/workflows/ci.yml`: `governance-gate` job (lines 263–305). Line 300 runs `test_phase5_context_bus.py`, `test_phase5_workflow_engine.py`, `test_phase5_jit_approval_server.py`, `test_federated_sync.py`, `test_signature_relay.py`, `test_remediation_p1_p2.py`. Line 303 runs `test_consensus_flow.py`, `test_sandbox_enhancement_flow.py`, `test_skill_executor.py`. Lines 44, 49, 53, 58–59 run the validators above; lines 80, 96, 116 run acceptance tiers.
- `docs/acceptance.md`: row at line 60 (`test_anp_adapter_flow.py`) and the p1 row at line 205.
- `docs/generated/*` and `docs/okf-catalog*.yaml`: no matches for the module tokens. The "consensus" matches in `docs/generated/docs-inventory.md` are ADR and spec filenames. `scripts/verify_docs.sh:5` runs `generate_docs_inventory.py --check`.
- `docs/`: 73 files mention at least one token (`grep -rln "federated_sync\|signature_relay\|workflow_engine\|jit_approval_server\|anp_adapter\|context_bus\|teaagent/consensus" docs/ | wc -l`). These are documentation references, not guards. Present-tense lines that a deletion would need to change: `README.md:176` (context bus delta sharing), `:187` (remote JIT approval section), `:220` (multi-agent list naming ContextBus, WorkflowEngine, JIT). `docs/product-contract.md:61` sits under "Future Goals (Aspirational)" and is not a present-tense claim.

**Owner-override template** (used in each surface's "keep" line; the owner fills every field, and no field is inferred here):

> `owner-override` (ADR-0043 expiry), dated `<YYYY-MM-DD>`: keep `<path>` as a promoted `<class>` surface until `<date>`. Rationale (owner-supplied): `<text>`. Scope: `<daily path | opt-in path | config-gated path>`. Guards retained: `<list from section 2>`. Recorded in: `<DR-006 entry | operator friction log entry>`.

### 2.1 `teaagent/federated_sync.py` (register row 1)

- **Size:** `wc -l teaagent/federated_sync.py` → 763. Register says 763 + 398 test; measured `tests/test_federated_sync.py` is 399.
- **Importers:**

| Site | Form | Class | Reach |
| --- | --- | --- | --- |
| `teaagent/cli/_handlers/_sync.py:13` | module-level | CLI opt-in handler (`teaagent sync`) | import-time on every invocation (`cli/__init__.py:27` → `_handlers/__init__.py:253`) |
| `teaagent/policy.py:343` | function-level in `_check_multi_sig_quorum` (`:245`) | production, config-gated | runs only if `multi_sig_config.enabled` (guard `:256`) |
| `teaagent/approval/manager.py:611` | function-level in `_collect_peer_signatures` (`:595`; called from `check_quorum` `:491`→`:559`) | production, config-gated | `check_quorum` returns at `:502` unless `config.enabled`; the caller sets `multisig_attempted` from `enabled` at `:1022–1032` |

- Lazy export and compat: none (`grep -n federated_sync teaagent/_lazy_exports.py teaagent/_compat_modules.py` → no output).
- Internal imports: `federated_sync.py:542, :636` import `signature_relay` (row 2).
- Dependency, not an importer: `federated_sync.py:24` imports `federated_signature_token` and `signature_relay_api_token` from `teaagent/security_env.py` (not quarantined).
- **Daily path:** import-time yes. Execution only when `MultiSigQuorumConfig.enabled` is true. The register's "No" holds for execution only.
- **Guards:** `tests/test_federated_sync.py` (21 tests), `tests/test_sync_cli.py` (9), `tests/test_signature_relay.py` (4; also imports the federated module). `tests/test_policy.py` (66 tests) matches once, a skip reason at `:1049`. CI `ci.yml:300`. CLI: `cli/__init__.py:229–233, :450–454`; `cli/_handlers/__init__.py:253–256, :446`; the `sync` subparser at `cli/_misc_parsers/advanced.py:340`.
- **Recovery anchor:** HEAD `67a9b976`. First add: `git log --diff-filter=A --format='%h %ad' --date=short -- teaagent/federated_sync.py | tail -1` → `906db0e3 2026-05-27`.
- **Default disposition (register, verbatim):** "Promote under `owner-override` if multisig is wanted, else delete." Review Phase 3 default: "Delete together [with signature_relay] unless multisig is ratified." The register gives no single default.
- **To keep:** an owner-override naming the multisig path (`MultiSigQuorumConfig.enabled=True`; `policy.py:245`; `approval/manager.py:491`) and the WAN-multisig ratification the register requires. The owner must state the rationale.

### 2.2 `teaagent/signature_relay.py` (register row 2)

- **Size:** `wc -l teaagent/signature_relay.py` → 492. Register says 492 + 212 test; measured `tests/test_signature_relay.py` is 213.
- **Importers:** `federated_sync.py:542, :636` (function-level, internal to row 1). `cli/_handlers/_sync.py:239` (`SignatureRelayServer`) and `:274` (`SignatureRelayClient`), both function-level, reached only through the `sync signature-relay` subcommands. Lazy export and compat: none.
- String and config coupling, not imports: `teaagent/security_env.py:50` (`signature_relay_api_token()`); `teaagent/coordination/approval_backend.py:46` (docstring mention of `require_signature_relay_bind_auth`). `tests/test_redis_approval_auth.py:5` mentions it in a docstring only.
- CLI registration: `cli/__init__.py:231, :452`; `cli/_handlers/__init__.py:256, :446`; `cli/_misc_parsers/advanced.py:336, :401, :423`.
- **Daily path:** No. Not loaded by `import teaagent.cli`. Executed only by `teaagent sync signature-relay`.
- **Guards:** `tests/test_signature_relay.py` (4 tests). `tests/acceptance/test_security_security_env_flow.py` (14 tests) imports the helper `signature_relay_api_token` from `security_env`, not the module; the helper remains after deletion unless removed. CI `ci.yml:300`.
- **Recovery anchor:** first add `bf86d966 2026-05-29` (`git log --diff-filter=A --format='%h %ad' --date=short -- teaagent/signature_relay.py | tail -1`).
- **Default disposition (register, verbatim):** "Delete with `federated_sync` unless WAN multisig is ratified."
- **To keep:** an owner-override that names this module and states the WAN-multisig ratification; it cannot be kept without row 1 unless the owner separately ratifies the relay alone.

### 2.3 `teaagent/domain/workflow_engine.py` (register row 3), with SKILL.md

- **Size:** `wc -l teaagent/domain/workflow_engine.py` → 768 (ADR-0041 table says 748; measured 768). SKILL.md at `teaagent/skills/builtin/workflow-orchestration/SKILL.md` → 31. Note: the path in the request, `skills/builtin/workflow-orchestration/SKILL.md`, does not exist; the file is under `teaagent/skills/builtin/`.
- **Importers (C1, C2):** the only importer under `teaagent/` or `scripts/` is the root shim, `teaagent/workflow_engine.py:12`. No lazy export. No compat entry in `_compat_modules.py`. `grep -rn "workflow-orchestration" teaagent tests scripts --include=*.py` → `tests/test_prompt_assets.py:234` only.
- **Tests importing the domain module directly:** `tests/test_inline_todo_resolutions.py` (12 tests).
- **Daily path:** No. Not in the import-time set; not reached in the static closure from daily handlers (C5).
- **Guards:** `tests/test_prompt_assets.py:234` pins `workflow-orchestration` in the list of skill docs that must be present (14 tests, 241 lines). The ADR-0041 scope lists this module as one of five domain modules; the roadmap review requires that scope to be amended in the same change.
- **Recovery anchor:** first add `5acaae76 2026-06-20`.
- **Default disposition (register, verbatim):** "**Strongest deletion candidate** — importer sweep done 2026-09-13: zero production callers (only the root compat shim + tests reference it)." Review Phase 3: "Delete; amend ADR-0041's five-module scope in the same change."
- **Basis:** `grep -rn "import workflow_engine\|from teaagent.domain.workflow_engine\|from teaagent import .*workflow_engine" teaagent/ scripts/ --include=*.py` → the shim only. The register's "zero production callers" statement agrees with this sweep.

### 2.4 `teaagent/workflow_engine.py` root shim (register row 4)

- **Size:** `wc -l` → 30. First add `d55cd298 2026-05-28`.
- **Importers:** none under `teaagent/` or `scripts/` (the sweep's only hit is the shim's own docstring and its `:12` import of the domain module). Tests importing the shim: `tests/test_remediation_p1_p2.py` (11 tests), `tests/test_mode1_chaining.py` (60), `tests/test_phase4_workflow_engine.py` (10), `tests/test_phase5_workflow_engine.py` (7), `tests/test_workflow_durable_checkpoint_depth.py` (3), `tests/test_real_usage_agents.py` (83).
- **Runtime:** not loaded by `import teaagent.cli` (C4).
- **Root freeze:** counts toward the 177 root modules (section 2.0).
- **Default disposition (register, verbatim):** "Keep while ADR-0030 root-module freeze stands; delete with its target."

### 2.5 `teaagent/consensus/` and `teaagent/cli/_handlers/_consensus.py` (register row 5)

- **Size:** `wc -l teaagent/consensus/*.py` → `__init__.py` 46, `engine.py` 511, `peer_registry.py` 211, `types.py` 397, `voting.py` 238 = 1,403. `teaagent/cli/_handlers/_consensus.py` → 503. Register lists 475 + engine/registry/voting; that figure does not match the current tree.
- **Importers of `teaagent.consensus` (C1):**

| Site | Form | Class | Reach |
| --- | --- | --- | --- |
| `teaagent/swarm.py:23` | module-level (`ConsensusEngine` and related) | orchestrator; `enable_consensus` defaults to `False` (`:209`) | not import-time; not in the daily static closure |
| `teaagent/skill_executor.py:14` | module-level, `RiskLevel` | skill execution (production) | import-time: `cli/_handlers/_sandbox.py:10` |
| `teaagent/skill_router.py:15` | module-level, `RiskLevel` | skill routing (production) | import-time: `cli/_handlers/_sandbox.py:11` |
| `teaagent/governance/review_gate.py:20` | module-level, `RiskLevel` | governance | lazy via `goal_record.py:240` |
| `teaagent/vote_relay.py:16` | module-level, `ConsensusEngine`, `VoteDecision` | unregistered module (380 lines) | lazy via `cli/_handlers/_consensus.py:446, :488` |
| `teaagent/subagents/_manager.py:111` | function-level, `RiskLevel` | subagent path | not traced to execution |
| `teaagent/cli/_handlers/_consensus.py:10, :23` | module-level | CLI opt-in (`teaagent consensus`) | import-time: `cli/_handlers/__init__.py:64` |
| `teaagent/cli/_handlers/_consensus.py:487`; `teaagent/cli/_handlers/_sandbox.py:22, :108` | function-level | CLI | not traced |

- Lazy export and compat: none (`_lazy_exports.py` and `_compat_modules.py` have no `consensus` entry).
- CLI registration: `cli/_consensus_parsers.py:134` (`add_parser('consensus')`); `cli/__init__.py:106–121` (imports), `:381–382` (register imports), `:555` (`register_consensus`).
- **Daily path:** import-time yes (through `_handlers/_consensus.py:10` and through `RiskLevel` in `skill_router` and `skill_executor`). Execution of consensus code on the daily path was not traced.
- **Guards (strict match on import paths, 14 files; `test_docs_consistency.py` is a string match and is listed separately):** `tests/test_consensus_cli.py` (13 tests), `tests/test_consensus_engine_history.py` (1), `tests/acceptance/test_consensus_flow.py` (5), `tests/acceptance/test_sandbox_enhancement_flow.py` (6), `tests/acceptance/test_security_vote_relay_flow.py` (9), `tests/test_analysis_followups.py` (5), `tests/test_phase6_remaining_features.py` (8), `tests/test_real_usage_agents.py` (83), `tests/test_remediation_p1_p2.py` (11), `tests/test_skill_executor.py` (3), `tests/test_skill_router.py` (10), `tests/test_strategic_features.py` (9), `tests/test_surface_auth_hardening.py` (6), `tests/test_swarm.py` (21). CI `ci.yml:303` runs three of these. `tests/test_docs_consistency.py` matches only a string that names the deleted validation module's path (`:520–536`); it does not import `consensus/`.
- **Recovery anchor:** `teaagent/consensus.py` (the pre-package file) first added `e2361d95 2026-05-28`; the package directory first added `bd6e0389 2026-06-07`; `cli/_handlers/_consensus.py` first added `6e3934ad 2026-05-28`. HEAD `67a9b976`.
- **Default disposition (register, verbatim):** "Delete per ADR-0029 precedent unless swarm consensus is ratified." Review Phase 3: "Delete per ADR-0029 precedent unless `owner-override`."
- **To keep:** an owner-override that names `consensus/` and the `RiskLevel` dependency. It also needs a statement of whether `swarm.py`'s `enable_consensus` mode stays.

### 2.6 `teaagent/jit_approval_server.py` (register row 6), with `approval/server.py`

- **Size:** `wc -l teaagent/jit_approval_server.py` → 445. `teaagent/approval/server.py` (canonical import shim) → 5. Register says 445 + 286 test; measured JIT tests total 291 (`test_phase5_jit_approval_server.py`) plus 45, 161, 181 (section 6).
- **Importers (C1, C2, C3):**

| Site | Form | Class | Reach |
| --- | --- | --- | --- |
| `teaagent/control_plane_api.py:26` | module-level; `ControlPlaneServer` takes `jit_server` (`:56`) | control-plane HTTP server (unregistered in the register) | import-time through `cli/_handlers/_control_plane.py:9` → `_handlers/__init__.py:81` |
| `teaagent/approval/server.py:3` | module-level in shim | canonical import path | import-time, see next row |
| `teaagent/approval/__init__.py:35` (lazy map), `:94` (`__getattr__`), `:137` (TYPE_CHECKING) | lazy export | package API | `cli/_handlers/_control_plane.py:8` (`from teaagent.approval import JITApprovalServer`) loads it at import time |
| `teaagent/cli/_handlers/_control_plane.py:8, :18, :45` | module-level / call | CLI opt-in `teaagent control-plane serve` | import-time |
| `scripts/validate_wiring.py:24, :185` | entry root (optional) | guard | — |
| `scripts/migrate_imports.py:64, :81` | migration table | one-off script | — |

- Runtime check (C4): `import teaagent.cli` loads `teaagent.jit_approval_server`, `teaagent.approval`, and `teaagent.approval.server`. `import teaagent` loads none of them.
- CLI registration: `cli/_control_plane_parsers.py:14` (`'control-plane'`); `cli/__init__.py:121` (import), `:382` (`register_control_plane`).
- **Daily path:** import-time yes. Execution only under `control-plane serve`.
- **Guards:** `tests/test_phase5_jit_approval_server.py` (11 tests), `tests/test_phase6_jit_server.py` (2), `tests/test_cli_handlers_control_plane.py` (5; patches `teaagent.cli._handlers._control_plane.JITApprovalServer`; not in the register and not found by the first sweep), `tests/test_phase6_control_plane.py` (5; control-plane scope). CI `ci.yml:300`. `README.md:187` describes the JIT surface as On Hold.
- **Recovery anchor:** `git log --diff-filter=A --format='%h %ad' --date=short -- teaagent/jit_approval_server.py | tail -1` → `3a101b23 2026-05-28`.
- **Default disposition (register, verbatim):** "Covered by the M4 background-lifecycle/operator-cockpit carve-out **only if** a dogfood session is scheduled; else delete." Review Phase 3: "Keep only if Phase 2 happened and used it; else delete."
- **To keep:** an owner-override tied to the M4 carve-out, naming whether a dogfood session is scheduled (the register's condition). `control_plane_api.py` must be edited in either case, because it imports this module at module level.

### 2.7 `teaagent/anp_adapter.py` (register row 7)

- **Size:** `wc -l teaagent/anp_adapter.py` → 516. Register says 516 + 464 test; measured ANP tests total 464 (`test_anp_adapter.py` 247 + acceptance 217).
- **Importers:** none under `teaagent/` outside the module itself, `teaagent/_lazy_exports.py:12–19` (8 symbols, lazy), and `teaagent/__init__.py:41–50` (TYPE_CHECKING block only). Command: `grep -rln "ANP\|anp_adapter" teaagent --include=*.py | grep -v "teaagent/anp_adapter.py\|_lazy_exports\|teaagent/__init__.py"` → no output. Scripts: `scripts/run_acceptance_tier.py:31` (filename string in the p1 tier).
- **Daily path:** No. Not in the import-time set; no runtime importer.
- **Guards:** `tests/test_anp_adapter.py` (11 tests), `tests/acceptance/test_anp_adapter_flow.py` (6), `tests/test_bug_fixes.py` (29 tests; a class named `TestANPAdapterIndexBoundsFix`, no module import found). `scripts/run_acceptance_tier.py:31`; `docs/acceptance.md:60, :205`; `docs/adr/0007-anp-adapter-boundary.md:98, :104`; `README.md:124` (link to ADR 0007).
- **Recovery anchor:** `git log --diff-filter=A --format='%h %ad' --date=short -- teaagent/anp_adapter.py | tail -1` → `ddcd61f5 2026-05-18`.
- **Default disposition (register, verbatim):** "Promote under `owner-override` if ANP federation is wanted, else delete."
- **To keep:** an owner-override naming ANP federation and the acceptance tier that would need to keep `test_anp_adapter_flow.py`. The register also says "the `agent run` ANP path is a stub"; that claim was not verified (section 7).

### 2.8 `teaagent/context_bus.py` (register row 8)

- **Size:** `wc -l teaagent/context_bus.py` → 553. Register lists no LOC. Tests: `tests/test_phase5_context_bus.py` (364; 12 tests), `tests/test_security_fixes.py` (450; 20; mixed), `tests/test_swarm.py` (490; 21; mixed).
- **Importers:** `teaagent/swarm.py:32` (module-level). Scripts: `scripts/validate_event_spine_wiring.py:80`, `scripts/run_test_tier.py:34`. Lazy and compat: none.
- **Daily path:** No. Not in the import-time set; `swarm.py` is not in the daily static closure.
- **Docs with present-tense claims:** `README.md:176, :220`; `docs/context-bus-and-federated-sync.md`; `docs/adr/0027-context-bus-architecture.md`; `docs/adr/0020-phase-5-hardened-sandbox-virtualization.md:143, :235`.
- **Recovery anchor:** `git log --diff-filter=A --format='%h %ad' --date=short -- teaagent/context_bus.py | tail -1` → `3a101b23 2026-05-28`.
- **Default disposition (register, verbatim):** "Governed by G3/ADR-0032, not by this ADR; see the accepted fourth-parallel-system risk." Section 4 therefore has no execution plan for this row.

## 3. ADR status reconciliation

Current `## Status` lines, quoted from each file (first non-empty line after the heading):

| ADR | Current status line | Surfaces it covers |
| --- | --- | --- |
| 0007 | `Accepted and Implemented - 2026-05-22` | `anp_adapter.py` (ADR-0007 `:98`, `:104`) |
| 0019 | `Accepted and Implemented (Beta) - 2026-05-27 to 2026-05-29` | `consensus/` (ADR-0019 cites `teaagent/consensus.py`, `cli/_handlers/_consensus.py`) |
| 0020 | `Accepted and Implemented (Beta) - 2026-05-27 to 2026-05-29` | `workflow_engine.py`, `context_bus.py`, `jit_approval_server.py` (ADR-0020 `:142–145`, `:235–237`) |
| 0021 | `Accepted and Implemented (Beta) - 2026-05-27 to 2026-05-29` | JIT approve/reject dashboard and `control_plane_api.py` (ADR-0021 `:13`, `:69–70`, `:75`) |

**Proposed replacement** (text from the request, for owner approval; the four ADRs are not edited here):

> `Accepted and Implemented (Beta) — surface quarantined under ADR-0043 since 2026-09-09; disposition review 2026-12-09`

Notes for the owner:

- ADR-0007's current line has no "(Beta)". The proposed text adds it. Confirm or drop it for ADR-0007.
- The roadmap review (section 4, Phase 3) asks for `Superseded in part by ADR-0043` instead. ADR-0043 itself quarantines and does not use "supersede". The proposed text leaves disposition open, which matches ADR-0043's expiry wording. The owner chooses between the two.
- Apply the change in the same commit as the disposition, so that no ADR cites a live status for a deleted surface.

## 4. Execution order if the owner chooses delete

Each plan is bounded to one surface. Plans are ordered by coupling, lowest first. None is authorised by this packet. ADR-0029's procedure applies to each: before deletion, record the feature intent, a symbol-level inventory, and the recovery anchor (section 2 gives the anchors; the inventory is not prepared here).

**Standard verification after every step** (run in order; each must pass or the step is reverted):

```
python3 scripts/validate_wiring.py
python3 scripts/check_root_module_count.py
python3 scripts/check_god_modules.py
python3 scripts/validate_event_spine_wiring.py
python3 scripts/validate_runner_invariants.py
python3 scripts/run_test_tier.py --tier smoke
python3 scripts/run_acceptance_tier.py --tier p0
python3 scripts/run_acceptance_tier.py --tier p1
python3 scripts/generate_docs_inventory.py --check
python -X importtime -c "import teaagent.cli" 2>&1 | grep -E "<removed-module>"   # expect no output
grep -rn "<removed-module>" teaagent scripts tests docs README.md --include=*.py --include=*.md --include=*.yml   # expect only recorded history
```

**P1 — ANP (row 7).** Remove `teaagent/anp_adapter.py` (516), `tests/test_anp_adapter.py` (247), `tests/acceptance/test_anp_adapter_flow.py` (217). Edit: `teaagent/_lazy_exports.py:12–19`; the TYPE_CHECKING block at `teaagent/__init__.py:41–50`; `scripts/run_acceptance_tier.py:31`; `docs/acceptance.md:60, :205`; the ANP class in `tests/test_bug_fixes.py` (not measured). Root count −1. Expected removal: 980 lines (516 + 247 + 217). Owner note: ADR-0007 status (section 3).

**P2 — Workflow engine (rows 3 and 4).** Remove `teaagent/domain/workflow_engine.py` (768), `teaagent/workflow_engine.py` (30), `teaagent/skills/builtin/workflow-orchestration/SKILL.md` (31), and the exclusive tests `tests/test_phase4_workflow_engine.py` (291), `tests/test_phase5_workflow_engine.py` (92), `tests/test_workflow_durable_checkpoint_depth.py` (166). Edit, removing workflow cases only (not measured; the files stay): `tests/test_mode1_chaining.py` (916; matches only the workflow token, so each case needs checking), `tests/test_inline_todo_resolutions.py` (213), `tests/test_remediation_p1_p2.py` (267), `tests/test_real_usage_agents.py` (2,610). Also `tests/test_prompt_assets.py:234` (remove the skill from the list), `ci.yml:300`, and the ADR-0041 five-module scope. Root count −1. Expected removal: 829 + 549 = 1,378 lines.

**P3 — JIT approval server (row 6).** Two variants; the owner picks one.

- (a) Remove the control-plane as well: `teaagent/jit_approval_server.py` (445), `teaagent/approval/server.py` (5), `teaagent/control_plane_api.py` (447), `teaagent/cli/_handlers/_control_plane.py` (50), `teaagent/cli/_control_plane_parsers.py` (63), `tests/test_phase5_jit_approval_server.py` (291), `tests/test_phase6_jit_server.py` (45), `tests/test_cli_handlers_control_plane.py` (161), `tests/test_phase6_control_plane.py` (181). Expected removal: 1,688 lines. Edit: `teaagent/approval/__init__.py:35, :137`; `cli/__init__.py:121, :381–382`; `cli/_handlers/__init__.py:81`; `scripts/validate_wiring.py:24, :185`; `scripts/migrate_imports.py:64, :81`; `ci.yml:300`; `README.md:187`.
- (b) Keep the control-plane without JIT: remove only `jit_approval_server.py`, `approval/server.py`, and `test_phase5_jit_approval_server.py`, `test_phase6_jit_server.py`, `test_cli_handlers_control_plane.py` (947 lines). Edit `control_plane_api.py:26, :56`, `cli/_handlers/_control_plane.py:8, :18, :45` (the handler otherwise breaks), `test_phase6_control_plane.py`. Root count −1.

**P4 — Federated sync and signature relay (rows 1 and 2).** Prerequisite: the owner's multisig decision (section 2.1). Remove `teaagent/federated_sync.py` (763), `teaagent/signature_relay.py` (492), `teaagent/cli/_handlers/_sync.py` (294; its docstring names federated sync only), and `tests/test_federated_sync.py` (399), `tests/test_sync_cli.py` (149), `tests/test_signature_relay.py` (213). Expected removal: 2,310 lines. Edit: the `sync` subparser (`cli/_misc_parsers/advanced.py:340–430`); `cli/__init__.py:229–233, :450–454`; `cli/_handlers/__init__.py:253–256, :446`; the federated branch of `policy.py` `_check_multi_sig_quorum` (`:245`); the federated branch of `approval/manager.py` `_collect_peer_signatures` (`:595`), with the `check_quorum` path (`:491`) and `MultiSigQuorumConfig` (`:167`) decided together; `security_env.py:50` and the federated helper if unused afterward; `coordination/approval_backend.py:46` (docstring); mixed tests `tests/acceptance/test_security_security_env_flow.py` (91) and the multisig cases in `tests/test_policy.py` (1,235). Also `ci.yml:300`. Root count −2.

**P5 — Consensus (row 5).** Prerequisite: relocate `RiskLevel` (and `VoteDecision` if still used) out of `consensus/` into a non-quarantined module. The size of the `RiskLevel` definition was not measured. Moving it into a new root module adds one root module, which the freeze would reject unless the baseline changes. Remove `teaagent/consensus/` (1,403), `teaagent/cli/_handlers/_consensus.py` (503), `teaagent/cli/_consensus_parsers.py` (347), `teaagent/vote_relay.py` (380; unregistered, decision needed), and exclusive tests `tests/test_consensus_cli.py` (378), `tests/test_consensus_engine_history.py` (57), `tests/acceptance/test_consensus_flow.py` (266), `tests/acceptance/test_sandbox_enhancement_flow.py` (138), `tests/acceptance/test_security_vote_relay_flow.py` (138). Expected removal: 3,610 lines. Edit: `swarm.py` (1,104; exempt from the god-module check; consensus at `:23`, `:453`, `:465`, `:644`); `skill_executor.py:14`; `skill_router.py:15`; `governance/review_gate.py:20`; `subagents/_manager.py:111–112`; `cli/_handlers/_sandbox.py:10–11, :22, :108`; `governance/policy_routing.py` (`REQUIRE_CONSENSUS` at `:28`, `required_consensus_rule` at `:52`, decision branch at `:325–331`; a string rule ID with no import); the consensus CLI registrations (`cli/__init__.py:106–121, :381–382, :555`; `cli/_handlers/__init__.py:64`); mixed tests importing `RiskLevel` (`test_skill_executor.py`, `test_skill_router.py`, `test_swarm.py`, `test_strategic_features.py`, `test_surface_auth_hardening.py`, `test_real_usage_agents.py`, `test_remediation_p1_p2.py`, `test_analysis_followups.py`, `test_phase6_remaining_features.py`); `ci.yml:303`.

**P6 — Context bus (row 8).** No plan. The register places this row under G3/ADR-0032. Its guards are listed in section 2.8 for reference.

## 5. Falsifiers

The packet is wrong if any of these holds. Each check is runnable.

- **F1. Import-time claims are wrong.** Run `python -c "import sys, teaagent.cli; print(sorted(m for m in sys.modules if m.startswith('teaagent') and any(t in m for t in ('federated_sync','signature_relay','workflow_engine','consensus','jit_approval_server','approval.server','control_plane_api','anp_adapter','context_bus','swarm'))))"`. The packet expects `federated_sync`, `consensus`, `jit_approval_server`, `approval.server`, and `control_plane_api` to appear; it expects `signature_relay`, `workflow_engine`, `anp_adapter`, `context_bus`, and `swarm` not to appear. `import teaagent` alone is checked with the same test.
- **F2. The static graph misses lazy exports.** `teaagent/approval/__init__.py:94` (`__getattr__`) loads `approval.server`, which the static graph did not reach. Any "not reached" statement in this packet is an upper bound only for explicit imports. Runtime checks (F1) are authoritative for import-time.
- **F3. Dynamic imports the sweep cannot see.** `grep -rn "import_module(" teaagent --include=*.py` returns four sites: `teaagent/_compat_modules.py:31`, `teaagent/_lazy_exports.py:341`, `teaagent/approval/__init__.py:99`, `teaagent/managed_runtime.py:228`. The last takes `agent_module` from its caller and can load any named module. That path is not analysed. Plugin discovery uses `importlib.metadata.entry_points` (`teaagent/plugin_system.py:82`) and loads external packages, not `teaagent` submodules.
- **F4. Daily execution claims are wrong.** Execution was not traced. Check: run each daily command (`agent run`, `ask`, `approve`, `undo`, `daily`, `preflight`) in a scratch workspace with no network, and print `sys.modules` membership before and after. Any listed surface marked "No" in section 6 that appears is a falsifier.
- **F5. Search scope.** The sweep covered `teaagent/`, `scripts/`, `tests/`, `docs/`, `examples/`, and `skills/`. `examples/` has no matches for the tokens; `docs/` code fences contain no imports of the targets (`grep -rn "from teaagent\.\(federated_sync\|...\)" docs/ README.md` → no output). `teaagent/skills/builtin/workflow-orchestration/SKILL.md` mentions the name in text only.
- **F6. Deleting `consensus/` without relocating `RiskLevel` breaks import.** `python -c "import teaagent.cli"` after P5 would raise at `skill_router.py:15`. This must fail before the relocation and pass after it.
- **F7. The ANP register date is the file date.** If `git log --diff-filter=A -- teaagent/anp_adapter.py` showed 2026-09-15, the register would be right. It shows 2026-05-18.
- **F8. Minor number mismatches.** The register's test LOC values differ from `wc -l` by 1 for `federated_sync` (398 vs 399) and `signature_relay` (212 vs 213). The ADR-0041 `domain/workflow_engine.py` figure (748) differs from `wc -l` (768). None of these changes a disposition, but ADR text should be corrected when it is amended.

## 6. Summary per surface

LOC is `wc -l`. "Exclusive" tests are files whose import-level matches are for one surface only (section 2 and the matrix in section 1). Mixed files are not counted. Test counts are from `pytest --collect-only`.

| ADR-0043 row | Module LOC | Exclusive test LOC / tests | LOC removed (module + exclusive tests) | Import-time (every CLI start) | Executed on daily path | Default disposition (register) |
| --- | ---: | --- | ---: | --- | --- | --- |
| 1. `federated_sync.py` | 763 | 548 / 30 (`test_federated_sync`, `test_sync_cli`) | 1,311 | yes | no (only if multisig enabled) | Promote under owner-override if multisig wanted, else delete |
| 2. `signature_relay.py` | 492 | 213 / 4 (`test_signature_relay`) | 705 | no | no | Delete with row 1 unless WAN multisig ratified |
| 3. `domain/workflow_engine.py` (+ SKILL.md) | 768 + 31 | 549 / 20 | 1,348 | no | no | Strongest deletion candidate |
| 4. `workflow_engine.py` (root shim) | 30 | (tests of row 3) | 30 | no | no | Keep while ADR-0030 freeze stands; delete with row 3 |
| 5. `consensus/` + `cli/_handlers/_consensus.py` | 1,403 + 503 | 977 / 34 | 2,883 (+ `vote_relay.py` 380, unregistered) | yes | not traced (`swarm.py` is outside the static daily closure) | Delete per ADR-0029 precedent unless swarm consensus ratified |
| 6. `jit_approval_server.py` (+ `approval/server.py`) | 445 + 5 | 678 / 23 (incl. control-plane tests) | 1,128 (+ 560 if control-plane removed, P3a) | yes | no (only `control-plane serve`) | M4 carve-out only if dogfood scheduled; else delete |
| 7. `anp_adapter.py` | 516 | 464 / 17 | 980 | no | no | Promote under owner-override if ANP wanted, else delete |
| 8. `context_bus.py` | 553 | 364 / 12 | 917 (out of packet scope) | no | no | Governed by G3/ADR-0032 |

**Totals, rows 1–7 (the default-delete rows):**

- Module lines: 4,920 excluding SKILL.md and the `approval/server.py` shim, which matches the roadmap review's figure; 4,956 including them (`wc -l` over the listed files, total 5,509 with `context_bus.py`).
- Exclusive test lines: 3,429 across 128 collected tests.
- Rows with import-time reach: 1, 5, 6. Rows with no daily-path reach: 2, 3, 4, 7.

**Notes.**

- N1. The row 6 test total includes `tests/test_phase6_control_plane.py` (181, 5 tests), which is control-plane scoped. Variant P3(b) keeps it.
- N2. The roadmap review's 11,622 test-line figure is not reproduced. The strict union of the 33 import-matched test files is 10,926 lines and 470 collected tests (`wc -l` and pytest collection over the same list). Adding the loose matches (`test_policy.py`, `test_redis_approval_auth.py`, `test_bug_fixes.py`, `test_security_ssh_signatures_flow.py`, `test_security_vote_relay_flow.py`) gives 13,192 lines. Neither equals 11,622, so the review's file set is unknown.
- N3. ADR-0043's "roughly 3,500 LOC" understates the eight rows (4,920 excluding `context_bus.py`; 5,509 including it and the shims).

## 7. Could not verify

- Execution of daily commands. Only import-time was measured (F4 is the check to run).
- Per-case classification of mixed test files (`test_mode1_chaining.py`, `test_real_usage_agents.py`, `test_policy.py`, `test_swarm.py`, `test_security_fixes.py`, `test_bug_fixes.py`). Edits to these files are unmeasured.
- Whether a builtin-skill loader enumerates `workflow-orchestration` at runtime. No code outside tests references the name.
- The register's claim that the `agent run` ANP path is a stub.
- Whether any user configuration sets `MultiSigQuorumConfig.enabled=True` or uses `teaagent sync`. The repository holds no usage telemetry.
- The `RiskLevel` relocation design (the new module's location and the root-freeze effect).
- The smoke and acceptance tiers were not executed for this packet. Read-only guards passed at HEAD: root count, god modules, wiring, event-spine wiring.
- Working-tree state. After the first clean `git status`, 17 tracked files were modified (`scripts/report_docs_aging.py`, `teaagent/run_evidence.py`, `.github/workflows/ci.yml`, and 14 test files, including `tests/test_real_usage_agents.py`). They were not authored by this packet and were not reverted. The packet's counts for files in its own scope were rechecked: `tests/test_real_usage_agents.py` is still 2,610 lines with the same collected-test totals.

## 8. Commands and results recorded for this packet

- `git rev-parse HEAD` → `67a9b97675e173c2583e3ba04ed182e1e5c8eb35`. `git status --short` → no output before writing.
- `wc -l` figures in sections 2 and 6, and `wc -l teaagent/vote_relay.py teaagent/control_plane_api.py teaagent/cli/_handlers/_sync.py teaagent/cli/_handlers/_control_plane.py teaagent/cli/_control_plane_parsers.py teaagent/cli/_consensus_parsers.py ...` (coupled modules).
- `git log --diff-filter=A --format='%h %ad' --date=short -- <path> | tail -1` for each path in section 2.
- `python -m pytest --collect-only -q -p no:cacheprovider -o addopts="" <file list>` → `574 tests collected` for the 35 files in the first match list; `470` for the 33-file strict union (section 6).
- `python scripts/generate_docs_inventory.py --check` → exit 1 after this file was written. Regenerating into the scratchpad (not the repo) and diffing against `docs/generated/docs-inventory.md` shows 8 changed lines: this packet's row (`plans/adr-0043-disposition-packet-2026-10-09.md | archive`), the inventory's own row, and the Markdown count (667 → 669). The inventory must be regenerated in the recording commit; this packet does not edit it.
- `python scripts/check_root_module_count.py` → `Root module count OK: 177 <= 184`. `python scripts/check_god_modules.py` → `OK: No god modules found (threshold=800, exemptions=18).` `python scripts/validate_wiring.py` → `Wiring validation passed.` `python scripts/validate_event_spine_wiring.py` → `Event-spine wiring check passed.`

## References

- [ADR-0043](../adr/0043-legacy-competitive-surface-quarantine.md), [ADR-0029](../adr/0029-consensus-validation-deferred.md), [ADR-0041](../adr/0041-execution-surface-unification-and-harness-thinning.md), [ADR-0030](../adr/0030-root-module-freeze.md)
- [Consensus validation disposition spec](../specs/consensus-validation-disposition-spec-2026-07-11.md) (procedure precedent, section 2.1 preservation record)
- [Roadmap review 2026-10-09](../reviews/roadmap-review-and-improvement-plan-2026-10-09.md), section 4 Phase 3
- [Action register](../retrospective/06-action-register.md), G-P2-21 (line 75)
- ADR status lines: [ADR-0007](../adr/0007-anp-adapter-boundary.md), [ADR-0019](../adr/0019-phase-4-federated-swarm-consensus.md), [ADR-0020](../adr/0020-phase-5-hardened-sandbox-virtualization.md), [ADR-0021](../adr/0021-phase-6-skill-writer-docker-monitor-control-plane.md)
- Context bus and federation documentation: [context-bus-and-federated-sync](../context-bus-and-federated-sync.md); [acceptance catalogue](../acceptance.md)
