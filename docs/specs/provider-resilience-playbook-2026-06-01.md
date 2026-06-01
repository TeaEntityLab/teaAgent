# Provider Resilience Playbook
# 2026-06-01

**Fills:** Gap **F-ECO-009** — *"add provider-resilience acceptance: detect outage,
suggest fallback, preserve permission mode and audit lineage, and avoid silently using a
more dangerous model/tool profile."*

**Grounding (current state, verified).**
- **`teaagent/model_routing.py`** (295 lines): `route_model(task, provider, model)` →
  `ModelRoute{category, provider, model, reason, complexity, estimated_tokens}`. This is
  **task-based selection**, not resilience — there is no outage detection, retry, or
  model fallback here.
- **`teaagent/model_capabilities.py`** (198): `build_model_capability_table`,
  `explain_route` — capability metadata exists.
- **`teaagent/external_backends.py`** (634): a `FallbackKnowledgeBackend{primary,
  fallback}` exists (line 270) with a `fallback_used` flag — **but this is for
  knowledge/RAG backends, not the LLM model itself.**
- **`teaagent/llm/_config.py:128`** `available_providers()` — provider list.

**Key finding:** teaagent has **fallback for knowledge backends** but **no fallback for
the LLM provider/model**. If the active model provider has an outage, mid-run, there is
no detect→fallback→preserve-governance path. That is precisely F-ECO-009.

---

## The resilience contract

When a provider degrades or fails, teaagent must: **detect → classify → fallback (or
fail clearly) → preserve governance → record**. Crucially, fallback must **never widen
risk** (a cheaper/weaker model must not come with a more permissive tool profile).

### 1. Detect

| Signal | Source | Classify as |
|--------|--------|-------------|
| HTTP 429 / rate-limit | adapter error | throttled |
| HTTP 5xx / timeout | adapter error | outage |
| auth/401 | adapter error | credential |
| budget cap hit | `RunBudget` / `_assert_cost_budget` | budget (not a provider fault) |
| capability mismatch | `model_capabilities` | misroute |

### 2. Fallback policy (`ModelFallbackPolicy` — to add)

Mirror the existing `FallbackKnowledgeBackend{primary, fallback}` pattern at the LLM
layer:

```
ModelFallbackPolicy
├── primary:   provider/model
├── fallbacks: [provider/model, …]   # ordered, capability-compatible
├── on:        [throttled, outage]   # which classes trigger fallback
└── preserve:  permission_mode, allow_destructive, audit lineage  # INVARIANT
```

- Fallbacks must be **capability-compatible** (use `model_capabilities` to reject a
  fallback that can't do the task's `category`).
- `fallback_used: true` is recorded on the `RunResult`/run summary (mirroring the
  knowledge backend's `fallback_used`).

### 3. Preserve governance (the safety invariant)

- Permission mode and `allow_destructive` are **carried unchanged** to the fallback.
- Audit lineage continues on the **same run_id** with a `provider_fallback` event
  (from→to, reason). No new ungoverned run is spawned.
- A fallback to a model with broader default tool access does **not** expand the tool
  profile — the run's existing profile is authoritative.

### 4. Fail clearly when no fallback applies

- Budget hit → the existing budget-prompt path (`_budget_prompt_handler`), not a model
  swap.
- No compatible fallback → fail with a clear, audited error and the partial run's
  evidence bundle (EVB) — never a silent hang or a silent downgrade.

---

## Operator surface

- `daily` / cockpit shows current provider health and whether a fallback is active.
- A `provider_fallback` line appears in the run summary and the evidence bundle.
- `teaagent doctor` / `modelProviders` can probe provider reachability before a run.

---

## Acceptance

- `test_provider_outage_triggers_fallback`: simulated 5xx on primary ⇒ next configured
  fallback used; `fallback_used=true` recorded.
- `test_fallback_preserves_permission_mode`: fallback run keeps the original mode +
  `allow_destructive`; an audit event records from→to.
- `test_fallback_capability_compatible`: an incompatible fallback is skipped, not used.
- `test_no_silent_downgrade`: fallback never widens the tool profile.
- `test_budget_hit_is_not_fallback`: budget exhaustion routes to the budget prompt, not
  a model swap.
- `test_no_fallback_fails_clearly`: no compatible fallback ⇒ audited error + evidence
  bundle, no hang.

## Open decisions

- **DQ-PROV-1:** Is the fallback list operator-configured per workspace, or derived
  automatically from `model_capabilities`? Recommendation: explicit list, validated
  against the capability table.
- **DQ-PROV-2:** Should mid-run fallback re-issue the last turn or resume from the next
  step? Recommendation: re-issue the failed turn (idempotent), since tool side-effects
  before failure are already audited.

## Non-goals

- Not multi-provider load balancing or cost arbitrage routing — this is *resilience*
  (stay alive + safe under failure), not optimization.
- Not automatic credential rotation (that's an ops/secret concern).

## Cross-references

- Cost/budget truth: `daily-driver-hardening-plan-2026-06-01.md` P1-1 (real cost).
- Governance invariant: `permission-mode-risk-decision-table-2026-06-01.md`.
- Failure evidence: `run-evidence-bundle-spec-2026-06-01.md`.
- Pattern reused: `FallbackKnowledgeBackend` in `teaagent/external_backends.py:270`.
</content>
