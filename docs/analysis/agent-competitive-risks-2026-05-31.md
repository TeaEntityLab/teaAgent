# Competitive Risk Analysis — AI Coding Agent Market
# 2026-05-31

> Supersession note, 2026-06-05: This file is historical evidence. The
> competitive risk analysis was refreshed in
> `docs/analysis/competitor-signal-survey-2026-06-04.md`. For current risk
> register entries, use
> `docs/security/risk-register-and-threat-model-2026-06-02.md`.

**Purpose:** Map the competitive landscape's failure modes to teaagent's
strategic risks. Separate evidence from inference. Inform prioritization.

**Source:** `docs/analysis/agent-market-ux-survey-2026-05-31.md` (primary)
plus direct web research. See that document for full sourcing.

---

## Competitive Risk Register

### CR-1 — Budget Cap UX is a Retention Killer [HIGH]

**Evidence:** Claude Code's "Claude Is Dead" thread (841 upvotes, Sept 2025)
was triggered entirely by opaque weekly cap behavior. Users paying $200/mo
lost 4 days of work with no warning.

**Risk to teaagent:** `RunBudget` enforces caps. If the cap UX matches the
industry pattern (silent until exhaustion, then hard block), teaagent faces
the same trust collapse.

**What "good" looks like:**
- Show remaining budget at session start
- Warn at 50% and 80% consumed
- Offer "continue in read-only mode" at cap

**Severity if unaddressed:** High — budget surprises are the #1 community rage
trigger across all agents.

---

### CR-2 — Verification Bottleneck is the New Speed Problem [HIGH]

**Evidence:** Hacker News consensus (2026): "The core bottleneck is no longer
code generation speed but verification capacity." 93% of devs use AI; only 10%
see measurable productivity gain. The gap is verification overhead.

**Risk to teaagent:** If teaagent produces correct outputs but the operator
cannot easily verify *what changed and why*, adoption stalls at power users.
The audit log exists but is it operator-legible without `teaagent audit` CLI?

**What "good" looks like:**
- Post-run summary: N files changed, N lines added/removed, estimated cost
- Diff viewer in TUI (`teaagent show --last`)
- One-command undo with preview

**Severity if unaddressed:** High — this is the reason Aider retains loyalty
despite inferior UX: its git-commit-per-change makes verification trivial.

---

### CR-3 — Context Rot Erodes Trust on Long Tasks [HIGH]

**Evidence:** Memory degradation in 40–60% of long context windows
documented by multiple research sources (2026). Teams building four-layer
memory stacks to compensate.

**Risk to teaagent:** Long agent runs that forget earlier decisions, introduce
contradictory patterns, or repeat already-discussed approaches will generate
the same "the agent went off the rails" feedback that plagues Cursor and
Windsurf on complex tasks.

**What "good" looks like:**
- Persistent decision log (why was X implemented this way?)
- Cross-session scratchpad (checkpoint that survives `ctrl+c`)
- Proactive context compaction before the window fills

**Severity if unaddressed:** High — this is table stakes for 2026/2027.
`checkpoint.py` and `MemoryCatalog` are partial answers.

---

### CR-4 — OpenCode Is a Fast-Moving Open-Source Threat [HIGH]

**Evidence:** OpenCode: 164,373 GitHub stars (6.8x Roo Code's 24,137). MIT
license. LSP-aware. Rust/Tauri TUI. Growing fast.

**Risk to teaagent:** teaagent is also a terminal TUI with governance features.
If OpenCode adds governance-quality approval gates, teaagent's CLI/TUI
niche is directly threatened.

**Differentiator to defend:** teaagent's governance primitives (multi-sig,
audit chain, permission modes, plan-before-write) are not something a fast-
growing open-source project can replicate in quarters. The risk is that
teaagent doesn't *communicate* this advantage while OpenCode captures mindshare.

**Severity if unaddressed:** High for market positioning; Medium for technical
differentiation (the primitives are hard to copy quickly).

---

### CR-5 — Enterprise Security Gap is an Opportunity AND a Risk [HIGH]

**Evidence:**
- 88% of enterprise agent pilots fail to reach production
- 88% experienced security incidents
- Only 14.4% get full security/IT approval before production
- CISOs blocking Cursor for want of DLP plan, tenant isolation, SOC 2

**Opportunity:** teaagent's governance-first design is exactly what the 86%
of enterprises that can't ship agents need. The audit chain, permission modes,
and multi-sig approvals are enterprise prerequisites, not nice-to-haves.

**Risk:** If teaagent doesn't have SOC 2, tenant isolation docs, or a security
whitepaper, CISOs will pass over it even when the technical controls are
stronger than competitors.

**What "good" looks like:**
- Security whitepaper (teaagent as governance infrastructure)
- Tenant isolation docs (`docs/threat-model.md` expanded)
- Formal list of controls mapped to NIST AI Agent Standards

**Severity if unaddressed:** High opportunity cost — the enterprise market
is explicitly looking for what teaagent provides.

---

### CR-6 — Model Churn Creates Feature Inconsistency Risk [MEDIUM]

**Evidence:** GitHub Copilot released 50+ model variants in November 2025,
causing inconsistent suggestion quality that developers blamed on "degradation."
Windsurf experienced periods where "completions on Anthropic models are not
happening."

**Risk to teaagent:** Model-agnostic design means teaagent inherits model
quality variance. If teaagent's governance layer adds latency on top of
an already-slow model, the compound experience is worse than a tool with less
governance but faster responses.

**What "good" looks like:**
- Model capability matrix in docs (which models support which teaagent features)
- Per-model performance baselines in `benchmark.py`
- Fallback model configuration

**Severity if unaddressed:** Medium — teaagent's value is correctness and
governance, not raw speed. But speed matters for daily-use retention.

---

### CR-7 — Fork Risk from Open-Source Community [MEDIUM]

**Evidence:** Roo Code is a Cline fork that achieved 5.0/5.0 (vs Cline 4.0)
and a better issue-to-resolution ratio despite lower installs. Cline has 746
open issues — the fork captured quality reputation by fixing what the original
left open.

**Risk to teaagent:** If teaagent accumulates open issues in security-critical
paths (governance, approval, audit), a fork that fixes them wins community
trust even without feature parity.

**Mitigation:** Keep security-critical issue resolution time < 2 weeks.
Use the comprehensive audit process (already in place) to proactively find
and fix issues before community reports them.

**Severity if unaddressed:** Medium — the fork risk is real but slow-moving.

---

### CR-8 — "Capable but Reckless" Narrative Collapse [MEDIUM]

**Evidence:** Cursor's community narrative shifted from "fast and powerful" to
"capable but reckless" after the March 2026 silent revert incident. This
narrative is sticky and hard to reverse.

**Risk to teaagent:** A single high-profile incident where teaagent takes
an irreversible destructive action — even in a user-authorized mode — could
attach a "dangerous" narrative that follows the project.

**What "good" looks like:**
- Irreversible actions always require explicit confirmation (never implicit)
- `danger-full-access` mode requires a typed confirmation phrase
- Post-incident communication plan exists

**Severity if unaddressed:** Medium — teaagent's approval architecture makes
this less likely, but "less likely" is not "impossible."

---

### CR-9 — Onboarding Time > 15 Minutes Kills Adoption [MEDIUM]

**Evidence:** Pragmatic Engineer survey: onboarding friction (not capability)
now drives adoption and satisfaction. Tools with >15 minute setup show
significantly lower activation rates.

**Risk to teaagent:** If `teaagent` requires provider config, workspace setup,
permission mode selection, and memory catalog initialization before first use,
the onboarding friction is high.

**What "good" looks like:**
- `teaagent init` produces a working single-model session in < 2 minutes
- First run shows visible useful output (not an error or warning)
- `wizard.py` is the default first experience, not the optional path

**Severity if unaddressed:** Medium — this limits the growth ceiling.

---

## Competitive Advantage Map

These are teaagent's structural advantages that the market has validated as
the features developers and enterprises actually need in 2026:

| Advantage | Market validation | Current teaagent state |
|---|---|---|
| Governance-first (plan-before-write) | 57% of enterprises cite governance friction as prod-readiness blocker | ✅ Core feature |
| Audit chain (every action logged, hash-verified) | 33% of enterprises have no audit trail — compliance now law | ✅ Implemented |
| Permission modes (read-only → full access spectrum) | "Start supervised, expand over time" is the community ask | ✅ Implemented |
| Multi-sig approval (peer verification) | Agent identity + authorization = NIST priority area | ✅ Experimental |
| Undo / git sandbox | Invisible rewrites = #1 trust killer | ✅ `RunUndo`, `git_sandbox` |
| Model-agnostic (BYOK) | Vendor lock-in anxiety is real | ✅ Multiple adapters |
| Terminal-native (no IDE fork) | "Slot into existing workflow" = adoption driver | ✅ Core design |

**The gap is not the features — it is their legibility and discoverability.**
Developers need to understand these features exist, why they matter, and how
to activate them, without reading 70+ docs files.

---

## Risk Prioritization for Competitive Response

| Priority | Risk | Action |
|---|---|---|
| P0 | CR-2 (verification UX) | Post-run summary, diff view, one-command undo |
| P0 | CR-1 (budget cap UX) | Proactive budget warnings at 50%/80% |
| P1 | CR-3 (context rot) | Persistent decision log, proactive compaction |
| P1 | CR-5 (enterprise) | Security whitepaper, NIST control mapping |
| P2 | CR-4 (OpenCode) | Communicate governance primitives in README |
| P2 | CR-9 (onboarding) | `teaagent init` < 2 minutes to first useful output |
| P3 | CR-6 (model churn) | Model capability matrix |
| P3 | CR-7 (fork risk) | Issue resolution time < 2 weeks for security paths |
| P3 | CR-8 (reckless narrative) | Typed confirmation for `danger-full-access` |
