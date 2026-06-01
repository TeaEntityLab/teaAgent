# Subagent Parent-Review & Merge Workflow
# 2026-06-01

**Fills:** Gap **F-ECO-006** — *"define `subagent review` as a first-class journey and
test the parent review → patch apply → conflict path."*

**Grounding (current state — more complete than the May-31 review assumed).**
- **`teaagent/subagents/_review.py`** (230 lines): `SubagentReviewArtifact`,
  `capture_subagent_review(...)` — persists an isolated **child worktree diff as a
  binary patch** (`git diff --binary HEAD`) before cleanup, keyed by `SubagentLineage`
  (worktree/container paths). Plus `list_subagent_reviews`, `load_subagent_review`,
  `check_subagent_review` (`apply_patch=False`, dry-run) and
  `apply_subagent_review` (`apply_patch=True`).
- **`teaagent/cli/_handlers/agent_review.py`** (245): `interactive_review_mode(run_id)`
  — per-file **accept / edit / reject** loop, writes `review-{run_id}.json` with counts.
- **`teaagent/subagents/_isolation.py`** (292), `_manager.py` (382),
  `_team_orchestrator.py` (224), `_approval_queue.py` (866) — isolation, lineage,
  orchestration, and a destructive-tool approval queue all exist.

**What exists:** per-child patch capture, dry-run check, single-patch apply, interactive
per-file accept/edit/reject, lineage tracking.
**What's missing (the *journey*):** the **multi-child** parent decision flow — compare
several children's results side by side, apply one and reject the rest, handle
**conflicts** when a patch no longer applies cleanly, and **record rationale** for the
choice (delegation accountability).

---

## The parent-review journey (fan-in)

```
children finish → capture patches → COMPARE → SELECT → APPLY (handle conflict) → RECORD → CLEANUP
```

| Step | Operator action | Backed by | Gap to close |
|------|-----------------|-----------|--------------|
| capture | (automatic on child stop) | `capture_subagent_review` | ✓ |
| list | `subagent review list <parent_run_id>` | `list_subagent_reviews` | ✓ |
| **compare** | `subagent review compare` — diffstat + files-touched + cost per child | review artifacts | **add multi-child comparison view** |
| inspect | `subagent review show <review_id>` | `load_subagent_review` | ✓ (single) |
| dry-run | `subagent review check <review_id>` | `check_subagent_review` | ✓ |
| **select+apply** | apply one child's patch | `apply_subagent_review` | ✓ for one; **add reject-others** |
| **conflict** | patch no longer applies cleanly | `git apply` failure | **add conflict surface + 3-way resolve** |
| **record** | why this child won | `review-{run_id}.json` | **add rationale field + audit event** |
| cleanup | drop unselected worktrees/patches | `_isolation` | **add "reject closes the rest" cleanup** |

---

## Behavioral requirements

1. **Compare before choose.** The comparison view shows, per child:
   `files_changed`, `+ins/-del`, cost (from `RunResult.cost_cents`), status, and lineage
   — so the parent picks on evidence, not order. (Reuses the parallel-experiment
   `compare_branches` idea already in the TUI.)
2. **Apply is dry-run-gated.** `apply` runs `check` first; if it would conflict, it stops
   and surfaces the conflict rather than half-applying.
3. **Conflict path is explicit.** On a non-clean `git apply`, present the conflicting
   hunks and offer: rebase-the-patch, accept-ours, accept-theirs, or open the conflict
   resolver (the TUI already has a conflict mode — `o/t/n/p/a`).
4. **Reject is decisive and audited.** Selecting one child auto-marks the others
   `rejected`, records a rationale string, writes an audit event
   (`subagent_review_decided` with chosen review_id + reason), and cleans up the rest.
5. **Delegation accountability.** The parent run's audit lineage records which child's
   work was merged and why — closing the loop on "who did what" for unattended fan-out.

---

## Acceptance (the F-ECO-006 path + multi-child)

- `test_subagent_review_compare_multichild`: 3 children → comparison lists diffstat +
  cost + status for each.
- `test_subagent_review_apply_one_rejects_rest`: applying child B marks A and C
  `rejected` and cleans up their worktrees/patches.
- `test_subagent_review_conflict_surfaced`: a patch that no longer applies stops with a
  conflict report (no partial apply).
- `test_subagent_review_records_rationale`: the decision writes rationale + an audit
  event.
- `test_subagent_review_dry_run_gate`: `apply` refuses when `check` predicts a conflict.

## Open decisions

- **DQ-SUB-1:** Can the parent apply **multiple** non-overlapping child patches in one
  pass, or strictly one-winner? Recommendation: allow multiple if `check` shows no
  overlap; otherwise one-winner.
- **DQ-SUB-2:** Reuse the existing TUI conflict resolver (`o/t/n/p/a`) for patch
  conflicts, or a patch-specific resolver? Recommendation: reuse it for consistency.

## Non-goals

- Not automatic selection of the "best" child — the human/parent decides; the tool
  presents evidence (verification-bottleneck thesis: keep the human in the loop).
- Not a replacement for the approval queue (`_approval_queue.py`) — that gates
  destructive tools *during* child runs; this gates *merge* after.

## Cross-references

- Persona P-OPS/P-ML review steps: `daily-driver-persona-journey-maps-2026-06-01.md`.
- Conflict resolver: TUI `o/t/n/p/a` (`teaagent/tui/__init__.py`).
- Existing building blocks: `teaagent/subagents/_review.py`,
  `teaagent/cli/_handlers/agent_review.py`.
</content>
