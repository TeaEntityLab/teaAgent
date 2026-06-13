# M5 — HookRegistry: Observability Onto the Spine, Execution Stays in Dispatch

> **Status:** observability slice DONE (taxonomy typed + reader-surfaced); the
> enforcement-bridge half of the planned M5 is assessed UNSUITABLE for the same
> runtime-coupling reason as approval (B) and budget (B-analog). Recommendation:
> close M5 as **observability-only**. Owner decision pending on the bridge.

## What the plan assumed vs. what the code shows

The work-plan's M5 (§7 row, T002) assumed hooks run in the runner and that the
migration would move **PreToolUse → spine interceptor**, **PostToolUse + session
lifecycle → spine consumers**, touching `teaagent/runner/_core.py`. The
observable code contradicts every part of that:

| Hook | Production caller | Nature |
|---|---|---|
| PreToolUse | `teaagent/tools.py::ToolRegistry.execute` (~line 222) | **Mutates in-flight `arguments`** fed to `tool.handler`; can veto via `HookError`; destructive-tool mutation guard |
| PostToolUse | `teaagent/tools.py::ToolRegistry.execute` (~line 291) | **Mutates the tool `result`** returned upstream |
| SessionStart / SessionEnd / UserPromptSubmit / PreCompact / Stop / SubagentStop | **none** — only tests call `run_session_*` etc. | defined + unit-tested, **not wired into any production path** |

So hooks live at the **tool-dispatch layer**, plumbed via
`tool_registry.hook_registry` ([chat_agent.py:502](../../teaagent/chat_agent.py),
[run_contract.py:105](../../teaagent/integration/run_contract.py)) — not the
runner the plan named.

## Finding: the enforcement bridge is unsuitable (third consecutive case)

1. **PreToolUse/PostToolUse are mutating, not pure decisions.** `run_pre_hooks`
   rewrites `arguments`; the rewritten args feed `tool.handler`. `run_post_hooks`
   rewrites `result`. An EventSpine interceptor can veto (raise) but the spine
   has **no channel to carry mutated args/results back** to the dispatch site
   that consumes them. This is the same shape that kept approval inline (a gate
   that mutates in-flight state, not a pure event decision) — moving it onto the
   spine would either lose the mutation capability or require the spine to ferry
   mutable payloads back into `tools.py`, the coupling we rejected for approval.

2. **The session-lifecycle hooks have no inline path to strangle.** They are not
   invoked in production. "Move them to spine consumers" would move *nothing*;
   to make them do anything you would have to **newly wire** them — that is
   feature work, not a parity-preserving migration, and out of scope for the
   strangler arc.

3. Even setting (1)-(2) aside, PreToolUse runs *inside* `tool.handler` dispatch,
   after the runner's plan interceptor and inline approval already allowed the
   call — a different layer than the spine's `TOOL_CALL_REQUESTED` point.

## What IS suitable, and was done

The genuinely spine-shaped value is **observability** — identical to M2 and to
the approval/budget observability that already reaches the M6 fold. The
HookRegistry bridge already emits 5 audit events; they were untyped. Done:

- Added 5 members to `RunEventType` (`teaagent/runner/_events.py`):
  `TOOL_HOOK_PRE_MUTATION`, `TOOL_HOOK_PRE_MUTATION_BLOCKED`, `TOOL_HOOK_VETOED`,
  `TOOL_HOOK_POST_MUTATION`, `TOOL_HOOK_POST_FAILED`.
- Added the 5 bidirectional mapper entries; the M2-T001 reader now surfaces hook
  veto/mutation activity **from the audit JSONL** for the M6 fold.
- Test `test_m5_hook_audit_events_are_typed_and_reader_surfaced` +
  round-trip completeness (`len(mapper) == len(RunEventType)` now 31).

Mapping/reader only. **Hook execution is unchanged** — it stays in the dispatch
layer, with its mutation semantics and audit emission exactly as before. Audit
bytes are unchanged.

## Recommendation

**Close M5 as observability-only.** The hook taxonomy is typed and folds into
M6; hook *enforcement/mutation* stays in `tools.py` by the same evidenced logic
as approval (B) and budget (B-analog): the spine/interceptor model fits
stateless, non-mutating decisions; mutating/dispatch-coupled mechanisms stay
where they are.

Separately (and out of the migration's scope): the 6 unwired session-lifecycle
hooks (SessionStart/End, UserPromptSubmit, PreCompact, Stop, SubagentStop) are
**defined but dead** in production. Wiring them is a product decision, not a
spine migration — flag for the backlog, do not bundle here.

## Pattern across M3-M5

- **M3 plan gate** → moved to interceptor cleanly (stateless decision).
- **M4 approval** → stays inline (runtime-stateful: JIT/handler/swappable policy).
- **M4 budget** → stays inline (dedup state + interactive handler + multi-point).
- **M5 hooks** → execution stays in dispatch (mutating + dead lifecycle hooks);
  observability folds onto the spine.

The spine's realized value is the **read side** (typed evidence → M6 fold → M7
consumers), not wholesale relocation of enforcement. Plan gate is the one gate
that genuinely belonged on the spine.
