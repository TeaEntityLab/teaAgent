# Roadmap Rethink — Decision Rationale and Proposed Plan (2026-09-16)

> **Claim class:** Dated review and continuation record; not current truth or scheduling authority.
> **Status:** Review recorded 2026-09-16; owner adjudicated G23–G38 "Yes for all" the same day and R2/R3/R5 landed (see §7). R4 and the independent decision gates remain open.
> **Owner:** docs
> **Last reviewed:** 2026-09-16
> **Review trigger:** Owner disposition, a relevant contract/source change, new owner-use evidence, or a named decision gate.
> **Recording authorization:** User requested “Record all thoughts and plans” after the roadmap rethink. This authorizes preserving the review, not implementing its proposals or supplying owner verdicts.
> **Repository HEAD observed when recording:** `c4a2566d2604ddee11e14a38b8bdbfbd10b0564f`. Historical fix commits below are cited from their records; ancestry was not checked in this review.

## 1. Goal, scope, and recommendation

**Recommendation: retain harness-first, but sequence work around one dependable local coding workflow rather than more surfaces, review rounds, or command-count dogfooding.**

The intended outcome is a smaller actionable roadmap: distinguish existing-contract repairs, completed dispositions, unverified daily use, and genuinely held expansion. This record preserves the conclusions, supporting evidence, alternatives, proposed work, acceptance criteria, and unresolved decisions from the review. It is not a transcript of deliberation.

Scope: roadmap sequencing and completion claims, the consolidated dogfood findings, first-run/background/MCP reliability, owner-use evidence, and H4/EFX/quarantine boundaries. No runtime changes, enforcement changes, new framework, live-provider calls, deletions, or owner testimony are authorized by this record.

Authority remains, in order:

1. [Harness-First Direction](../strategy/harness-first-direction-2026-06-13.md).
2. [DR-006 Owner Decision](../strategy/dr-006-owner-decision-2026-06-22.md).
3. [Roadmap Status](../roadmap-status.md).
4. [Backlog Priority](../backlog-priority.md).
5. Relevant ADRs, then the [Held Roadmap Forward-Spec Index](../specs/held-roadmap-forward-spec-index-2026-07-11.md), then dated review evidence such as this file.

The [Daily-Driver Current Status](../daily-driver-current-status.md) owns operator-facing runtime trust, not scheduling. The [Current Roadmap Execution Plan](../plans/current-roadmap-execution-plan-2026-08-26.md) sequences admitted work; it cannot promote held work.

**Identifier boundary:** G1–G38 below are dogfood finding IDs from the [consolidated findings](../work-log/dogfood-findings-2026-09-15.md), not the separate north-star goals G1–G6. D1 is the shadow-denial candidate; B1 is owner-observed dogfood acceptance.

## 2. Evidence and verification boundary

The preceding review executed the commands below successfully. This recording step preserves those results rather than claiming to have rerun the dogfood scenarios.

| Check executed during review | Observed result | What it establishes / does not establish |
| --- | --- | --- |
| `python3 scripts/prepare_g1_evidence.py` | 1,528 total runs; 0 organic/positively tagged owner runs; 1,206 synthetic; 322 unknown; `verdict: unexercised`; `doc_lookup_instrumented: false` | No positive owner-use denominator in this index. Unknown origin is not proof of no use, no demand, or zero friction. |
| `python3 scripts/prepare_h4_evidence.py --since 2026-08-13 --until 2026-09-15` | 9 observed events; 22 reachable runs; 7,844 total events; 1 candidate; `owner_verdict: null`; `synthetic_excluded: 0`; `verdict: needs_review` | Candidate extraction for the stated window, not production cleanliness or promotion acceptance. |
| `python3 -m teaagent.cli agent automation run --help` | Usage requires positional `automation_id`; optional `--root` | The command does not advertise name lookup. Help alone does not prove the full automation lifecycle. |
| `python3 -m teaagent.cli consensus request --help` | Exposes `--peer-storage`, `--consensus-storage`, and `--storage` | Explicit storage flags exist. This is not a fresh end-to-end consensus execution. |

Additional source checks:

- [Background argv construction](../../teaagent/ergonomics/background_run.py), `build_agent_run_command`: no forwarding of `--from-plan`, `--require-plan`, or `--skip-plan-check` in the reviewed implementation.
- [Memory CLI handler](../../teaagent/cli/_handlers/_memory.py), `memory_failures_auto_invalidate_command`: passes `args.root` directly to `MemoryAutoInvalidationConfig.from_workspace_config`; the [configuration loader](../../teaagent/memory/failure_card.py) uses Path division. This supports the previously recorded G32 failure; it is not a new reproduction.
- [Provider readiness](../../teaagent/preflight.py), `check_provider_connectivity`: remote-provider branch performs a DNS lookup, supporting the recorded fake-provider readiness problem.
- [MCP server](../../teaagent/mcp_server.py), `_call_tool`: inspected error containment around registry execution; the unknown-tool server termination is prior recorded runtime evidence.
- [Consensus handler](../../teaagent/cli/_handlers/_consensus.py), `_consensus_engine_from_args`: consumes the explicit peer/consensus storage arguments, using `None` when omitted. This narrows G34 to the default-storage mismatch rather than every CLI configuration.
- [Automation provenance](../../teaagent/automation_ticket.py), `automation_provenance_payload`: consumes `spec.name`. The name is not literally a write-only field.

Two read-only scouts investigated disjoint daily-path and held-surface evidence. Their reports were leads, not independent behavioral verification or a new panel verdict. Load-bearing claims were checked against repository sources and the command outputs above. In particular, the scout claim that the consensus parser lacks `--peer-storage` was rejected by actual CLI help. Source inspection was not relabeled as runtime proof. No new external-advisor consultation occurred in this review.

Not executed for the review: a new all-command sweep, the full test suite, live-provider proof, owner TUI acceptance, enforcement promotion, or a deletion/import-graph campaign. Earlier dogfood failures and fix receipts remain attributed to their dated work logs and the supplied conversation record.

## 3. Findings and corrected interpretations

### 3.1 Historical completion is not present-day journey acceptance

The H1 row in [Roadmap Status](../roadmap-status.md) says “Complete” / “High” for the setup-to-recovery journey and cites a June 10 snapshot of 628 acceptance tests. Later dogfood findings describe failures in setup, offline readiness, sandbox initialization, background execution, and machine-readable outputs.

**Conclusion:** the historical milestone can remain historical evidence, but it does not establish current end-to-end reliability. Proposed correction: distinguish implementation closure from current workflow verification. Do not infer that every interactive or prompt-mode path is broken, and do not reopen every completed milestone.

Cockpit claims also need surface-specific reading: the dead tabbed TUI implementation was deleted by owner decision; the primary TUI command loop and shared operational snapshot are different surfaces. Deleting the dead tabs does not prove the whole TUI unusable, nor does it prove the deleted tab capability delivered.

### 3.2 “All G1–G38 await adjudication” is stale

The later “Owner decisions” and re-dogfood sections in the [findings record](../work-log/dogfood-findings-2026-09-15.md) supersede its earlier blanket owner-only summary for G1–G22.

| Dogfood findings | Recorded disposition | Continuation rule |
| --- | --- | --- |
| G1–G10, G15/G16, G18, G21/G22 | Selected fixes recorded as implemented; fix and re-dogfood evidence cites `1611e71b`, with later pending-queue work citing `18d1feaa` / `025c353e` | Do not ask for the same original decisions again or claim every fix was re-proven by this review. |
| G11–G13 | Explicitly not selected | Preserve the owner decision; do not silently implement them as adjacent cleanup. |
| G14 | Quarantine under ADR-0043 | No revival merely because a defect is recorded. |
| G17 | Delete dead cockpit code | Preserve the deletion disposition; G19/G20 are moot for that deleted implementation. |
| G23–G38 | No per-item owner disposition in the reviewed decision table | Triage separately as proposed repairs, policy/UX choices, or held-surface evidence. |
| D1 | Deferred pending more evidence | False-positive classification remains owner-only. |

One residual must survive the “fixed” summary: the G4 re-dogfood record reports an unset orphan marker when a background process dies before `run_id` backfill. The path with a known `run_id` was verified. Do not generalize that proof to all launch/crash timing boundaries.

The execution plan and Horizon A/B drafts still describe September 12 entry conditions and no booked dogfood; later owner records booked the session and extended ADR-0031. The held-spec index still carries the older H4 expiry. These are documentation reconciliation candidates, not permission to alter gates.

### 3.3 H4 preparation is not H4 acceptance

The [roadmap provenance erratum](../roadmap-status.md) records **8 in-log approval receipts plus 1 orphan-sourced D1 candidate**, not “9 organic events.” The D1 receipt is preserved in `pending-1061f13779524cb9b8763a9a2d130e7d.jsonl`, associated with parent run `b15ffcfb361d4f438b04abb7041d6a67`. Missing provenance and `synthetic_excluded: 0` are not evidence of production cleanliness. Preserve the orphan as evidence; do not delete it to improve a count.

The documented “4/5 criteria prepared” is not four criteria passed. [ADR-0031](../adr/0031-shadow-mode-exit-criteria.md) still requires the 30-day production false-positive window, policy/RBAC test coverage, performance evidence, explicit owner sign-off, and validated rollback. The roadmap itself identifies `promotion_ready: false` as a hardcoded literal, not a readiness metric.

The local, gitignored `.teaagent/reviews/adr-0031/decision-packet.json` inspected during the review held an older extraction snapshot of 5 observed events / 13 reachable runs. It must not substitute for a current, criterion-by-criterion decision packet. Refresh and reconcile decision inputs when preparing the owner review; never overwrite an owner verdict with an agent classification.

### 3.4 Missing owner-use evidence is not zero demand

The owner-use extractor requires positive `origin: owner` evidence. The 322 unknown-origin rows cannot establish either use or disuse. The friction log has five closed owner entries and later agent verification on open hypotheses; absence of new owner-written entries does not establish continued frictionless operation.

The [M4 session record](../work-log/m4-dogfood-2026-09-15.md) explicitly labels the agent PTY run as partial: 0 tool calls, 0 file changes, and 0 new shadow receipts. B1 still requires real coding with owner-observed testimony. Another fake-provider completion is not a substitute.

### 3.5 The defect list is not an implementation queue

- **G37:** `automation run` explicitly takes an ID, and `name` is consumed elsewhere. Name lookup may be useful, but the review did not establish that it is a promised contract. Treat it as an ergonomics proposal until owner friction or a documented promise supports it.
- **G34:** default peer storage is inconsistent, but explicit storage flags exist and are consumed. Avoid the stronger claim that every CLI consensus configuration is nonfunctional. Consensus remains quarantined regardless.
- **G32 and G35:** a path-type crash and a protocol connection dying on one invalid request concern existing behavior. They should not be treated as new product features merely because they were discovered by dogfooding. Scheduling still needs the correct recorded DR-006 basis.
- **G28 and G38:** deciding default audit scope or implicit non-interactive setup defaults changes a user contract. Preserve these as explicit choices; do not invent broad defaults while “fixing errors.”

The archived later sweeps include empty IDs, argument errors, missing candidates, and timeouts of services intended to keep running. Those observations do not prove successful lifecycle execution. Stop repeating the same broad sweep; verify named workflows with valid inputs and observable postconditions.

## 4. Decision rationale, alternatives, and falsifiers

| Recommendation | Evidence / reason | Strongest counterargument or unknown | Decision and falsifier |
| --- | --- | --- | --- |
| Reconcile current status before selecting work | Later owner dispositions conflict with earlier owner-only summaries; active date references drift | Another review document can worsen corpus cost | Use this one dated record and existing entry points, not a new roadmap hierarchy. Reconciliation succeeds when the active sources distinguish the four states without contradictory gates. |
| Prioritize first-run and existing-contract reliability | G23/G24/G29/G30/G38 and G26/G31/G35 affect existing exposed paths | Actual owner workload and preferred provider remain unmeasured; not every edge case blocks daily use | Proposed bounded repairs, not a general rewrite. Change priority if owner evidence establishes a different failing path. |
| Keep owner observation distinct from agent proof | Positive owner-origin count is zero; PTY session did not exercise tools | Agent smoke tests still catch real bugs and should not be discarded | Keep both evidence classes; use scratch proofs for repairs and owner testimony for B1. Neither stands in for the other. |
| Keep expansion held | DR-006 and ADR-0043 already bind consensus/cloud/federated/other product expansion | A held surface may eventually be useful | Reconsider only on the named demand, governance, or owner-override trigger. A bug report alone does not ratify revival. |
| Do not start a broad thinning refactor | Current task is reliability and claim accuracy; new abstractions create more state boundaries | “Thin harness” is not an accurate code-size description | The operating-rule snapshot dated 2026-09-09 is 502 files / 124,984 LOC, 18 exemptions to the 800-line rule, and `runner/_core.py` at 1,054 lines; not remeasured here. Any later thinning proposal must show actual removal or a justified narrow seam, not a second framework. |

The strongest case for holding everything is that safety fixes landed and no positive owner-use denominator exists. That supports keeping expansion held; it does not prove known failures in existing advertised workflows are complete. The opposite extreme—repair every G-number—would revive non-goals and convert usability preferences into features without authority. The bounded middle is the recommendation, not an adopted scheduling decision.

## 5. Proposed work and acceptance criteria

All implementation rows below remain **Proposed**, not scheduled. Requirements describe observable outcomes; they do not authorize bypassing approval, plan, audit, or provider gates.

### R1 — Reconcile existing current-truth entry points

- **Scope:** Roadmap status, backlog, execution plan, held-spec index, and the findings summary, only where they conflict with later recorded decisions.
- **Keep:** historical implementation closure, dated evidence, owner no-change decisions, and existing source-of-truth ownership.
- **Acceptance:** current readers can distinguish resolved/dispositioned, unadjudicated, held, and owner-acceptance work; active H4 references use September 29; September 22 is never described as DR-006 authority expiry.
- **Authority:** documentation claim hygiene is separate from code scheduling. Recording this review is authorized; the factual reconciliation was applied 2026-09-16 under the standing keep-docs-current instruction (see §7). Proposed status-column wording — for example H1 confidence — is not adopted by the recording request.
- **Stop:** no new roadmap layer, automatic milestone promotion, or wholesale historical rewrite.

### R2 — First-run reliability

**Findings:** G23, G24, G29, G30, G38.

- **Acceptance scenario:** a fresh scratch Git workspace follows documented non-interactive setup, readiness, planning, and execution without unexpected prompts, unexplained plan failure, avoidable network dependence for the fake provider, or accidental sandbox fallback caused by owned runtime files.
- Required information missing in non-interactive mode produces an actionable error before partial setup; do not silently choose a credentialed provider or widen permissions.
- The offline fake-provider path does not request a fake API credential or depend on public DNS for provider readiness.
- Setup instructions explain how to satisfy the existing plan gate; bypassing the gate is not the recommended repair.
- Runtime-file handling preserves tracked configuration and unrelated user changes. No automatic stash, discard, or broad ignore rule is implied by the proposal.
- **Proof:** focused regression evidence plus an actual scratch CLI journey. A fake completion with zero tool activity proves only the setup/readiness route, not coding acceptance.
- **Gate:** record the applicable DR-006 basis per change. UX work is not automatically `governance-gap`; sandbox correctness needs its real safety invariant and appropriate review.

### R3 — Execution and machine-readable contracts

| Finding | Required observable result | Negative / regression boundary |
| --- | --- | --- |
| G31 background plan handling | A valid approved plan survives foreground-to-background dispatch; the worker produces an inspectable run and terminal outcome | Missing/invalid plans remain rejected; existing explicit options keep their semantics, with no blanket plan bypass. |
| G26 mixed run-list entries | Run collections contain valid run records; scratchpad metadata does not masquerade as another run | Check affected `runs list`, `session list`, and `agent status` consumers; avoid silently breaking documented output contracts. |
| G35 MCP error containment | An unknown tool request gets the contract-appropriate error; a subsequent valid request succeeds in the same connection | Registered-tool errors remain classified; malformed requests do not bypass ToolRegistry/governed execution or trigger tool effects. |

These are independent repair slices after shared contract decisions; they need no new queue, runner, or orchestration framework. Exact protocol error wording/codes must follow the implemented MCP contract rather than an unverified suggestion in the findings table.

### R4 — Owner-observed coding and workflow acceptance

- **Scenario:** one real coding task through the harness, with actual tool activity and file-level outcome verification; exercise approval/rejection, receipt inspection, and recovery as relevant, plus background/attach for the booked M4 scope.
- **Acceptance:** owner-written account of commands, expected/actual outcome, friction or explicit “no friction,” and referenced run/audit evidence. If a denied action occurs, prove no denied mutation and a recoverable terminal or paused state.
- **Boundary:** agents may prepare a scratch scenario and collect records; only the owner supplies B1 testimony, field-readability judgment, and D1 adjudication. Use only an authorized provider/credential scope.
- **Dependency:** repair blockers of the chosen workflow first, not every reported command. This is not permission for live EFX mutation proof.
- **Stop:** one meaningful workflow record is more useful than another purportedly exhaustive command sweep. Do not relabel agent/fixture runs as owner runs.

### R5 — Remaining active-surface repairs and optional improvements

Every remaining G23–G38 finding has a proposed disposition below; none is silently dropped.

| Finding | Proposed handling | Acceptance or decision required |
| --- | --- | --- |
| G27 missing MCP trust key | Follow core-path work with a bounded error-contract repair | Classified actionable failure without modifying trust or changing the owner-rejected G11 wrong-key semantics. |
| G28 default `audit verify` target | Resolve the CLI default contract before repair | Explicitly required target or a documented bounded default; no successful-looking result over nonexistent evidence. |
| G32 memory auto-invalidation root type | Narrow existing-contract repair | Valid workspace root reaches configured invalidation behavior without `str / str`; disabled configuration remains disabled. |
| G33 missing skill candidate | Narrow error-contract repair | Missing candidate produces an actionable classified result, not an uncaught exception; valid candidate lifecycle needs separate positive-path proof. |
| G36 unsupported automation schedule | Narrow input-error repair | Unsupported syntax is rejected without persisting invalid automation; no promise of cron support is added. |
| G25 release evidence progress | Lower-priority usability proposal | If admitted, communicate the existing expensive gates/progress without deleting, weakening, or silently skipping them. |
| G37 automation name lookup | Optional ergonomics proposal, not a confirmed contract defect | Owner need or a documented promise must justify name resolution; preserve unambiguous ID behavior and decide duplicate-name semantics first. |
| G34 consensus default storage | Held-surface disposition evidence | Do not revive consensus under a routine repair batch; owner-override or expiry disposition is required for reopening. |

Coverage: R2 owns G23/G24/G29/G30/G38; R3 owns G26/G31/G35; R5 records G25/G27/G28/G32/G33/G34/G36/G37. This accounts for all sixteen G23–G38 findings once.

## 6. Independent decision gates and held scope

| Lane | Current boundary | Next permitted decision / evidence |
| --- | --- | --- |
| H4 policy/RBAC promotion | Hold; [ADR-0031](../adr/0031-shadow-mode-exit-criteria.md) review is **2026-09-29** | All five criteria must be satisfied, including owner D1 classification/sign-off and the real production window. Otherwise an authorized extension with blocking evidence or reversion; no automatic mode flip. |
| EFX-001–003 live proof | Local guards are not provider-settlement proof | Owner supplies all six readiness items in the [live-proof procedure](../plans/efx-live-proof-procedure-2026-08-31.md): target, scoped credentials, exact tools/payloads/budget, expected effect/pre-state, reconciler/reversal, and interruption authorization where needed. |
| M4 background/cockpit | Existing co-maintainer carve-out only; B1 pending | Owner-observed workflow within the booked scope. It does not authorize cloud, gateway, or multi-tenant expansion. |
| Legacy consensus/federation/workflow surfaces | [ADR-0043](../adr/0043-legacy-competitive-surface-quarantine.md) quarantine; review **2026-12-09** | Promote only with recorded owner-override or delete using the ADR-0029 inventory/import-graph/recovery-anchor procedure. Expiry is a review trigger, not deletion authority by itself. |
| DR-006 falsifiers | Standing tripwires; no authority expiry on September 22 | Approximately September 22 is a calendar evidence-review reminder. The mechanical scheduling gate remains in force afterward. |
| Other held expansion | Existing H2 continuity, packaging/update, funded evaluation, and broader effect-framework triggers remain intact | No new cloud/distributed system, generic effect ledger/outbox, scheduler, supervisor, or second agent framework on this review's authority. |

EFX proof and H4 acceptance are separate decision lanes; one does not establish the other. Missing external receipts are unknown outcomes, not permission for blind retries. No live credentials or external effects were used for the review or its recording.

## 7. Candidate adoption and continuation ledger

| Item | Status at recording | Next action / owner |
| --- | --- | --- |
| Preserve this review and link it from existing entry points | Done 2026-09-16 | Indexed in `docs/INDEX.md` and `docs/roadmap-status.md`; links, G23–G38 coverage, and docs gates verified. |
| R1 broader status reconciliation | Applied 2026-09-16 (docs-only, under the standing keep-docs-current instruction) | Execution plan header/§1 date, Horizon A/B status banners, held-spec index H4 expiry rows, findings owner-only list, backlog Proposed row, H1 exit-evidence caveat. Not changed: H1 status/confidence columns and every gate or horizon status — owner calls. |
| R2 first-run repair batch | Implemented 2026-09-16 (owner "Yes for all"; `Gate: owner-override` for G23/G24/G30/G38, `Gate: governance-gap` for G29) | Landed with regression tests and an integrated scratch journey (headless `init` → committed scaffold → offline preflight → sandboxed `agent run`, worktree clean). Residual: `doctor model/project` wizards still EOF on non-TTY stdin (twins, out of scope). |
| R3 execution/output/protocol repairs | Implemented 2026-09-16 (`Gate: governance-gap`) | G31 plan flags forwarded (+`--allow-external-plan`), G26 arrays contain only runs, G35 `-32602` for unknown tools plus `-32603` containment for any other per-request failure, session alive. Residual: deprecated `ultrawork start` hand-rolled argv still lacks plan flags. |
| R4 owner-observed coding | Owner acceptance still pending | Owner performs/attests the real task; agents do not simulate the testimony. |
| R5 residual repair and improvement triage | Implemented 2026-09-16 except G34 (held): G27/G28/G32/G33/G36 under `Gate: governance-gap`, G25/G37 under `Gate: owner-override`; G27 twin (`mcp trust revoke`) fixed same day | Residuals: legacy unimported `agent_automation.py`, `automation promote/status` id-only, `release evidence` live progress not exercised (unit-proven only). |
| H4 enforcement, D1 verdict, EFX live proof, quarantine deletion | Existing gates unchanged | Named owner authorization and evidence, not this review, determine execution. |

### Next recommended action

Reconcile the active status summaries with the recorded dispositions, then seek/adopt the narrow first-run/background batch through the existing authority path. Execute and prove admitted repairs in scratch workspaces; follow with the real owner-observed coding session. Keep independent H4/EFX/disposition decisions explicit rather than blocking all local work behind one owner-only task.

### Do not do

- Do not treat the recording request as adoption of R1–R5 or as a `Gate: owner-override` for code.
- Do not repeat a broad panel or all-command sweep without new evidence or a specific question.
- Do not claim a lifecycle passed from help output, missing IDs, wrong arguments, clean error messages, or service timeouts.
- Do not turn unknown run provenance into either owner use or zero demand.
- Do not equate generated-doc freshness, test counts, `prepared`, or a hardcoded readiness flag with runtime/product acceptance.
- Do not delete orphan evidence, overwrite owner verdicts, change permission modes, use live credentials, or revive/delete held surfaces on this review's authority.
- Do not make a new abstraction, telemetry program, workflow engine, or durable governance layer merely to record this plan.

## 8. Record completeness and validation contract

The documentation-only recording is complete when this file preserves the evidence qualifications, corrected interpretations, all G23–G38 dispositions, bounded acceptance criteria, owner gates, counterarguments, unknowns, and next action; existing entry points link it as dated proposed work rather than adopted scheduling; and documentation verification runs against the final files.

Validation uses the existing generators and `bash scripts/verify_docs.sh`, plus a temporary in-memory check of local links and the sixteen-finding disposition coverage. No permanent test, new verifier, separate plan hierarchy, runtime scaffold, or acceptance gate is introduced for this record. Validation results belong to the recording task's delivery; the earlier review commands in section 2 remain separately attributed.
