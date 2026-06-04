# Phase 0 To Phase 1 Outlook
# 2026-06-04

## Thesis

TeaAgent's differentiated path is not to become the broadest agent framework. It
is to become the agent harness whose behavior can be explained, audited, and
recovered when something goes wrong.

The pasted review's strongest insight is that TeaAgent looks more like a
security product than a demo. The strategic risk is that security-product
process can grow faster than product clarity. The next four weeks should turn
governance assets into fewer, sharper user-visible guarantees.

## Strategic Reading

### What is real

- The zero-dependency core is a real architectural advantage.
- The permission vocabulary is product-defining, not incidental.
- Acceptance coverage is broad enough to support rapid hardening.
- ADRs and module docs give future maintainers unusual historical context.
- The daily-driver direction is coherent: TUI, chat, and agent mode should share
  controller semantics, cost truth, undo truth, and audit truth.

### What is not yet real

- "Production-safe autonomy" is not yet a fair claim.
- "Approval governance is unified" is not yet fully true while duplicate
  approval-manager names and bypass flags remain.
- "Docs are healthy" is only true if front doors keep current truth discoverable.
- "Optional dependencies are safe" is only true after optional-extra scanning is
  explicit.

## Phase 0 Priorities

| Priority | Theme | Why now | ROI |
| --- | --- | --- | --- |
| P0 | Gate destructive bypasses | Protects the core trust promise | Very high |
| P0 | Consolidate or rename approval manager authority | Prevents future wrong patches in security code | Very high |
| P0 | Break policy/approval helper coupling | Reduces import fragility and reasoning cost | High |
| P0 | Decide memory catalog canonical structure | Removes divergent behavior in context/memory paths | High |
| P0 | Coverage omit accountability | Turns "excluded" into managed debt | High |
| P0 | Optional dependency audit policy | Keeps zero-dependency core from hiding optional risk | High |

## Phase 1 Entry Criteria

Phase 1 can begin when these are true:

1. P0 trust risks have owners and failing tests or closed PRs.
2. `danger-full-access` and `allow_all_destructive` are impossible to confuse in
   CLI, TUI, and API surfaces.
3. TUI and CLI chat share the same execution, cost, result, and undo semantics or
   explicitly document remaining differences.
4. `docs/daily-driver-current-status.md` accurately links the current risk,
   roadmap, and ticket truth.
5. New feature proposals reference the risk register and include acceptance tests
   before implementation.

## Phase 1 Work Themes

### 1. Daily user confidence

Focus: first-hour onboarding, error recovery, cost display, undo/recovery, and
state visibility.

Reason: users forgive missing features more easily than false confidence. The
daily driver becomes credible when it tells the user what happened and what can
be recovered.

### 2. Agent mode continuity

Focus: suspend, resume, background review, run evidence, and actionable audit
summaries.

Reason: agent mode is where trust failures become expensive. A background run
must never leave the user guessing whether it is paused, completed, failed, or
waiting for approval.

### 3. Optional runtime ecosystem

Focus: managed runtimes, MCP trust policy, skills, and plugins.

Reason: ecosystem expansion is valuable only after the base trust contract is
clear. Optional runtimes should be powerful but visibly governed.

## Investment View

| Investment | Cost | Risk reduction | User value | Recommendation |
| --- | --- | --- | --- | --- |
| Approval bypass fix | Low to medium | Very high | High | Do immediately |
| Approval manager consolidation/rename | Low to medium | High | Medium | Do immediately |
| Memory catalog consolidation | Medium | High | Medium | Do in Phase 0 |
| Coverage omit smoke tests | Medium | Medium | Medium | Do in parallel |
| Docs front-door index | Low | Medium | High for maintainers | Do in Phase 0 |
| New managed-runtime features | High | Low or negative until audit lanes exist | Medium | Wait |
| Large UX redesign | High | Medium | Potentially high | Wait until trust repair exits |

## Four-Week Watch Metrics

| Metric | Current baseline | Target direction |
| --- | ---: | --- |
| P0 trust risks without owner | To be assigned | 0 |
| Approval manager canonical classes | 2 names | 1 authority name |
| Memory catalog implementations | 2 implementations | 1 runtime implementation |
| Coverage omit patterns | 16 | Every entry has reason and return path |
| Acceptance tests collected | 441 | Stable or rising with real-path tests |
| Markdown files | 435 | Growth allowed only with front-door links |
| Commit velocity | 626 commits in 27 days | Lower churn, higher review clarity |

## Future Outlook

The project has a credible future if it stays ruthless about trust repair. The
winning shape is a compact, auditable core with optional power surfaces that
remain visibly governed.

The project stalls if documentation becomes a replacement for closure, if tests
protect risky legacy semantics, or if optional ecosystem breadth outruns the
permission model.

The next phase should feel less like "add more agent features" and more like
"make every trust claim boringly true."
