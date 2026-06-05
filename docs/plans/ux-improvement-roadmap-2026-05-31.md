# UX Improvement Roadmap — Community-Validated Gaps
# 2026-05-31

> Supersession note, 2026-06-05: This file is historical evidence. The UX
> items described here were absorbed into the P0-A (TUI/CLI parity), P0-B
> (cost/budget truth), P0-C (undo/recovery), and P1-D (onboarding) workstreams.
> For current UX work status, use `docs/daily-driver-current-status.md`. For
> the complete prioritization, use
> `docs/plans/daily-driver-complete-work-plan-risk-roi-2026-06-04.md`.

**Status:** Reference document - not an active execution plan. Extract actionable items to backlog-priority.md as needed.

**Source:** `docs/analysis/agent-market-ux-survey-2026-05-31.md` and
`docs/analysis/agent-competitive-risks-2026-05-31.md`.

**Principle:** Every item below is validated by community frustration patterns
across 3+ agents. These are not hypothetical UX improvements — they are the
features developers explicitly ask for and competitors fail to deliver.

---

## UX Horizon 1 — Trust & Verification (P0 — 1–2 Weeks)

### UX1.1 — Post-Run Summary (Verification Bottleneck Fix)

**Problem:** After a teaagent run, the operator cannot easily answer:
"What changed? How much did it cost? Is it safe to commit?"

**Evidence:** "The core bottleneck is no longer code generation speed but
verification capacity." (HN 2026). Aider retains loyalty because git-commit-
per-change makes this trivially answerable.

**Implementation:**
At the end of every `AgentRunner.run()`, emit a structured summary:
```
Run summary:
  Tools called:    14 (12 read, 2 write)
  Files changed:   3 (workspace_write_file × 2, workspace_delete_file × 1)
  Cost:            $0.042 (12,400 tokens)
  Budget remaining: $4.96 / $5.00
  Audit log:       .teaagent/runs/2026-05-31-001/audit.jsonl
  Undo:            teaagent undo --run 2026-05-31-001
```

**Acceptance criteria:**
- Run summary is always emitted at session end (non-interactive and TUI)
- `--no-summary` flag suppresses it
- Summary includes: files changed, cost, undo command

---

### UX1.2 — Proactive Budget Warnings (Cap Surprise Fix)

**Problem:** Budget exhaustion is communicated only at the point of failure.
Developers paying for subscriptions hit limits unexpectedly mid-session.

**Evidence:** Claude Code "Claude Is Dead" thread (841 upvotes). Users "hit
the limit on Wednesday, week resets Sunday — four lost work days."

**Implementation:**
In `AgentRunner._assert_cost_budget()` or a new `BudgetMonitor` hook:
- Emit a TUI/CLI warning at 50% budget consumed
- Emit a warning at 80% budget consumed
- At 90%: prompt "Budget at 90%. Continue? (y/n)"
- At 100%: offer "Switch to read-only mode for the remaining session?"

**Acceptance criteria:**
- `pytest tests/test_budget_warnings.py` — trigger at 50%, 80%, 90%, 100%
- TUI shows a persistent budget status line during agentic runs
- Budget warning is in the post-run summary even if not triggered mid-session

---

### UX1.3 — One-Command Undo with Diff Preview

**Problem:** `RunUndo` exists but the UX path from "something went wrong" to
"I've reverted it" is unclear. Cursor's silent reversal incident shows that
invisible undo is worse than no undo.

**Evidence:** Invisible rewrites cited as the #1 reason developers stop trusting
agents. Aider: "every edit is a commit you can review, revert, or cherry-pick."

**Implementation:**
```
teaagent undo --run <run-id> --preview   # Show what will be reverted
teaagent undo --run <run-id>             # Execute undo
teaagent undo --last                     # Undo most recent run
```
The `--preview` flag shows a unified diff of what will be restored.

**Acceptance criteria:**
- `teaagent undo --last --preview` shows a readable diff without executing
- `teaagent undo --last` reverts all workspace writes from the last run
- Post-run summary includes the undo command for that run

---

## UX Horizon 2 — Memory & Context (P1 — 2–4 Weeks)

### UX2.1 — Persistent Decision Log

**Problem:** Context rot — agents forget "why code looks a certain way" across
sessions, introducing contradictory patterns and re-discussing already-settled
decisions.

**Evidence:** Teams shipping fastest in 2026 use "decision memory" as layer 2
of a four-layer memory stack. Without it, agents re-derive architecture every
session.

**Implementation:**
A lightweight `DecisionLog` stored in `.teaagent/decisions.md` (human-readable):
```markdown
## 2026-05-31
**Decision:** Use JSONL for audit log, not SQLite
**Reason:** Single-writer per workspace; SQLite requires migration for multi-host
**Do not reverse without:** Reading ADR 0008
```

Injected into the agent's system prompt at session start (as compressed summary).
Operator can append decisions manually or the agent can propose new entries.

**Acceptance criteria:**
- `teaagent memory decisions list` shows all logged decisions
- `teaagent memory decisions add "..."` appends a new entry
- System prompt includes the 10 most recent decisions (truncated for tokens)

---

### UX2.2 — Proactive Context Compaction Warning

**Problem:** Transformer attention degrades in the middle 40–60% of long
context windows. No tool currently warns the operator before this happens.

**Evidence:** "Bigger context windows stopped helping" (ZenCoder 2026). Context
rot defined as a named failure mode with dedicated research literature.

**Implementation:**
In `AgentRunner.run()`, track context window usage:
- At 60% of context budget: "Context is filling up. Consider `/compact` or
  starting a new session with summary."
- Offer `/compact` as a one-command summary-and-continue

**Acceptance criteria:**
- Compaction warning triggers at configurable threshold (default 60%)
- `/compact` summarizes conversation history and replaces it with a compressed
  version, preserving key decisions

---

### UX2.3 — Cross-Session Scratchpad

**Problem:** When a session is interrupted (ctrl+c, timeout, crash), the
agent's in-progress context is lost. The next session has no memory of what
was being worked on.

**Evidence:** "Every session, the agent starts contradicting earlier decisions."
checkpoint.py exists but its UX path is unclear.

**Implementation:**
On session end (including abnormal termination), write a structured scratchpad:
```json
{
  "last_goal": "Implement rate limiting for the vote relay",
  "progress": "Completed: TokenRateLimiter class. Remaining: wire into server init.",
  "open_questions": ["Should the rate limit be per-IP or per-token?"],
  "next_step": "Add rate_limiter parameter to VoteRelayServer.__init__"
}
```
On session start: "Found scratchpad from previous session. Resume? (y/n)"

**Acceptance criteria:**
- Scratchpad is written on clean exit, ctrl+c, and crash (via atexit handler)
- On next session start, scratchpad is offered for resumption
- `teaagent sessions list` shows recent sessions with their last goal

---

## UX Horizon 3 — Onboarding & First-Run (P1 — 2–4 Weeks)

### UX3.1 — `teaagent init` < 2 Minutes to First Useful Output

**Problem:** Tools with >15 minute setup show significantly lower activation.
If `teaagent` requires provider config, workspace setup, permission selection,
and memory init before first use, many developers won't get there.

**Evidence:** "The fastest-growing tool was the one that slotted cleanly into
existing habits." Claude Code +58 NPS attributed partly to zero-friction start.

**Implementation:**
```
$ teaagent init
✓ Detected git repo at /Users/you/myproject
? Which AI provider? [Claude (recommended)] / OpenAI / Local (Ollama)
? Permission mode? [Prompt for each action (safe)] / Read-only / Full auto

✓ Config written to .teaagent/config.toml
✓ Ready. Try: teaagent "What does this codebase do?"
```

**Acceptance criteria:**
- `teaagent init` completes in < 2 minutes with guided prompts
- After init, `teaagent "hello"` produces a useful response without further setup
- Init path is the documented first step in README.md

---

### UX3.2 — First-Run Orientation Message

**Problem:** New users don't know what teaagent's governance features are or
why they matter. The value of approval modes, audit logs, and undo is lost if
users never discover them.

**Evidence:** "Governance-first is the 2026 differentiator — but only if users
know it exists." Cursor users who discovered `--skip-agent-review` only after
losing work; Claude Code users who didn't know about permission modes.

**Implementation:**
On first run (detected by absence of `.teaagent/`):
```
Welcome to TeaAgent!

You're protected by:
  ✓ Approval gates  — teaagent asks before any write or delete
  ✓ Audit log       — every action recorded (.teaagent/runs/)
  ✓ Undo            — teaagent undo --last reverses any run
  ✓ Budget cap      — set in config to prevent surprise costs

Run `teaagent --help` or `teaagent docs` to learn more.
```

**Acceptance criteria:**
- First-run message is shown exactly once (gated by `.teaagent/welcomed` file)
- Message is skippable with `--quiet`
- Message links to the relevant docs

---

## UX Horizon 4 — Enterprise & Team (P2 — 1–2 Months)

### UX4.1 — Security Whitepaper / Control Mapping

**Problem:** Enterprise CISOs block agent adoption for want of DLP plan, tenant
isolation docs, and vendor security posture. 88% of enterprises experienced
agent security incidents. Only 14.4% ship to production with full IT approval.

**Evidence:** Cursor enterprise blocks. NIST AI Agent Standards Initiative.
teaagent has the controls — they are not documented in a form CISOs consume.

**Implementation:**
Create `docs/security-whitepaper.md`:
- teaagent control catalog (permission modes, multi-sig, audit chain, sandboxes)
- NIST AI Agent Standards Initiative mapping
- Data handling (what leaves the local machine, under what conditions)
- Deployment isolation guide (per-repo `.teaagent/`, no shared state)
- Incident response guidance

**Acceptance criteria:**
- Security whitepaper exists and is linked from README.md
- Every control in the whitepaper is traceable to code (`docs/threat-model.md`)
- NIST control mapping covers identity, authorization, and security sections

---

### UX4.2 — Team Memory / Inherited Context

**Problem:** When multiple engineers use teaagent on the same codebase, each
starts fresh. The agent re-derives architecture, coding conventions, and team
decisions every session.

**Evidence:** "Teams building four-layer memory stacks — team memory lets
onboarding agents inherit what colleagues learned." Not addressed by any major
tool yet. First-mover opportunity.

**Implementation:**
Shared `.teaagent/team-memory.md` (committed to the repo):
- Architecture decisions (mirrors `docs/adr/`)
- Coding conventions (auto-derived from `.editorconfig`, `pyproject.toml`)
- Team-specific patterns ("We always use dataclasses, never TypedDict")
- Known gotchas ("The approval_manager has two implementations — see ADR 002")

Injected into system prompt when present. Operator curates manually or via
`teaagent memory team add "..."`.

**Acceptance criteria:**
- `.teaagent/team-memory.md` is auto-created by `teaagent init` with a template
- `teaagent memory team list` shows current entries
- System prompt injection is token-budgeted (truncated at 2K tokens)

---

### UX4.3 — Cost Attribution Per Run / Per Task

**Problem:** As agent use scales to teams, cost tracking per task/feature/PR
becomes an infrastructure-procurement question. Reddit: "token burn, rework
cost, and fallback stacks" are the 2026 vocabulary.

**Evidence:** "The coding-agent market is becoming more like infrastructure
procurement." Aider users maintain spreadsheets for token burn per task type.

**Implementation:**
- Tag each run with optional `--label "feature:rate-limiting"` or `--pr 42`
- `teaagent cost report --last 30d` — cost by label, by day, by model
- `teaagent cost report --pr 42` — total cost for all runs tagged to that PR
- Export as CSV or JSON for team reporting

**Acceptance criteria:**
- `teaagent cost report` produces a table without requiring external tooling
- Labels are stored in run metadata and queryable
- Budget warnings in UX1.2 use the same label context

---

## UX Horizon 5 — Explainability (P2 — 1–2 Months)

### UX5.1 — "Why Did It Do That?" Tool-Decision Explainer

**Problem:** Audit logs record *what* happened but not *why* the model chose
a particular tool call. The verification bottleneck (CR-2) is partly a
reasoning-visibility problem.

**Evidence:** "Build in explainability from the start: log not just what the
agent did, but why." (Dev.to compliance audit guide 2026). NIST: log the
reasoning, not just the action.

**Implementation:**
When the model emits reasoning before a tool call (via extended thinking or
chain-of-thought), capture it in the audit event:
```json
{
  "event": "tool_call",
  "tool": "workspace_write_file",
  "reasoning": "The test file is missing an import for the new class...",
  "arguments": {...}
}
```
Surface in post-run summary and `teaagent audit show --run <id>`.

**Acceptance criteria:**
- `teaagent audit show --run <id> --with-reasoning` shows model reasoning per event
- Reasoning is optional (off for models that don't expose it)
- Stored reasoning is redacted at L0/L1 audit levels

---

### UX5.2 — Permission Explain Mode

**Problem:** When a tool call is blocked, the operator sees "Permission denied"
but not a legible explanation of *which rule* blocked it and *how to change it*.

**Evidence:** "Start supervised, expand over time" is the community ask. But
developers don't expand permissions because they don't understand what blocked
them or what the options are.

**Implementation:**
On permission denial, emit:
```
✗ Blocked: workspace_delete_file
  Rule:    Permission mode = read-only
  Why:     workspace_delete_file is destructive (delete action)
  Options:
    1. Approve once:    teaagent approve --call-id <id>
    2. Approve session: teaagent approve --tool workspace_delete_file --session
    3. Change mode:     teaagent config set permission_mode prompt
    4. Learn more:      teaagent docs permissions
```

**Acceptance criteria:**
- Every permission denial includes the rule, reason, and options
- `teaagent docs permissions` opens the relevant docs page
- `--quiet` suppresses the explanation (CI use)

---

## UX KPIs — Measurement Plan

| KPI | Baseline | Target | Measurement |
|---|---|---|---|
| Time to first useful output | Unknown | < 2 min | `teaagent init` timing |
| Post-run undo usage | 0% (feature unknown) | 5% of runs | Audit event count |
| Budget warning acknowledgment | N/A | >80% see warning before cap | Telemetry opt-in |
| Permission explain mode usage | N/A | Track denial + explain event ratio | Audit log |
| Session resumption rate | 0% | 20% of interrupted sessions | Scratchpad read event |

---

## Human Review Gates

| Plan | Gate reason |
|---|---|
| UX2.2 (context compaction) | Must not silently drop conversation history |
| UX4.2 (team memory in repo) | Team memory file should not contain secrets — needs `.gitignore` guidance |
| UX5.1 (reasoning in audit) | Reasoning may contain sensitive data — needs redaction policy before L0/L1 |
