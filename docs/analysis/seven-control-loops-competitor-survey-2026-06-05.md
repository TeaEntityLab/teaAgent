# Seven Control Loops Competitor Survey - 2026-06-05

## Purpose

This survey records the current agent-system topics behind seven control loops:

1. Spec-first controls direction.
2. Dynamic workflow controls breadth.
3. Loop and goal control depth.
4. Model routing controls cost and quality.
5. Synthesis review controls truth.
6. Precise memory controls cross-session drift.
7. Human review gates control irreversible risk.

The goal is to compare competitor direction with TeaAgent's structure and turn
the differences into roadmap work.

## Source Boundary

Primary sources:

- GitHub Spec Kit documentation:
  - https://github.github.com/spec-kit/index.html
- AWS/Kiro documentation:
  - https://aws.amazon.com/documentation-overview/kiro/
  - https://kiro.dev/docs/specs/
  - https://kiro.dev/docs/steering/
- Cline documentation:
  - https://docs.cline.bot/core-workflows/plan-and-act
- OpenCode documentation:
  - https://dev.opencode.ai/docs/agents/
  - https://opencode.ai/docs/skills/
- Claude Code documentation:
  - https://code.claude.com/docs/en/memory
  - https://code.claude.com/docs/en/code-review
  - https://code.claude.com/docs/en/hooks
  - https://code.claude.com/docs/en/model-config
- GitHub Copilot documentation and changelog:
  - https://docs.github.com/en/copilot/how-tos/use-copilot-agents/request-a-code-review/use-code-review
  - https://github.blog/changelog/2026-04-27-github-copilot-code-review-will-start-consuming-github-actions-minutes-on-june-1-2026/
- OpenAI Codex product documentation:
  - https://openai.com/index/introducing-the-codex-app/
  - https://openai.com/index/codex-for-almost-everything/
  - https://openai.com/index/introducing-gpt-5-2-codex/
- Pi documentation:
  - https://pi.dev/docs/latest/extensions
  - https://pi.dev/docs/latest/packages

Research sources:

- https://arxiv.org/abs/2604.05278
- https://arxiv.org/abs/2605.18583
- https://arxiv.org/abs/2605.14859
- https://arxiv.org/abs/2605.08017
- https://arxiv.org/abs/2603.20847

Community sources:

- Reddit Kiro steering/spec posts from May 2026 search results.
- Reddit OpenCode subagent/model-routing posts from March to May 2026 search
  results.
- Reddit Claude Code memory posts from February to May 2026 search results.

Community posts are treated as operational signals, not proof.

## Executive Synthesis

The newest agent ecosystems are converging on the same pattern:

- A spec or plan layer narrows intent before code.
- Dynamic skills, hooks, packages, extensions, and subagents widen what the
  agent can do.
- Long-running goal loops and parallel worktrees let agents attack deeper work.
- Model routing and effort controls are becoming explicit cost/quality knobs.
- Automated review is becoming a second agent system, not a single prompt.
- Memory is moving from one giant rules file toward scoped, layered state.
- Human review remains the terminal authority for irreversible changes.

The counter-pattern is equally clear:

- Specs can drift or become theater if not grounded in repository evidence.
- Dynamic workflow surfaces can become unreviewed supply-chain or persistence
  paths.
- Deep loops can overrun scope, cost, and context.
- Model routing can be invisible or ignored by subagents.
- Review agents can create cost without merge authority.
- Memory can make the agent worse when stale, broad, or unverifiable.
- Human review gates fail when the gate lacks enough evidence to review.

TeaAgent already has strong ingredients for the safety side: approvals, audit,
run receipts, candidate skills, budget, plan gates, and memory catalog. The gap
is integration. The seven controls need one coherent operating model.

## Control Loop 1: Spec-First Controls Direction

### Competitor evidence

GitHub Spec Kit defines spec-driven development as a workflow that puts
specifications at the center of AI-assisted development. Its default process is
Spec -> Plan -> Tasks -> Implement, with Markdown artifacts feeding each phase.

Kiro presents specs as structured artifacts that turn high-level ideas into
requirements, design, and tasks. Its docs describe `requirements.md` or
`bugfix.md`, `design.md`, and `tasks.md`, plus task execution and parallel task
waves.

Cline separates Plan mode from Act mode. Plan mode can read and search but not
modify files or execute commands; Act mode executes against the planning
context. Cline also supports different models for Plan and Act.

Research signal:

- Spec Kit Agents argues that SDD can still be "context blind" in large repos,
  and proposes phase-level repository grounding hooks.

Community signal:

- Kiro users report that steering/spec docs can be ignored or can consume quota
  without producing working output.

### TeaAgent comparison

TeaAgent has:

- `docs/specs/` as a spec surface.
- `teaagent/plan.py`, `teaagent/plan_storage.py`, and `teaagent/plan_mode.py`.
- `teaagent/governance/plan_gate.py`.
- Plan-before-write ADR and approval-oriented workflow.

TeaAgent lacks:

- One canonical spec lifecycle equivalent to Spec -> Plan -> Tasks -> Implement.
- A repository-grounding check at each spec phase.
- A spec hash that every execution step can cite.
- A failure mode where "spec exists but code violated it" is easy to detect.

### Integration thesis

TeaAgent should adopt spec-first as a gating spine, not as more documentation.

Minimum rule:

- For multi-file, destructive, security-sensitive, or long-horizon work, the run
  must bind to a spec artifact or explicit "small task no spec" exemption.

## Control Loop 2: Dynamic Workflow Controls Breadth

### Competitor evidence

Pi extensions are TypeScript modules that can subscribe to events, register
custom tools, add commands, intercept tool calls, store session state, customize
compaction, register providers, and hot-reload from project or global paths.
Pi docs also warn that extensions run with full system permissions.

OpenCode has primary agents, subagents, and on-demand Agent Skills. Skills are
loaded by a native skill tool after discovery from project and global paths.
OpenCode agents can have custom prompts, models, and permissions.

Codex app documentation describes skills as bundles of instructions, resources,
and scripts, and says users can explicitly ask Codex to use a skill or let Codex
choose based on task.

### TeaAgent comparison

TeaAgent has:

- Agent Skills discovery.
- Skill candidates, required artifacts, review, eval, and install.
- ToolRegistry and typed tool metadata.
- MCP and hook surfaces.

TeaAgent lacks:

- A fast but governed "create, reload, test, refine" workflow.
- Runtime proof that a loaded skill was used.
- A protected path policy for active skill directories.
- A single UX story for prompt skills versus executable skill tools.

### Integration thesis

TeaAgent should not copy Pi's full-power extension default. It should adopt
dynamic workflow breadth through reviewed candidate paths and visible lifecycle
states.

Minimum rule:

- New dynamic capabilities start as candidates unless the user explicitly opts
  into unmanaged development mode.

## Control Loop 3: Loop And Goal Control Depth

### Competitor evidence

Codex app documentation frames the new challenge as supervising multiple agents
over long-running tasks that can span hours, days, or weeks. It uses separate
threads and worktrees for parallel work.

OpenAI's GPT-5.2-Codex release highlights improvements on long-horizon work
through context compaction.

Cline recommends `/deep-planning` for complex work and returning to Plan mode
when unexpected complexity appears.

Kiro can execute independent spec tasks concurrently by building a dependency
graph and running task waves.

### TeaAgent comparison

TeaAgent has:

- Iteration and tool-call limits.
- RunStore and audit logs.
- Context bus.
- Subagent and background/suspension surfaces.
- Plans and task ledgers in docs.

TeaAgent lacks:

- One durable goal object that links spec, plan, task wave, runs, evidence, and
  review outcome.
- Goal health metrics for drift, cost, blocked state, and context rot.
- A dependency-aware task wave executor tied to current roadmap items.
- A "stop and re-plan" protocol when the loop encounters unknown complexity.

### Integration thesis

TeaAgent should treat deep work as a goal lifecycle, not a single long prompt.

Minimum rule:

- A goal run should expose current objective, bound spec, active tasks, cost,
  evidence, blockers, and next gate.

## Control Loop 4: Model Routing Controls Cost And Quality

### Competitor evidence

Cline supports separate models for Plan and Act modes and gives examples for
cost optimization, maximum quality, and speed-focused setups.

OpenCode agents can override the model per agent; if no model is specified,
subagents inherit the invoking primary agent's model.

Claude Code model configuration includes initial model selection and managed
`availableModels` allowlists. The docs distinguish initial selection from
enforcement and note that managed/policy settings are required for strict
control.

Pi extensions can register providers and set models dynamically.

GitHub's April 2026 Copilot Code Review billing change shows that agentic
review consumes both AI credits and, on private repositories, GitHub Actions
minutes after June 1, 2026.

### TeaAgent comparison

TeaAgent has:

- `teaagent/model_routing.py`.
- Provider registry and model smoke flows.
- Budget and cost tracker modules.
- Role prompts and current AGENTS model routing guidance.

TeaAgent lacks:

- A durable, tested role-to-model routing contract that every surface obeys.
- Per-task routing evidence in run summaries.
- Automatic downgrade/upgrade decisions tied to task risk and budget.
- A guard against accidental subagent model inheritance when a role explicitly
  needs a different capability/cost tier.

### Integration thesis

TeaAgent should make model routing explicit, auditable, and budget-aware.

Minimum rule:

- Every run records requested model, resolved model, routing cause, estimated
  cost, actual cost, and whether a policy/allowlist constrained selection.

## Control Loop 5: Synthesis Review Controls Truth

### Competitor evidence

Claude Code Review uses a fleet of specialized agents to inspect pull requests
for logic errors, security vulnerabilities, edge cases, and regressions. Its
docs say a verification step filters candidate findings, and results are
deduplicated, ranked, and posted as inline comments. It does not approve or
block PRs.

GitHub Copilot Code Review leaves comment reviews rather than approve/request
changes reviews, so it does not satisfy required approvals or block merging.
Copilot review can use repository instructions, Agent Skills, and MCP context;
GitHub docs explain how to verify which MCP tools were called from review
session logs.

Research signal:

- The PR lifecycle paper finds that terminal merge authority remains mostly
  human across analyzed tools, even when agents open and carry PR work.

### TeaAgent comparison

TeaAgent has:

- Run receipts and audit logs.
- Code review and reflective-review workflows in the surrounding tooling.
- Acceptance docs and validation scripts.
- Subagent review surfaces.

TeaAgent lacks:

- A mandatory synthesis review pass for high-risk or long-running runs.
- A machine-readable distinction between "finding", "verified finding",
  "false positive", and "human accepted".
- A review evidence bundle that can prove which files, tests, sources, and tools
  informed the synthesis.

### Integration thesis

TeaAgent should make synthesis review a separate evidence-producing phase, not
just another answer from the same agent.

Minimum rule:

- High-risk runs cannot move from "produced output" to "ready to merge" without
  a synthesis review artifact and human review gate status.

## Control Loop 6: Precise Memory Controls Cross-Session Drift

### Competitor evidence

Claude Code has two memory mechanisms: `CLAUDE.md` instructions written by the
user and auto memory written by Claude. Its docs state both are loaded at the
start of each conversation and are context, not enforced configuration.

Kiro steering files provide persistent knowledge about product, tech stack, and
project structure. Kiro docs warn never to include secrets and recommend
reviewing steering changes like code changes.

Codex product documentation says Codex can remember preferences and learn from
previous actions.

Community signal:

- Claude Code and Kiro users report confusion when memory or steering files are
  ignored, too broad, or stale.

### TeaAgent comparison

TeaAgent has:

- `MemoryCatalog`.
- Team memory.
- Pinned files.
- Failure cards.
- Memory isolation tests and current memory risk docs.

TeaAgent lacks:

- Typed memory classes with different TTL, owner, provenance, and review rules.
- A memory quarantine/promote loop for agent-written memory.
- A compact memory budget policy tied to context health.
- A way to prove which memory item influenced a run.

### Integration thesis

TeaAgent should treat memory as precise scoped evidence, not generic prompt
state.

Minimum rule:

- Agent-written memory starts as quarantined, source-linked, and reviewable
  unless it is a low-risk ephemeral run note.

## Control Loop 7: Human Review Gate Controls Irreversible Risk

### Competitor evidence

The Overeager Coding Agents paper measures agents doing more than asked on
benign tasks and reports that stripping explicit consent declarations increases
overeager behavior.

The least-privilege authorization paper reports that frontier models can both
omit required permissions and grant unused or sensitive permissions; more
reasoning does not fix this by itself.

Claude Code memory docs say behavioral context is not enforcement and point to
PreToolUse hooks for hard blocking.

GitHub Copilot and Claude review systems both keep PR merge authority outside
the review agent.

Pi packages and extensions warn that installed packages/extensions can run with
full system access.

### TeaAgent comparison

TeaAgent has:

- Approval manager.
- Permission modes.
- Tool governance.
- Plan-before-write gate.
- Hash-chained audit.
- Path-scoped approvals.
- Human review language in governance docs.

TeaAgent lacks:

- A single irreversible-risk classifier shared by CLI/TUI/agent/dynamic skills.
- A review gate that attaches to memory promotion, skill install, model routing,
  and long-running goal closeout uniformly.
- A concise "why human review is required" UX state.

### Integration thesis

TeaAgent should keep human review gates as the final authority for irreversible
changes, but make them cheaper to perform through better evidence.

Minimum rule:

- Human review gates should be evidence-rich, not chat-based. The gate should
  show spec hash, diff, tool calls, approval history, cost, tests, unresolved
  risks, and rollback path.

## Competitor Difference Matrix

| Control | Competitors emphasize | Common weakness | TeaAgent advantage | TeaAgent gap |
| --- | --- | --- | --- | --- |
| Spec-first | Spec Kit, Kiro, Cline plan mode | Specs can drift or be ignored | Plan gate and docs governance | No one canonical spec lifecycle |
| Dynamic workflow | Pi extensions, Codex skills, OpenCode skills | Full-access or unmanaged extension risk | Candidate skills and audit | Slow create-reload-test loop |
| Loop/goal | Codex worktrees, Kiro task waves, Cline deep planning | Long loops drift or cost too much | RunStore and tool limits | No durable goal object |
| Model routing | Cline mode models, OpenCode agent models, Claude allowlists | Routing can be invisible or inherited incorrectly | Budget/cost modules | No auditable routing contract |
| Synthesis review | Claude/Copilot code review | Does not replace human approval | Evidence ledger mindset | No mandatory synthesis gate |
| Precise memory | Claude memory, Kiro steering, Codex preferences | Memory is context, not enforcement | MemoryCatalog and failure cards | No typed memory lifecycle |
| Human review | PR gate remains human | Review can lack evidence | Approval and audit systems | Gate UX not unified across surfaces |

## Recommendations

1. Add a seven-control-loop strategy doc as the new product frame.
2. Add an architecture integration map that connects each control to existing
   TeaAgent modules.
3. Add a work-item ledger that attaches these controls to roadmap horizons.
4. Update `docs/roadmap-status.md` so H2 through H5 explicitly name these
   controls.
5. Keep dynamic skill work as H3's first spine, but make the seven controls the
   broader framework for product maturity.

## Bottom Line

The current market is moving from "agent can code" to "agent systems can be
controlled." TeaAgent's differentiation should be that every control loop is
inspectable: spec controls direction, workflow controls breadth, goal loops
control depth, model routing controls spend, review controls truth, memory
controls drift, and human gates control irreversible risk.
