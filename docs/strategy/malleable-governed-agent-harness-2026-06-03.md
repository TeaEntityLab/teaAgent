# Malleable Governed Agent Harness — 2026-06-03

## North Star

**Malleable workflows with receipts.**

TeaAgent lets users shape agent behavior as fluidly as a spreadsheet lets you reshape data -- while keeping an unforgeable, inspectable record of every capability used, every cost incurred, every gate passed, and every change made.

TeaAgent = Pi-like malleability + Codex-like operator safety + first-class evidence ledger.

This is not a compromise between freedom and safety. It is a design that refuses to treat them as opposing forces. The premise is simple: when every action is recorded and every tool is governed, users feel safe enough to make the system genuinely malleable. And when the system is genuinely malleable, users do not need to work around governance -- they work within it, because the receipts make their own life easier.

## Design Principles

### 1. Inspectability is a feature, not an overhead

Every capability, cost, approval decision, and undo path must be readable -- by the user, by an auditor, by an automated reconciliation script. If something happens and there is no record of it in a queryable form, it is a bug. This applies to tool calls, approval grants, token consumption, error states, and session lifecycle events alike.

RunStore is not just persistence. It is the system's memory. Audit is not just compliance. It is the user's ability to answer "what just happened?" without guesswork.

### 2. Safety gates must be adjustable, not removable

Permission modes (plan-only, ask, allow) define a spectrum, not a binary. The system ships with conservative defaults but exposes the knobs. A user who trusts a tool can widen its gate. A user who wants full lockdown can tighten it. The architecture must never assume a single safety profile fits everyone.

The gate itself is not negotiable. Tool calls pass through policy evaluation. Approvals are recorded. Undo paths are prepared before writes execute. These are invariants. What changes is where the bar sits.

### 3. Malleability means composable primitives, not monolithic features

A malleable harness is built from small, independently useful pieces that users can reconfigure. Skills are not plugins. They are prompt-plus-tool bundles that can be composed, layered, and versioned locally. Tools are registered through ToolRegistry with typed schemas. Runs can be suspended, resumed, forked, and replayed.

If a feature cannot be explained as a composition of existing primitives, it does not belong in the core harness -- it belongs in a skill or a recipe.

### 4. Cost transparency must be real-time and cumulative

Tokens, tool calls, wall-clock time, and budgets must be trackable at the call level and aggregatable at the session level. The cost tracker is not a post-hoc report. It is a live instrument that the user can inspect mid-run to decide whether to continue, pause, or fork.

Every run summary must answer: how much did this cost, what tools did it use, which gates did it pass, and what did it change.

### 5. Actionability over pager duty

When a gate blocks, the system must tell the user why and what they can do about it. Permission explain is not optional. A "denied" without context is a failure. The system should surface the matching policy rule, the tool's risk classification, and the available remediation paths (adjust mode, grant token, switch plan).

This principle extends beyond permissions. Error messages must include recovery steps. Budget caps must include the option to resume with a higher cap. Undo must include a preview of what will be reverted.

### 6. The harness is the platform, not the product

TeaAgent's value is what it enables users to build on top of it. The harness provides orchestration, governance, audit, and state management. The user provides skills, tools, policies, and workflows. This separation means the harness stays lean and the user's customizations stay portable.

Features that belong in userland stay in userland. The harness provides the primitives; the community provides the recipes.

## What "Malleable" Means

Malleability in TeaAgent means the user can reshape behavior across four dimensions without forking the harness:

**Skills.** Users write or install skill bundles that add new agent capabilities. A skill can inject system prompts, register tools, define approval defaults, and attach reference docs. Skills can be layered, overridden, and version-controlled alongside project code instead of living in a separate plugin registry.

**Permission profiles.** Users configure which tools require approval, which run silently, and which are blocked entirely. These profiles are checked into the project repo as policy-as-code files, not buried in a settings UI. Teams can review permission changes in the same PR review flow they already use for code changes.

**Tool registration.** Users add custom tools through the ToolRegistry with full typed schemas and risk classifications. A tool is just a Python function with metadata. If you can write a function, you can add a tool. No build step, no SDK, no separate process.

**Run lifecycle.** Users can start a session, suspend it to background, resume it later, fork a completed run to try an alternate path, or undo the last write and continue. Sessions are not fire-and-forget. They are interactive artifacts the user can engage with on their own schedule.

The goal is that when a user thinks "I wish the agent could do X differently," the answer is "write a skill" or "adjust a setting" -- not "submit a feature request."

## What "Receipts" Means

Receipts are the evidence ledger that makes every action accountable. They are not log files. They are structured, queryable, machine-readable records that compose into human-readable summaries.

**Tool call receipts.** Every tool invocation records: what tool was called, with what parameters, by which agent turn, at what cost, whether it required approval, who approved it (or what policy allowed it), what it returned, and how long it took. These are stored in the audit log and are available through the RunStore.

**Approval receipts.** Every approval gate records: what was requested, what policy rule matched, what risk classification was assigned, what mode was active, who approved or denied it, what token was used, and at what timestamp. Destructive tool approvals include the hash-anchored plan that preceded the call.

**Cost receipts.** Every run accumulates a cost ledger: total tokens (input + output), total tool calls, elapsed time, and per-tool cost breakdown. The cost tracker surfaces this incrementally during the run and commits it to the run summary on completion.

**Undo receipts.** Every undo-capable write records the pre-image state. The undo path is computed before the write executes. The user can preview what undo would restore. After undo, the system records what was undone and whether the undo succeeded fully or partially.

**Run receipts.** Every agent run produces a run summary containing: the initial prompt, the full tool call sequence, the cost ledger, the approval decisions, the final output, and the session metadata. These summaries are retained in the RunStore and are searchable by date, tool, cost range, and outcome.

The receipts contract: if it happened, there is a record. If there is no record, it did not happen. This is the foundation for trust in autonomous operations.

## Comparison with Pi and Codex

### Pi (Malleability Reference)

Pi.dev demonstrates what deep malleability looks like. Pi makes the agent feel like a live environment that the user can reshape in real time -- modifying prompts, injecting context, redirecting the agent mid-conversation, and composing skills fluidly. The user experience is conversational and responsive.

What TeaAgent takes from Pi: the commitment that the user should never hit a wall where the answer is "the system does not support that." Skills, tool registration, and run lifecycle flexibility are direct responses to Pi's example.

What TeaAgent adds that Pi does not prioritize: governance. Pi does not track costs transparently, does not prepare undo paths, does not gate destructive tools behind policy, and does not produce structured audit records. Pi trusts the user completely. TeaAgent trusts the user and also trusts the record.

### Codex (Governance Reference)

Codex (and its agent mode) demonstrates what enterprise-safe agent operation looks like. Permission gates, approval queues, workspace sandboxing, and cost controls. Codex is designed for environments where mistakes have real consequences.

What TeaAgent takes from Codex: the seriousness of safety gates. The permission mode spectrum, the approval queue, the plan gate, the budget cap -- these are direct responses to Codex's example.

What TeaAgent adds that Codex does not prioritize: malleability. Codex's governance is rigid. You cannot compose custom skills, register ad-hoc tools, or suspend and fork runs. Codex's safety comes from restricting what the user can do. TeaAgent's safety comes from recording and governing what the user can do -- while keeping those capabilities open.

## Trade-off Guidance: When to Favor Which

### Favor malleability when:

- **Exploration and prototyping.** The user is learning a codebase, testing hypotheses, or iterating on a design. Safety gates should be wide (plan-only or ask-on-write). The user should be able to inject ad-hoc context, try different prompts, and fork runs without friction.
- **Skill development.** The user is writing or debugging a custom skill. They need to test tool registrations, tweak system prompts, and iterate rapidly. Permission overhead should be minimal for the skill author's own workspace.
- **Local development.** The user is working in a sandboxed environment (local machine, dev branch, isolated container). The risk surface is bounded. The harness should optimize for flow state, not gate checks.

### Favor governance when:

- **Production operations.** The agent is running against production infrastructure, making real changes, or affecting live users. Every tool call must be gated, every change must be approved, every cost must be tracked.
- **CI/CD pipelines.** The agent runs unattended. Budget caps are hard limits. Approval decisions are automated through policy. The audit trail must be complete and tamper-evident.
- **Regulated environments.** Compliance requirements demand per-action records, separation of duties, and retention policies. The harness must produce receipts that satisfy external auditors.
- **Multi-tenant or shared workspaces.** The agent operates in a workspace shared across team members. Permission modes must be strict, undo paths must be reliable, and cost attribution must be precise.

### The tension is real and by design

The same feature that makes a harness malleable (ad-hoc tool registration, live prompt injection, background session forking) also makes it harder to govern. The same feature that makes a harness safe (pre-approval for every write, mandatory plan gates, hard budget caps) also adds friction.

TeaAgent does not resolve this tension. It manages it. The architecture provides the knobs. The user -- or the team -- sets them based on context. The harness's job is to make both extremes work well and to support every point between them without bifurcating the codebase.

## Decision Framework

For every proposed feature, ask two questions in order:

1. **Does this make the harness more moldable?** Can users reshape behavior in ways they could not before? Does it lower the cost of customization? Does it remove a wall between the user and their intent?

2. **Does this make the harness more inspectable?** Does it produce a new receipt, improve an existing one, or make receipts more accessible? Does it close a gap in the evidence ledger?

A feature that scores yes on both is a clear priority. A feature that scores yes on one and no on the other requires a deliberate decision based on context. A feature that scores no on both should not be built.

When a feature scores yes on moldability but no on inspectability, the first question is: can we add inspectability? If the answer is yes (and it almost always is), do that before shipping. Do not ship a feature that creates a blind spot in the evidence ledger.

When a feature scores yes on inspectability but no on moldability, the first question is: is there a lighter-weight way to achieve the same governance outcome? If the answer is yes, do that instead. If the answer is no, build the feature -- inspectability gaps are safety gaps.

## Decision Matrix

For each common scenario, here is how the harness provides both malleability and receipts.

### Exploration

- **Malleability:** User runs agent in plan-only or ask-on-write mode. No gate friction for read-only operations. User can inject background context mid-session. User can fork the run to explore alternatives.
- **Receipts:** ChatSessionController records every prompt and response. Cost tracker accumulates token usage. RunStore persists the session for later review. User can replay the exploration path.

### Editing

- **Malleability:** User registers custom edit tools through ToolRegistry. Permission mode allows safe writes (ask-on-write). Undo path is computed before each write. User can suspend a long edit session and resume later.
- **Receipts:** Every edit records tool, parameters, cost, and approval gate. Undo receipts capture pre-image state. Run summary shows every file changed and by which tool.

### Debugging

- **Malleability:** User injects ad-hoc debug prompts, forks the run at a specific turn, inspects tool call parameters and return values. Can suspend, inspect state, and resume.
- **Receipts:** Full tool call history with parameters and outputs. Cost trackings per debug cycle. Session suspension state is persisted and recoverable.

### Review

- **Malleability:** User inspects a completed run through the run summary. Can fork the run to test a reviewer suggestion. Can replay the run step by step.
- **Receipts:** Run summary includes prompt, tool sequence, cost, approvals, and final output. Audit log provides the raw evidence. Undo receipts show what would be reverted.

### Deployment

- **Malleability:** Automated run with policy-as-code permissions. User configures budget caps, approval gates, and tool allowances per environment. CI/CD pipeline picks up the same policy files.
- **Receipts:** Every deployment run produces a complete evidence ledger. Budget overruns are prevented. Policy violations are recorded. Approval queue stores every decision. RunStore retains the full history for compliance.

## Conclusion

Malleable workflows with receipts is not a slogan. It is a design constraint that applies to every feature, every tool registration, every permission mode, and every audit record. When the harness makes something easier to do, it must also make that thing easier to verify. When the harness adds a gate, it must also add a way to understand and adjust it.

This document should be referenced when evaluating RFCs, reviewing PRs that touch governance or malleability, and deciding which direction to prioritize when the two are in tension. When in doubt, ask: does this make the system more moldable or more inspectable? If the answer is "neither," stop. If the answer is "both," proceed. If the answer is "one of them," fix that before shipping.
