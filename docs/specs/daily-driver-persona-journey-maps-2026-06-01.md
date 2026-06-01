# Persona Journey Maps & Journey-to-Acceptance Matrix
# 2026-06-01

**Fills:** Gap **F-ECO-002** from `agent-ecosystem-daily-use-gap-review-2026-05-31.md`
— *"add a journey-to-acceptance matrix with required P0/P1/P2 flows per persona and
surface."* The May-31 review listed journey **gaps** in the abstract; this spec turns
them into concrete, surface-anchored journeys mapped to the **real command surface**
(from `teaagent/tui/__init__.py` HELP_TEXT and `teaagent/cli`).

**Grounding.** Personas extend the two existing onboarding docs
(`docs/onboarding-ml-researchers.md`, `docs/onboarding-security-engineers.md`) plus the
implied daily-driver developer and automation operator. Commands cited are real TUI/CLI
verbs. Where a step depends on a known defect, it links the finding ID from
`daily-driver-code-grounded-ux-findings-2026-06-01.md`.

---

## Personas

| ID | Persona | Primary surface | Source |
|----|---------|-----------------|--------|
| **P-DEV** | Solo daily-driver developer | TUI chat / `teaagent chat` | product-contract golden path |
| **P-OPS** | Automation / agent-mode operator | `teaagent agent run`, background, automations | `cli/_handlers/agent_automation.py` |
| **P-ML** | ML researcher (experiment-centric) | TUI `parallel`/`select`, agent | `docs/onboarding-ml-researchers.md` |
| **P-SEC** | Security / compliance reviewer | audit viewer, approvals, MCP trust | `docs/onboarding-security-engineers.md` |

---

## Canonical journey spine (all personas)

`setup → inspect → plan → execute → approve → verify → recover → remember → report`
(the spine named in F-ECO-002). Each persona traverses a subset with different
emphasis and a different required priority per step.

---

## P-DEV — Solo daily-driver developer

| Step | Command(s) | Required behavior | Pri | Blocking finding |
|------|-----------|-------------------|-----|------------------|
| setup | `setup`, `doctor` | Workspace + provider validated in one pass | P0 | — |
| inspect | `daily`, `runs`, `context list` | Readiness + recent runs + budget visible | P0 | CG-06 (panel clears screen) |
| plan | `plan <task>`, `preflight` | Read-only plan artifact before writes | P1 | — |
| execute | `ask`/`run`, chat REPL | Answer is shown; status accurate | **P0** | **CG-01** |
| approve | `approve`, `permission`, preset grants | y/n/path/tool/stop choices honored | P0 | — |
| verify | run summary (`format_run_summary`) | Files-changed + cost + undo cmd shown | P1 | CG-03 (cost fake) |
| recover | `undo [run_id]` | Reverts only this run's edits | **P0** | **CG-02** |
| remember | `memory add/list/search` | Workspace memory persists | P2 | — |
| report | run summary / audit log path | Sendable summary (see evidence-bundle spec) | P1 | — |

**P-DEV verdict:** Two P0 blockers (CG-01 execute, CG-02 recover) sit on the spine.
Until Phase 0 of the hardening plan lands, P-DEV's daily loop is not trustworthy.

---

## P-OPS — Automation / agent-mode operator

| Step | Command(s) | Required behavior | Pri | Notes / gap |
|------|-----------|-------------------|-----|-------------|
| setup | `agent run --detach`, automations | Background task starts, run_id returned | P1 | F-ECO-003 background not productized |
| inspect | `attach <id> --follow`, `status <run_id>` | Live status + heartbeat liveness | P1 | — |
| plan | `plan`, automation templates | Provenance-gated automation creation | P1 | — |
| execute | `agent run`, swarm/subagent | Detached run honors permission mode | P0 | — |
| approve | JIT approval server | Approve out-of-band without attaching | P1 | F-ECO-008 (MCP trust journey) |
| verify | audit chain, `eval` | Tamper-evident audit of unattended run | P0 | — |
| recover | `resume <id>`, `undo` | Resume partial/failed background run | P1 | F-ECO-012 lifecycle |
| remember | failure cards | Failure reused as warning next run | P2 | grounded: `get_failure_warnings` |
| report | audit export, webhook sink | Status delivered to channel | P1 | F-ECO-012 missed-run remediation |

**P-OPS verdict:** Functionally rich, but lifecycle (review/renew/pause/transfer/expire)
and out-of-band approval are the thin spots — matches F-ECO-003/008/012.

---

## P-ML — ML researcher

| Step | Command(s) | Required behavior | Pri | Notes |
|------|-----------|-------------------|-----|-------|
| setup | `setup`, provider (ollama/vllm) | Local model providers work | P1 | — |
| inspect | `daily`, `parallel` status panel | Compare branch stats (+ins/-del/files) | P1 | grounded: `_parallel_stack.compare_branches` |
| plan | `complexity`, `estimate` | Token-budget estimate before run | P1 | — |
| execute | `parallel <A> <B> …` | Isolated git-branch experiments | P0 | — |
| approve | `select <option>` | Merge chosen branch, discard others | P0 | — |
| verify | branch diff comparison | Per-branch insertions/deletions/files | P1 | grounded |
| recover | `cancel` | Clean up all experiment branches | P1 | — |
| remember | memory catalog | Record which hypothesis won | P2 | — |
| report | run summary per branch | Reproducible comparison artifact | P2 | evidence-bundle spec |

**P-ML verdict:** The parallel-experiment journey is genuinely differentiated and
mostly complete; the gap is a *comparison report artifact* (reproducibility), not the
mechanics.

---

## P-SEC — Security / compliance reviewer

| Step | Command(s) | Required behavior | Pri | Notes |
|------|-----------|-------------------|-----|-------|
| setup | risk-mode selection | Choose permission mode by risk | P0 | see risk-decision-table doc |
| inspect | audit viewer, `show <run_id>` | Hash-chained, tamper-evident trail | P0 | differentiator |
| plan | threat model, product-contract | Constraints legible per surface | P1 | F-ECO-013 |
| execute | (observes) | Every action attributed + audited | P0 | UX-F7 |
| approve | approval policy, MCP trust review | Scoped grant, revoke, expiry | P1 | F-ECO-008 |
| verify | audit export, `aibom`, sigstore | Evidence bundle for compliance | P1 | evidence-bundle spec |
| recover | undo journal audit | Recovery itself is audited | P1 | CG-08 (undo ambiguity) |
| remember | — | n/a | — | — |
| report | audit export, control plane | Compliance-grade report | P1 | F-ECO-011 |

**P-SEC verdict:** This is teaagent's strongest persona (governance-first). The gaps are
*legibility* (one risk-mode guide) and *out-of-band trust review*, not capability.

---

## Journey-to-acceptance matrix (required test coverage)

| Journey step | Existing test (if known) | Required new acceptance | Persona(s) |
|---|---|---|---|
| execute shows answer | — | `test_chat_repl_displays_answer` (P0-1) | P-DEV |
| recover scoped | — | `test_chat_repl_undo_scope` (P0-2) | P-DEV, P-OPS |
| verify shows real cost | `test_run_summary.py` | extend: assert non-zero session cost (P1-1) | all |
| cross-surface parity | — | `test_chat_surface_parity` (P1-3) | P-DEV |
| background lifecycle | background attach/resume tests | review/pause/transfer/expire | P-OPS |
| MCP trust journey | `test_remote_mcp_consumption_flow` | unknown-tool/expired-token/revoke | P-OPS, P-SEC |
| parallel compare report | parallel branch tests | comparison evidence artifact | P-ML |
| risk-mode selection | — | per-mode capability assertion | P-SEC |

## Open questions for the maintainer

1. Are P-OPS background/cloud journeys a near-term commitment or a documented non-goal
   (F-ECO-004)? The matrix above assumes commitment; flip to non-goal if not.
2. Should P-ML's parallel-experiment comparison produce a file artifact (reproducible)
   or remain TUI-only? Affects evidence-bundle scope.
</content>
