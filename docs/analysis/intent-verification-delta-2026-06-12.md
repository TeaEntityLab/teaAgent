# Intent Verification Delta - 2026-06-12

> **Claim class:** Dated verification delta (evidence + open work), not a new survey.
> **Scope:** TeaAgent at commit `e2e8317` (HEAD on 2026-06-12) plus an
> uncommitted working tree (generated docs, one type-annotation fix in
> `teaagent/runner/_core.py`).
> **Complements:** [Intent Reassessment and Governance Worklist (2026-06-11)](intent-reassessment-and-worklist-2026-06-11.md)
> and the [2026-06-10 System Critical Review Package](system-critical-review-2026-06-10-INDEX.md).
> **Method note:** Per WDH-001 and five prior review cycles, this pass does
> **not** re-survey competitors or re-derive the product thesis. It verifies
> what the prior cycle claimed, records what broke since, and updates the
> work list. Competitor facts remain dated 2026-06-11.

---

## 1. Intent, Re-Derived From Docs (confirmation, not re-litigation)

The docs at HEAD tell one consistent story, and it matches the 06-11 thesis:

- **README + product contract:** local-first, provider-agnostic, governance-
  first harness. The wedge is *provable trustworthiness* — permission matrix,
  hash-chained audit, bounded runs, human gates, "verify, don't trust."
- **Roadmap (fixed since 06-10):** horizons H2–H6 now carry honest
  "Partially fixed — shadow wired / unwired" statuses with evidence citations.
  The ENG-R2 roadmap⇄commit contradiction is resolved at HEAD.
- **The operative product question** (unchanged from 06-11): not "can it edit
  code?" but "can every material action be explained by a receipt?"

**Verdict:** intent is stable and docs-coherent. The live risk is no longer
*what* the project claims — it is whether the claim-enforcement machinery
actually holds the line day to day. See §3.

## 2. Verification of the 06-11 Ledger at HEAD

The [P0/P1 implementation ledger](../work-log/p0-p1-governance-implementation-ledger-2026-06-11.md)
marks W1–W9 done; commit `da49ad0` additionally landed W10–W12. Spot-verified
on 2026-06-12 (`.venv`, Python 3.12):

| Item | Ledger says | Verified 06-12 | Evidence |
| --- | --- | --- | --- |
| W1 docs evidence drift | done | **REGRESSED** | `docs/acceptance.md` claims `648 passed`; collection reports **646**; guard test `test_docs_acceptance_count_accuracy.py` FAILS at HEAD |
| W2 full collection | done | holds (venv) | acceptance collect 646 in 0.5 s; system `python3` still lacks `hypothesis` (documented constraint) |
| W3 governed first-hour e2e | done | holds | `--skip-plan-check` no longer present in `test_first_hour_e2e_flow.py`; runs with `--require-plan` |
| W5 control-loop map | done | holds | `docs/architecture/control-loop-ownership-map-2026-06-11.md` exists |
| W6 narrow runner boundary | done | holds | `teaagent/runner/_plan_validator.py` owns the write gate |
| W7 adversarial tests | done | holds | `tests/acceptance/test_adversarial_over_scope_behavior_flow.py` exists |
| W10 five-minute proof | done | exists, not re-run | `scripts/five-minute-proof-demo.sh` + `docs/demo/five-minute-proof.md` |
| W11 provider contract | done | exists | `docs/architecture/provider-agnostic-governance-contract.md` + `tests/test_governance_contract.py` (539 lines) |
| W12 claim traceability | done | exists | `docs/architecture/claim-to-test-traceability-matrix.md` + `tests/acceptance/test_claim_traceability.py` |
| WD-A shadow wiring | done (Sprint 2) | holds | policy/RBAC shadow code in `teaagent/governance/h4_integration.py`, `runner/_approval_manager.py`; roadmap rows cite WDA-002/003 |
| WD-F folding | done (676fd93) | holds | H4/H5 root modules folded into `teaagent/governance/`; old names only in `_compat_modules.py` |
| Docs consistency validator | passed 06-11 | **FAILS 06-12** | stale `docs/generated/docs-inventory.md` + the 648-vs-646 mismatch |

**Bottom line:** the 06-10 → 06-11 execution was real — the islands are
labeled, folded, and shadow-wired; the contradiction is fixed; the eval gate
and traceability matrix exist. But the suite's own truth gate is red at HEAD,
one day after the cycle that built it.

## 3. Live Findings (new since 06-11)

### V1 — The drift gate failed open on the very next commit (P0)

Commit `e2e8317` (2026-06-12 00:05, authored via a *different* agent, Devin)
updated the acceptance count 643→648 with the note "verified," yet the guard
test fails locally (collection = 646) and `validate_docs_consistency.py`
errors. CI (`ci.yml`) does run this gate — so either the commit landed
without CI, or the authoring environment collects a different count.
Either way, **main is red on its own governance check right now.**

Why it matters: this is the exact failure class (status claim ≠ verifiable
state) that three review cycles and WD-B were built to kill. It recurred in
under 24 hours, through a second AI agent. The gate exists; the *enforcement
path* (branch protection / pre-merge requirement / agent-contribution rules)
does not.

### V2 — Evidence citation integrity (P0, small)

`docs/acceptance.md` cites `docs/generated/suite-summary.json, 2026-06-12` as
support for the 648 figure. The artifact actually says: smoke tier, 200
tests, generated 2026-06-10 at `676fd93`. A dated citation pointing at an
artifact that does not support the claim is worse than no citation — it
launders staleness as freshness. WDB-004 (suite-status freshness rule) is the
designed fix and is not yet enforcing.

### V3 — Shadow mode has no exit criteria on record

Policy/RBAC are shadow-wired (log, don't enforce). Roadmap next-gates point
at WDA-004/005, but nothing states *what evidence promotes shadow → enforce*
or *when shadow mode expires*. WDA-006 set the precedent (ADR with expiry
for consensus deferral); the same discipline should apply to shadow mode,
or "wired" quietly becomes the new "implemented but unwired."

### V4 — Multi-agent contribution surface is ungoverned

The repo is now edited by at least three agent harnesses (Claude Code
sessions, subagent lanes, Devin) plus the human owner. TeaAgent's *product*
is agent governance; its *own contribution path* has no agent-facing
contract (which gates must pass before commit, which claims an agent may
update, required trailers). V1 is the first observed casualty.

## 4. Socratic Questions for the Next Cycle

Numbered to continue the 06-11 list (which ended at Q15); these probe the
*new* state, not the old one:

16. If the drift gate can fail open on main, is it a gate or a dashboard?
    What technically prevents a red `validate_docs_consistency.py` from
    merging — and if the answer is "nothing," is that a one-line branch-
    protection fix or a process decision?
17. When two environments collect different test counts (648 vs 646), which
    one is canonical — and should the doc record a count at all, or a
    machine-readable artifact hash that CI regenerates?
18. What single piece of evidence would justify flipping policy/RBAC from
    shadow to enforce? Who decides, and where is that recorded?
19. If a second AI agent can commit a false "verified" claim, what is the
    minimum contribution contract for agents — and should TeaAgent dogfood
    its own approval/receipt machinery on its own repo?
20. The five-minute proof demo exists — when was it last actually run
    end-to-end, by someone other than its author, from a clean checkout?
21. Which of the 06-11 "Do Not Do" rules is closest to being violated today?
    (Candidate: "do not treat acceptance test count as quality by itself" —
    the count is now the most-churned governance artifact in the repo.)
22. Is the eval gate (W-D/WDD-001) red-able in practice — has CI ever gone
    red because of a seeded conversational regression, or only in fixture
    tests of the gate itself?

## 5. Competitor Cross-Check Stance

Per WDH-001 (binding, reaffirmed by five cycles): **no new competitor survey
this pass.** The 06-11 reassessment refreshed Claude Code, Codex, OpenCode,
Aider, Cline, Kiro, Devin, and OpenHands same-day; those facts remain
current-to-2026-06-11 and must be same-day re-verified before any external
use (claim-audit rules). Refresh triggers that *would* justify new competitor
work: (a) publishing WDD-002's public eval-gate doc, (b) the WS6-003
quarterly refresh, (c) a major competitor shipping a user-auditable eval
gate — which would erase COMP-2, TeaAgent's one benchmark-setting axis.

One new internal data point belongs in the competitor file when next
refreshed: TeaAgent's repo is itself now a multi-agent production
environment (V4), which is both a dogfooding opportunity and a credibility
risk if its own governance does not apply to itself.

## 6. Work List (delta items; supersede nothing)

| ID | P | Item | Acceptance gate |
| --- | --- | --- | --- |
| V1-a | P0 | Reconcile the acceptance count: root-cause 648 vs 646 (env-dependent collection vs wrong number), set the true value, make the guard pass | `test_docs_acceptance_count_accuracy.py` green; `validate_docs_consistency.py` green; root cause noted in commit |
| V1-b | P0 | Close the enforcement gap: make the docs gate blocking on the merge path (branch protection or required check), so a red gate cannot land on main | A seeded wrong-count commit is mechanically rejected; note in `docs/governance-compliance.md` |
| V2-a | P0 | Fix the suite-summary citation in `docs/acceptance.md`; implement WDB-004 freshness enforcement (claims citing artifacts must match artifact date/commit/scope) | Validator fails on a seeded stale-citation fixture |
| V2-b | P1 | Regenerate and commit `docs/generated/docs-inventory.md` (currently dirty + out of date) | Validator inventory check green |
| V3-a | P1 | Shadow-mode exit ADR: evidence required to promote policy/RBAC to enforce, with an expiry date for shadow status (mirror ADR 0029 discipline) | ADR merged; roadmap H4 row links it |
| V4-a | P1 | Agent contribution contract: a short doc + CI trailer check defining what any agent (Claude, Devin, subagent) must run/pass before committing, and which claim-bearing files require a passing gate in the same commit | Doc exists; CI check has a fixture test; next agent-authored commit complies |
| V4-b | P2 | Dogfood pilot: run one real TeaAgent-governed change against the TeaAgent repo itself and publish the receipt as demo evidence | Receipt bundle linked from `docs/demo/` |
| V5-a | P2 | Independent five-minute-proof run from a clean checkout (not by its author); record outcome and friction | Dated note; failures filed as bugs |
| V6-a | P2 | Eval-gate live-fire: seed a real conversational regression on a branch and confirm CI goes red end-to-end (Q22) | CI run link or local equivalent recorded |

Carry-forward (still open from prior backlogs, unchanged): WDC-001/002
stranger-test + three-concept onboarding (partially advanced by the
stranger-session pilot harness in `15aaeb1` — needs status check), WDH-002
external-user evidence, WDH-003 when-not-to-use page upkeep, WDA-005 update/
packaging proof, WDA-004 full release-profile wiring.

**Suggested order:** V1-a → V2-a/V2-b (same sitting, all are small) →
V1-b → V4-a → V3-a → the P2 proofs.

## 7. Second-Pass Review Addendum (2026-06-12, same morning)

A same-day re-review (claims-ledger method) corrected and updated §3/§6.
Where this addendum conflicts with §3–§6 above, the addendum wins.

### Corrections to findings

- **V1 corrected (worse than stated):** the drift gate did not first fail on
  `e2e8317` — it was already red at `da49ad0` itself. Measured by checkout:
  collection at `da49ad0` = **646**, while its committed doc said 643. The
  governance pass landed with its own gate red; Devin's `e2e8317` then wrote
  648 without adding any test (diff touches only `plan.py`, `run.py`,
  `docs/acceptance.md`). **True count at HEAD = 646.** Two consecutive
  commits carried wrong counts in opposite directions. CI execution status
  for `e2e8317` could not be verified from this machine (`gh` returned
  nothing); the local gate failure at committed HEAD stands regardless.
- **V3 remediated:** [ADR 0031](../adr/0031-shadow-mode-exit-criteria.md)
  (Proposed, expiry 2026-09-12) now defines shadow→enforce exit criteria and
  cites this doc's V3. Created by a parallel agent within minutes of this
  doc's first write. Status: Proposed — still needs human acceptance (its
  own criterion 4).
- **V4 evidenced live:** during this very review, a parallel agent staged
  changes to the working tree (ADR 0031, `docs/agent-contribution-contract.md`,
  `scripts/check_agent_contribution_contract.py`, CI gate step, the 648→646
  fix — and staged this file). The multi-agent contribution surface is not
  hypothetical; it is concurrent within a single morning.

### Verification of new governance tests (theater check)

`test_claim_traceability.py`, `test_adversarial_over_scope_behavior_flow.py`,
and `test_governance_contract.py`: **50 passed** at the current tree.
Assertions are substantive (referenced test files must exist; claims need an
evidence command or an explicit gap; adversarial cases drive the real
runner/gate path with a deterministic `FakeAdapter`, per the 06-11 doc's own
standard). Not test theater.

### Work-list status updates

| Item | Status after pass 2 |
| --- | --- |
| V1-a count reconciliation | **Done in working tree** (uncommitted): `docs/acceptance.md` = 646; guard test and `validate_docs_consistency.py` both green |
| V2-b inventory regeneration | Done in working tree |
| V3-a shadow exit ADR | Done as Proposed (ADR 0031); human acceptance still required |
| V4-a agent contribution contract | **Partial.** Doc + checker + CI step exist, but two gaps: (1) the gate is self-bypassable by any agent via a `Bypass-agent-contract:` trailer or `ALLOW_AGENT_CONTRACT_BYPASS=1` — it only emits a warning, which recreates the failure mode it guards against; (2) no fixture test exists (`tests/*agent_contribution*` is empty), so the V4-a acceptance gate is unmet |
| V1-b blocking merge path | Still open — the CI step exists in the working tree but bypass semantics and branch protection remain undecided (human decision) |
| V2-a citation freshness rule | Partially addressed (bad citation removed with the 646 fix); WDB-004 enforcement still not implemented |

### New required fixes from pass 2

| ID | P | Item | Acceptance gate |
| --- | --- | --- | --- |
| V4-c | P0 | Harden the contract gate: bypass must require a human-attributable mechanism (e.g., repo-owner-set env in CI config, not a commit trailer any agent can write); failure must be an error, not a warning | Seeded agent commit with a bypass trailer still fails in CI fixture |
| V4-d | P1 | Add fixture tests for `check_agent_contribution_contract.py` (compliant, non-compliant, bypass cases) | Tests exist and pass; non-compliant fixture turns the check red |
| V7-a | P1 | Commit hygiene for the current shared working tree: the staged multi-agent batch (ADR 0031, contract, count fix, this doc) needs one reviewed commit with passing gates, rather than accreting further | Single commit; `validate_docs_consistency.py` + count guard green at that commit |

### Third-pass notes (2026-06-12, later the same morning)

- **Critical catch (fixed):** the staged batch contained a half-finished
  rename in `teaagent/runner/_core.py` — line 691 referenced the removed
  `reason_code` local, raising `NameError` on the destructive-tool approval
  path, surfacing as `failed:system` instead of `pending_approval`.
  Isolated by running `test_destructive_tool_requires_exact_call_approval`
  against pure HEAD (passes) vs worktree (failed). Fixed to
  `exc_reason_code`, re-verified: P0 harness 11/11, smoke tier
  **200 passed / 1 skipped**, fix re-staged. The smoke tier caught a real
  regression on its first live use in a review — WDG-002 earned its keep.
- **V4-c/V4-d verified done** (not just claimed): bypass attempts are now
  CRITICAL errors that fail the gate immediately (inverted semantics);
  18 fixture tests pass; emergency override is human-only via CI config.
  The checker even rejects HEAD (`e2e8317`) retroactively.
- Residual nits: the `ci.yml` step comment still advertises the old
  self-service override (now a critical error) — stale comment, same drift
  class this repo fights; the checker hardcodes `python3` rather than the
  venv-preferring resolution the count guard uses, so local verdicts are
  interpreter-dependent; `-m smoke` selects zero tests (tiering is
  path-list-based via `scripts/run_test_tier.py` — the registered marker is
  unused and could mislead).
- Inventory churn: `docs/generated/docs-inventory.md` went stale twice in
  one morning from concurrent agent edits; regeneration should move into a
  pre-commit hook or the contract gate (extends WDB-004).

### Fourth-pass notes (2026-06-12)

First full acceptance-tier run since `e2e8317`: **645 passed, 1 failed** in
60.6 s. The failure is the flagship governed first-hour test
(`test_first_hour_setup_daily_plan_edit_undo`), red at HEAD itself —
isolated against worktree changes, my pass-3 fix, and Devin's diff (all
exonerated; Devin's plan-contract change extracts but never applies the
plan's permission mode, and his comment correctly says CLI wins).

- **V8 — Config silently clobbers explicit `--permission-mode` (P0 product
  bug).** Root cause chain: the test's `setup` writes
  `permission_mode = read-only` to workspace config; the config merge at
  `teaagent/cli/__init__.py:842` overwrites any arg whose value equals the
  built-in default; the built-in default is `prompt`, so an *explicitly
  passed* `--permission-mode prompt` is indistinguishable from "not passed"
  and gets demoted to `read-only` → the write is blocked → exit 1. Here it
  fails safe, but the same logic runs in the escalation direction: a config
  with `allow` silently overrides an explicit `--permission-mode prompt`.
  Fix sketch: argparse sentinel (None default) or explicit-flag tracking,
  then resolve config only for genuinely unset args; add an acceptance test
  asserting explicit CLI mode survives any config value, both directions.
- **Ledger integrity:** the 06-11 ledger recorded this test green, but Lane
  B (its owner) "closed after timeout" — the green record came from a
  pre-final tree. A verification log entry must cite the tree state it ran
  against, or it inherits the same drift class it guards against.
- **V5-a substantially closed:** ran `scripts/five-minute-proof-demo.sh`
  end-to-end from the current checkout — all six governance steps passed
  (plan-gate block exit 2, approval before mutation, exact-file edit,
  verification, complete receipt, journal undo). The proof path works while
  the first-hour path fails — the defect is config precedence, not the
  governance core. Independent stranger run (non-maintainer) still open.
- **V9 — repo hygiene:** the real repo carries 8 old stashes (one named
  "TeaAgent dirty stash before run test_task" — evidence that a past run
  stashed the actual repo) and stale agent branches (`cascade/*`, `codex/*`,
  ticket branches). Audit and prune; add a check that runs never target the
  harness repo itself unless explicitly intended.
- WDG-003 gap: the acceptance-tier run did not refresh
  `docs/generated/suite-summary.json` (still the 06-10 smoke artifact);
  the tier runner only emits the artifact for some path. Worth one look.

Updated work items: **V8-a** fix config-vs-explicit-flag precedence (P0,
security-relevant in the `allow` direction) → makes **V8-b** the first-hour
test green; **V9-a** stash/branch hygiene audit (P2); V5-a reduced to
"stranger run" only.

### Fifth-pass notes (2026-06-12) — correction of pass 4, rejection of the staged V8-a fix

This pass falsification-tested the V8 root cause and reviewed the staged
V8-a fix (`_sentinel.py` + changes to `cli/__init__.py`,
`_agent_parsers.py`, `execution.py`, `chat_agent.py`).

- **Pass-4 site correction (named the right bug class, wrong layer).**
  Probe-traced through the live test: `args.permission_mode` is still the
  explicit `prompt` after argparse AND after `apply_config_defaults` — the
  pass-4 blamed site (`cli/__init__.py:842`) never fires for this test (it
  reads the CWD config, which says prompt). The actual clobber is **layer 3**:
  `_require_provider_for_agent_commands` (`cli/__init__.py:302`) calls
  `apply_workspace_defaults_to_namespace(args, root=args.root)`, and
  `workspace_defaults.py:171` overwrites any arg whose value matches
  `DEFAULT_KEYS` — the same explicit-vs-default trap, third location.
  Probe evidence: post-parse `prompt` → post-config `prompt` →
  post-provider-hook `read-only`.
- **Staged V8-a fix: Request changes (rejected as-is).** Evidence: the
  flagship first-hour test STILL fails (payload still
  `permission_mode=read-only`); the fix patched two layers that were not
  the culprit and missed the one that is. It also introduced a regression:
  `from_root` now hard-disables config/profile permission-mode application
  (`profile_overrides['permission_mode'] = PROMPT` unconditionally), which
  breaks the previously-green
  `test_config_loader.py::test_chat_agent_config_from_root_applies_profile`.
  Additionally the parser conversion is incomplete (2 of 6 sites in
  `_agent_parsers.py`, 5 sites in `_ergonomics_parsers.py` still default to
  `PROMPT.value`), making config semantics inconsistent across subcommands.
- **There are THREE permission-mode precedence layers**, each with its own
  explicit-vs-default logic: (1) `apply_config_defaults` defaults-dict
  merge, (2) `apply_workspace_defaults_to_namespace` DEFAULT_KEYS check,
  (3) `ChatAgentConfig.from_root` kwargs check. Any fix that does not
  unify these will whack one mole and feed the others — demonstrated
  empirically by the staged fix. Note also: a sentinel default makes layer
  2's `current in (None,'',0,0.0,'prompt')` check stop applying config for
  genuinely-unset flags, so all three layers must become sentinel-aware
  together.
- **Revised V8-a design:** one resolution function
  (explicit CLI value > env > workspace config > built-in default),
  sentinel-tracked explicitness, called exactly once on the entry path;
  layers 1–3 delegate to it; bidirectional acceptance tests (explicit
  survives config in both demote and escalate directions; config applies
  when flag unset; profile application restored).
- Hygiene: `gh` CLI is absent on this machine — CI status for `e2e8317`
  is unverifiable locally, permanently. Docs inventory went stale a third
  time today (regenerated again); the pre-commit/hook automation item
  stands.

### Sixth-pass notes (2026-06-12) — V8 fixed and verified end-to-end

This pass reviewed the parallel agent's second V8 attempt, found three
remaining defects, fixed them, and verified everything green.

- **State on entry:** the parallel agent's revised fix had made the two
  failing tests green (real progress: sentinel unified into
  `workspace_defaults._UNSET`, `from_root` regression reverted,
  `DEFAULT_KEYS` removed from layer 3's override tuple). But three defects
  remained: (1) `apply_config_defaults` had been reverted to the original
  trap — **proven live by repro**: CWD config `{"permission_mode":
  "allow"}` + explicit `--permission-mode prompt` resolved to `allow`
  (the escalation direction); (2) 7 of 11 parser sites still defaulted to
  `'prompt'`, so config could neither apply when unset nor be
  distinguished from explicit; (3) dropping `DEFAULT_KEYS` from layer 3's
  tuple also silently killed config application for non-permission keys
  (e.g. configured `max_iterations` over a defaulted 10).
- **Fix applied (this session):** sentinel-aware merge in
  `apply_config_defaults` (`_UNSET` → config applies; concrete
  `permission_mode` → never overridden; other keys keep equals-default
  compat); same three-branch logic in
  `apply_workspace_defaults_to_namespace` with `DEFAULT_KEYS` compat
  restored for non-permission keys; all 9 prompt-default
  `--permission-mode` parser sites converted to `_UNSET` (the two
  intentional `READ_ONLY` defaults left untouched);
  `_finalize_permission_mode()` added in `main()` after all config layers
  so the sentinel can never leak into handlers; orphaned
  `cli/_sentinel.py` removed.
- **Resulting precedence (now enforced and tested):** explicit CLI value >
  workspace config (CWD config at layer 1, root config at the provider
  hook) > built-in default. Repro-verified in all three directions:
  explicit `prompt` survives config `allow` (escalation blocked); unset
  flag picks up config value; unset + empty config falls back to `prompt`
  with no sentinel leak.
- **Verification:** first-hour + config-loader + governance-compliance
  68 passed; smoke tier 200 passed; **full acceptance tier 646/646 —
  first fully green acceptance run in this review saga**; ruff clean;
  docs validator 0 errors. Small items (stale ci.yml bypass comment,
  checker interpreter resolution) were already fixed by the parallel
  agent between passes.
- **Still open after this pass:** V7-a (commit the staged batch — now
  genuinely ready), V1-b (branch protection, human/GitHub UI),
  WDG-003 suite-summary refresh gap, V9-a stash/branch hygiene,
  inventory-regeneration automation (went stale a fourth time today),
  WDC/WDH carry-forwards, V6-a eval-gate live-fire.

## 8. Maintenance

- This is a dated delta; fold its open items into the next package rather
  than letting it become a parallel backlog.
- The 06-10 package's ENG-R1 finding is now historical: islands were labeled,
  folded (WDF-002), and shadow-wired (WDA-002/003). Cite this doc, not the
  06-10 package, for current wiring status.
- Memory updated same day: `teaagent-review-package-2026-06-10` (marked
  executed), with this file recorded as the current verification anchor.
