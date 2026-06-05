# Competitive Positioning Plan — 2026-05-31

> Supersession note, 2026-06-05: This file is historical evidence. For current
> competitive analysis, use `docs/analysis/competitor-signal-survey-2026-06-04.md`
> and `docs/strategy/teaagent-product-principles-2026-06-04.md`. For active work,
> use `docs/plans/daily-driver-complete-work-plan-risk-roi-2026-06-04.md`.

**Status:** Reference document - not an active execution plan. Extract actionable items to backlog-priority.md as needed.

**Source:** `docs/analysis/agent-competitive-risks-2026-05-31.md` and
`docs/analysis/agent-market-ux-survey-2026-05-31.md`.

**Purpose:** Translate market research into concrete, ordered actions that
strengthen teaagent's differentiation and close the gaps that competitors
exploit. No code changes without Human Review.

---

## The Positioning Problem

teaagent has the right technical architecture for 2026:
- Governance-first, audit-first, permission-mode-enforced
- Multi-sig, plan-before-write, undo, git sandbox
- Model-agnostic, terminal-native, no IDE fork required

But the market doesn't know this. The README competes with tools that have
better marketing despite weaker controls. The evidence:
- 88% of enterprises had agent security incidents — and would value teaagent's
  controls — but 0% of that 88% has heard of teaagent's audit chain
- Claude Code dominates CLI agents at 70% share by being "good enough" plus
  low friction; teaagent is better governed but more complex to discover

**The strategic choice:** Be the governance infrastructure layer, not just
another coding agent.

---

## Strategic Positioning Statement

> TeaAgent is the AI coding agent harness for teams that cannot afford
> invisible, irreversible, or unaudited agent actions.
>
> Where other agents ask "how do I make the AI faster?", TeaAgent asks
> "how do I make the AI safe enough to run on your codebase?"

---

## Plan CP-1 — README Rewrite for Governance-First Narrative [P0]

**Problem:** The current README likely leads with features and capabilities.
The market data shows that developers and CISOs choose tools based on trust
and governance, not benchmark scores.

**Target reader personas (2026):**
1. Senior developer — "I want AI assistance that respects my workflow and
   doesn't break things I didn't ask it to touch."
2. Engineering manager — "I need to know what the AI did, what it cost, and
   how to undo it."
3. CISO / security team — "I need audit trail, permission controls, and a
   security posture doc before my team can use this."

**README structure (proposed):**
```markdown
# TeaAgent — AI Coding Agent with Governance First

> The agent asks before it acts. Every action is logged. Everything is undoable.

## Why TeaAgent?

[3-line problem statement targeting the verification bottleneck]

## What Makes It Different

| | TeaAgent | Most agents |
|---|---|---|
| Permission gates | ✅ Prompt/read-only/full spectrum | ❌ Binary or none |
| Audit trail | ✅ Hash-verified, tamper-evident | ❌ Chat history |
| Undo | ✅ `teaagent undo --last` | ❌ Manual git revert |
| Cost cap | ✅ Configurable hard limit | ❌ Surprise bills |
| Model-agnostic | ✅ Claude, GPT, Ollama, etc. | ❌ Vendor locked |

## Get Started (< 2 minutes)
[teaagent init walkthrough]
```

**Acceptance criteria:**
- README answers all three persona questions in the first screen
- Governance table is in the top half of the README
- Time to comprehension ("what is this?") < 30 seconds for a new visitor

---

## Plan CP-2 — Security Whitepaper for Enterprise Evaluation [P1]

**Problem:** 86% of enterprises that want to adopt coding agents can't because
they lack governance documentation. teaagent has the controls; it lacks the
artifact that CISOs can put in front of their risk committee.

**Document:** `docs/security-whitepaper.md`

**Contents:**
1. Executive summary (1 page): teaagent's governance model in business terms
2. Control catalog: permission modes, audit chain, multi-sig, sandboxes
3. NIST AI Agent Standards mapping (see `agent-enterprise-security-risks`)
4. Data handling: what leaves the machine, under what conditions, who sees it
5. Deployment isolation: per-repo `.teaagent/`, no cross-workspace state
6. Incident response: undo, audit verify, forensic export
7. Known limitations: shared API keys, L3 plaintext (being fixed), experimental
   features

**Acceptance criteria:**
- Document exists and is reviewed by at least one person with security background
- Every control cited has a traceable code path or test
- "Known limitations" section is honest — no security theater

---

## Plan CP-3 — Aider-Style Commit-Per-Change Visibility [P1]

**Problem:** Aider retains community loyalty despite inferior UX because
its git-commit-per-change makes verification trivial. Every AI edit is a
reviewable, revertable commit.

**teaagent equivalent already exists** (`git_sandbox.py`, `RunUndo`). The gap
is that it's not surfaced prominently as a workflow.

**Proposed UX:**
After every agentic run that modifies files:
1. All workspace writes are staged in a git branch (`teaagent/run-<id>`)
2. Operator reviews the diff: `teaagent show --run <id> --diff`
3. Operator commits or discards: `teaagent commit --run <id>` or `teaagent undo --run <id>`
4. Committed runs show in `git log` with structured message:
   ```
   feat(teaagent): implement rate limiting for vote relay
   
   TeaAgent run: 2026-05-31-001
   Cost: $0.042 | Tools: 14 | Files: 3
   Approved by: john.lee@vm5.com
   Audit: .teaagent/runs/2026-05-31-001/audit.jsonl
   ```

**Acceptance criteria:**
- `teaagent show --diff` works without git knowledge
- Commit message includes run metadata
- `teaagent commit` is idempotent (safe to run twice)

---

## Plan CP-4 — OpenCode Gap Watch [P2]

**Problem:** OpenCode has 164K GitHub stars (6.8x Roo Code). If OpenCode adds
governance-quality approval gates, teaagent's CLI niche is directly threatened.

**Monitoring plan:**
- Check OpenCode GitHub releases monthly for governance-related features
  (permissions, audit, approval, undo)
- If OpenCode ships approval gates: accelerate CP-1 (README), CP-2 (whitepaper)
  and CP-3 (commit workflow) to widen the governance gap

**Trigger for escalation:** OpenCode issues or PRs mentioning "approval",
"audit", "permission", or "governance" with >50 votes.

---

## Plan CP-5 — Model Capability Matrix [P2]

**Problem:** Model churn (50+ variants in Nov 2025 for Copilot) is a
community frustration. Users don't know which teaagent features work with
which models.

**Document:** `docs/model-capability-matrix.md`

| Feature | Claude Sonnet 4.6 | Claude Haiku 4.5 | GPT-4o | Ollama |
|---|---|---|---|---|
| Extended thinking / reasoning | ✅ | ❌ | ⚠️ Partial | ⚠️ Model-dependent |
| Tool use | ✅ | ✅ | ✅ | ⚠️ Model-dependent |
| Streaming | ✅ | ✅ | ✅ | ✅ |
| Multi-sig approval | ✅ | ✅ | ✅ | ✅ |
| Cost tracking | ✅ | ✅ | ✅ | ❌ No billing |

**Acceptance criteria:**
- Matrix exists and is updated with each provider adapter change
- README links to the matrix

---

## Plan CP-6 — Community Presence / Developer Relations [P3]

**Problem:** teaagent's governance-first positioning is the 2026 differentiator
— but it can't win if developers don't know it exists. Aider maintains presence
via the developer's personal blog and Reddit engagement. OpenCode built
164K stars before being widely known in the press.

**Channels to consider:**
1. r/LocalLLaMA — post benchmark comparisons on governance: "I compared 5 agents
   on trust and reversibility, not just speed"
2. Hacker News — "Show HN: AI coding agent that governance teams can approve"
3. GitHub — respond to OpenCode/Cline/Aider issues that mention "audit" or
   "permissions" with "teaagent does this natively"
4. Dev.to / blog — post the UX survey research (this document's parent) as
   a developer-facing article

**Acceptance criteria:** This is a process, not a binary. Track: GitHub stars
per month, mentions in Reddit agent comparison threads, HN upvotes on launch post.

---

## Prioritized Action Summary

| Priority | Plan | Owner dependency | Timeline |
|---|---|---|---|
| P0 | CP-1 (README rewrite) | Copywriting + governance knowledge | 3 days |
| P0 | UX1.1 (post-run summary) — from ux-improvement-roadmap | Engineering | 3 days |
| P1 | CP-2 (security whitepaper) | Security review | 1 week |
| P1 | CP-3 (commit-per-change UX) | Engineering | 1 week |
| P1 | UX3.1 (init < 2 min) | Engineering | 1 week |
| P2 | CP-4 (OpenCode watch) | Ongoing monitoring | Monthly |
| P2 | CP-5 (model matrix) | Documentation | 2 days |
| P3 | CP-6 (community) | Marketing / DRel | Ongoing |
