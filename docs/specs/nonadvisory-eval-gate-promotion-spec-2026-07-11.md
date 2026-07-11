# Non-Advisory Eval Gate Promotion Spec (H5/M5)

> **Claim class:** Forward-looking specification (planned/held work — NOT current truth).
>
> **Status:** Preparation artifact for held item.
>
> **Date:** 2026-07-11
>
> **Trigger:** Owner request 2026-07-11 — forward-spec held/external roadmap items
> so future execution has pinned contracts and executable holds.
>
> **Scheduling gate (DR-006):** `governance-gap` preparation. Hold per
> `docs/work-log/roadmap-verification-2026-07-01.md` §Held/external: "H5
> non-advisory model/provider gate — needs live provider runs + owner"
> (M5 exit criteria in `docs/roadmap-status.md`).
>
> **Owns:** The evidence contract and mechanics for promoting the release
> eval gate's model-execution signal from advisory to blocking, and the
> release evidence bundle proof format.
>
> **Does not own:** Current-truth status (`docs/roadmap-status.md`), the hold,
> the gate implementation, `docs/analysis/eval-gate-design-2026-06-10.md`
> (prior design record).
>
> **Review trigger:** Owner decides to fund live provider regression runs, or
> a real model regression slips through and produces a friction entry.

## 1. Current verified state (2026-07-11, HEAD)

**The gate blocks on corpus failures today — "advisory" refers only to the
execution-quality signal.** Precisely:

- `run_release_eval_gate` (`teaagent/governance/release_eval.py:33-64`)
  registers the release corpus, runs it (simulated unless a `model_runner`
  is injected), and evaluates `ReleaseGate.run_and_evaluate`
  (`teaagent/governance/release_gate.py:251`).
- The **release profile** overrides the defaults: `required_success_rate=1.0`
  and critical categories `{prompt_regression, conversational,
  repo_map_benchmark}` (`release_eval.py:24-30`) — stricter than
  `create_default_gate_config`'s 0.9 (`release_gate.py:318-335`).
- Decision logic (`release_gate.py:145-249`): BLOCK on any critical failure
  (including *vacuously missing* critical categories — `:174-182`), BLOCK
  below required success rate, WARN/BLOCK on warnings per `allow_warnings`,
  else APPROVE.
- Execution disclosure (`release_gate.py:281-316`): a result is
  `simulated=True, advisory_only=True` unless **every** critical-category
  test result carries `metrics.execution_mode ∈ {real, fixture}` — note
  `fixture` counts as real execution by design (`:304`; the M5 deterministic
  repo-map fixture corpus is a real signal). When simulated, the note
  `EVAL_EXECUTION_ADVISORY_NOTE` (`:25-28`) is attached to
  `details.advisory_note` and prefixed to `format_gate_summary` output
  (`release_eval.py:75-80`).
- CI consumption: `.github/workflows/release.yml:36-37` runs
  `scripts/run_release_eval_gate.py --root . --report …`; the script exits
  non-zero via `should_block_release` (`release_eval.py:71-72`,
  BLOCK → True).
- Coverage: approve/block/warn, vacuous-category guard, simulated
  disclosure, real-execution approval (`tests/test_release_gate.py`,
  `tests/test_release_eval_gate.py`, `tests/test_eval_executor.py`).

So the *held* piece is precisely: **there is no blocking signal derived from
live model/provider execution** — a model-quality regression that keeps the
deterministic corpus green cannot block a release, and nothing enforces
"blocking gates must not be simulated".

## 2. The hold and its gate

Live provider regression runs cost money, need credentials in CI, and their
flake profile can block releases spuriously. The owner has not funded them;
M5's exit criteria call for "non-advisory model/provider regression evidence
and release evidence bundle proof". Until the owner decides, the split
stands: corpus checks block, execution quality is advisory-and-disclosed.

## 3. Future contract

### 3.1 Live provider regression evidence (definition)

A **provider evidence run** for a (provider, model, route-role) triple is:

- N ≥ 3 executions of the release corpus's critical categories with the
  real `ModelRunner` (`teaagent/eval_suite.py:22` callable contract);
- fixed decoding parameters and a recorded seed policy (temperature 0 where
  the provider honors it; otherwise N is raised to 5 and majority scoring
  applies);
- per-run wall-clock and cost recorded; a **cost budget per gate run**
  (default cap: 200 cents, reusing the budget vocabulary of
  `daily_cost_cap_cents`) — exceeding the cap fails the evidence run as
  ERROR, never silently truncates;
- variance bound: a test is `unstable` when pass/fail flips across the N
  runs; unstable tests report as warnings, and >10% unstable tests fail the
  evidence run (flake gate before the release gate);
- an **offline-replay fallback**: every live run's transcripts are stored so
  the same evidence can be re-scored offline (`fixture` mode) when the
  provider is down — provider outage must degrade to fixture-replay, not to
  simulated.

### 3.2 The non-advisory release profile

Extend `ReleaseGateConfig` with `require_real_execution: bool = False`
(serialized in `to_dict`/`from_dict` with a False default so old reports
parse). Semantics, enforced in `run_and_evaluate` after
`_apply_execution_disclosure`:

- `require_real_execution=True` and `result.simulated=True` →
  `decision=BLOCK`, summary "blocked: execution evidence is simulated but
  the profile requires real execution", reason recorded in
  `details.block_reason='simulated_execution'`.
- The invariant becomes: **a blocking-grade approval is impossible from
  simulated execution** — `decision==APPROVE and advisory_only` cannot
  coexist under the non-advisory profile.
- The release profile builder (`build_release_gate_config`) flips the flag
  when the owner enables it via config (workspace-defaults key
  `release_eval_require_real`, visible in `teaagent doctor config`).

### 3.3 Release evidence bundle proof

`create_release_bundle` (`release_gate.py:360-404`) currently emits
`{suite, results, summary, generated_at}` in the file and returns
`{bundle_path, suite_id, test_count, result_count}`. The proof format adds
(additive-only): `bundle_sha256` (hash of the canonical JSON), `gate_result`
(the full `ReleaseGateResult.to_dict()`, which already carries
`simulated`/`advisory_only` — `release_gate.py:94-109`), and
`evidence_class: simulated|fixture|live`. The release checklist then cites
one artifact instead of three.

### 3.4 Escape hatch (DR-006-consistent)

A provider outage on release day must not force either a bad release or a
gate bypass-by-editing-CI. Escape hatch: `--allow-simulated-once` on
`scripts/run_release_eval_gate.py`, valid only with a dated owner-override
paragraph appended to the release notes and an `update…gate_overridden`
audit line in the evidence bundle. Silent bypasses stay impossible.

## 4. Executable specification

Tests live in `tests/test_release_gate_promotion_spec.py`.

| Contract clause | Test | Kind |
| --- | --- | --- |
| Release profile is strict: 1.0 success rate + 3 critical categories | `test_release_profile_is_stricter_than_default` | guards hold today — failure = the CI gate config silently loosened |
| BLOCK-while-simulated is possible today (corpus blocks, execution advisory) | `test_simulated_run_still_blocks_on_seeded_corpus_failure` | guards hold today |
| `advisory_only` ↔ `simulated` coupling | `test_advisory_flag_tracks_simulated_flag` | guards hold today |
| `fixture` execution mode counts as real | `test_fixture_execution_mode_counts_as_real` | guards hold today (M5 fixture-corpus design point) |
| Gate-result flags survive dict round-trip | `test_gate_result_roundtrip_preserves_disclosure_flags` | guards hold today (report consumers) |
| Bundle metadata + file keys (proof-format base) | `test_release_bundle_key_contract` | guards hold today |
| Non-advisory profile field | `test_nonadvisory_profile_field_activates` | activates on implementation (skipif until `require_real_execution` exists) |

Existing coverage (not duplicated): approve/block/warn paths, vacuous
critical category, simulated-note disclosure text, real-runner approval.

## 5. Promotion checklist

1. Owner funds live runs (decision recorded; DR-006 owner-override or
   friction-driven).
2. Implement §3.1 evidence runner + flake gate; store transcripts for
   replay.
3. Implement §3.2 flag + BLOCK-on-simulated semantics; activate
   `test_nonadvisory_profile_field_activates` (remove its skip guard) and
   add the adversarial test: simulated + require_real → BLOCK with
   `block_reason='simulated_execution'`.
4. Extend the bundle per §3.3; wire `bundle_sha256` into the release
   checklist.
5. Update `docs/roadmap-status.md` M5/H5 rows and this spec's status in the
   same commit; docs regen chain + validators green.

## 6. Risks and open questions

- **Flaky-model false blocks** are the promotion's main cost; the §3.1
  variance bound and fixture-replay fallback exist to price that in before
  the flip.
- **Cost runaway**: the per-gate cap fails closed (ERROR), because a gate
  that silently truncates its corpus is worse than a failed gate.
- **Two-tier truth window**: between funding live runs and flipping
  `require_real_execution`, both signals exist; `format_gate_summary`
  already prefixes the advisory note, which keeps the window honest.
- Open: should `fixture` remain "real" under the non-advisory profile, or
  should live-provider evidence be mandatory for the model-routed
  categories only? Default: fixture stays real for deterministic
  categories (repo-map), live required for `conversational` — decide at
  promotion with cost data in hand.
