# Seven Control Loops Critical Questioning - 2026-06-05

## Purpose

This review challenges the seven-control-loop direction before it becomes
process theater. The point is to make the concept falsifiable.

## Core Challenge

The seven loops are useful only if they reduce real daily-driver failure modes.
If they become another layer of documents without runtime evidence, they will
increase drift instead of controlling it.

## Question 1: Does spec-first actually control direction?

Concern:

- Specs can be vague, stale, or ignored.
- A spec can become a ritual that delays work but does not constrain it.

Evidence:

- Kiro and Spec Kit both promote structured specs.
- Spec Kit Agents research says SDD can still be context blind without
  repository-grounding hooks.
- Community reports around spec/steering systems show ignored instructions and
  quota cost.

TeaAgent risk:

- TeaAgent may write more specs without binding runs to spec hashes.

Required proof:

- A mutating high-risk run fails without spec or explicit exemption.
- A run summary includes spec hash and acceptance criteria.
- A validator catches a run output that contradicts the bound spec.

## Question 2: Does dynamic workflow expand breadth safely?

Concern:

- Dynamic workflow can become unreviewed code execution or persistent prompt
  poisoning.

Evidence:

- Pi extensions can register tools, intercept events, and run with full system
  permissions.
- OpenCode and Codex use skills as reusable capability packages.
- TeaAgent's RSS failure showed skill creation can land in compatibility paths
  without proving reviewed use.

TeaAgent risk:

- The project could claim "dynamic skill support" while generated skills still
  fail basic behavior checks.

Required proof:

- Direct active-skill writes are blocked or quarantined.
- Generated skill candidates pass deterministic eval before install.
- A later run proves activation and output verification.

## Question 3: Do goal loops deepen hard work or hide drift?

Concern:

- Long-running loops can accumulate wrong assumptions.
- Parallel agents can produce conflicting artifacts.
- Context compaction can preserve the wrong summary.

Evidence:

- Codex app emphasizes long-running multi-agent tasks and worktrees.
- GPT-5.2-Codex highlights long-horizon improvements through compaction.
- Cline recommends returning to Plan mode when unexpected complexity appears.

TeaAgent risk:

- Background/goal work may become a sequence of loosely related runs rather than
  one inspectable goal.

Required proof:

- A goal object links spec, tasks, runs, cost, memory, review, and blockers.
- A goal can be paused, inspected, resumed, and closed with evidence.
- Drift triggers re-plan rather than continuing silently.

## Question 4: Does model routing control cost and quality or just add knobs?

Concern:

- Model routing can be invisible to users.
- Subagents can inherit the wrong model.
- Strong models can be used where cheap models would work.
- Cheap models can be used where high-risk review needs depth.

Evidence:

- Cline supports different Plan and Act models.
- OpenCode supports agent-level model overrides but subagents inherit invoking
  primary model when unspecified.
- Claude Code distinguishes initial model settings from enforced allowlists.
- GitHub Copilot review billing changes show review work has real cost.

TeaAgent risk:

- Project instructions say which model to use, but runtime evidence does not
  prove it happened.

Required proof:

- Run evidence records requested model, resolved model, route reason, policy,
  estimate, and actual cost.
- Tests prove plan/review/execution role routing does not silently diverge.

## Question 5: Does synthesis review control truth?

Concern:

- Review agents can produce plausible false positives.
- Review can increase cost without changing merge quality.
- The original agent may review its own work too sympathetically.

Evidence:

- Claude Code Review uses specialized agents and verification before posting
  deduplicated findings.
- Copilot code review comments do not approve or block PRs.
- PR lifecycle research shows human merge governance remains the terminal
  authority across tools.

TeaAgent risk:

- "Review passed" may become another natural-language claim.

Required proof:

- Review findings have states and evidence paths.
- Synthesis review is run by a separate role/model/prompt where appropriate.
- Human gates can accept/reject review findings.

## Question 6: Does precise memory reduce cross-session drift?

Concern:

- Memory can make agents worse when stale, broad, or wrong.
- Auto-written memory can preserve a bad inference.
- Guidance docs are context, not enforcement.

Evidence:

- Claude Code docs explicitly say memory is context and not enforced
  configuration.
- Kiro steering docs recommend review and warn against secrets.
- Community posts report confusion around memory and steering reliability.

TeaAgent risk:

- MemoryCatalog becomes a dumping ground for summaries that future agents
  over-trust.

Required proof:

- Agent-written durable memory has provenance, scope, TTL, confidence, and
  review state.
- A run can show which memory entries were read or used.
- Stale or untrusted memory is quarantined or excluded.

## Question 7: Do human review gates control irreversible risk?

Concern:

- A prompt saying "ask before dangerous actions" is not a gate.
- Humans may approve without enough evidence.
- Model-generated permission policies can be both too broad and too brittle.

Evidence:

- Overeager Coding Agents reports measurable out-of-scope actions.
- Least-privilege authorization research reports frontier models can grant
  unused/sensitive permissions and omit needed ones.
- Claude Code docs direct hard blocking to hooks/settings, not memory.
- Review systems keep merge authority outside the agent.

TeaAgent risk:

- Approval gates exist, but not every irreversible path may share the same gate
  packet and evidence standard.

Required proof:

- Irreversible paths produce a human review gate packet.
- The packet includes spec, diff, tools, cost, tests, risks, and rollback.
- Tests prove high-risk skill/memory/model-policy paths cannot bypass it.

## Cross-Loop Failure Modes

| Failure | What it looks like | Control that should catch it |
| --- | --- | --- |
| Spec theater | Beautiful spec, wrong code | Spec hash plus output verification |
| Dynamic sprawl | Many skills, no proven use | Skill lifecycle and candidate eval |
| Goal drift | Long task changes objective | Goal state and re-plan trigger |
| Cost leak | Strong model used for low-risk task | Model route receipt and budget |
| Review theater | "Looks good" without evidence | Synthesis review record |
| Memory poisoning | Bad summary persists | Memory quarantine and provenance |
| Rubber-stamp approval | Human clicks yes blindly | Gate packet and rollback evidence |

## Minimum Bar For Adoption

Do not declare the seven-loop architecture complete until:

- At least one acceptance test exists for each loop.
- Each loop has a receipt type.
- Each loop has a visible user-facing summary.
- Each loop has a failure state.
- Cross-loop docs link to roadmap rows.

## Bottom Line

The seven loops are a strong mental model, but only if they become runtime
contracts. The project should keep the phrase, but make it earn its place:
every loop must catch a real class of failure that users would otherwise feel
as lost time, lost money, fake success, stale memory, or irreversible damage.
