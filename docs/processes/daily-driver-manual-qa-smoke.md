# Daily-Driver Manual QA Smoke Checklist

**Status:** Active checklist
**Frequency:** Before any release touching chat/TUI/agent surfaces, and after each
daily-driver ticket lands
**Last reviewed:** 2026-06-01

## Purpose

CI can pass while a live interactive bug exists (CG-11 masked by CG-16; CG-12 masked by
CG-17). This checklist is the human backstop: concrete, observable steps a person runs in
a real terminal to confirm each finding's behavior. Each step says what to do and the
**expected** result; a deviation is a regression.

Run in a scratch git repo with at least one committed file. Use a cheap/stub model.

---

## A. `teaagent chat` (CLI REPL)

1. **Result handling (CG-01).** Run a trivial task ("say hello").
   - ✅ Expect: the answer prints; no "Task failed". ❌ Regression: "failed"/no answer.
2. **Cost accuracy (CG-03).** Run two tasks, then `/cost`.
   - ✅ Expect: a non-zero dollar amount that grew between tasks. ❌: `$0.00` or `+10`.
3. **Undo scope (CG-02).** Manually edit committed file A. Run a task that edits file B.
   `/undo`.
   - ✅ Expect: B reverted, **A's manual edit preserved**. ❌: A also reverted (data loss).
4. **Undo empty (CG-02).** Fresh session, `/undo` with nothing to undo.
   - ✅ Expect: "Nothing to undo". ❌: a destructive git operation.
5. **Compaction (CG-04).** Run several tasks, `/compact`.
   - ✅ Expect: counts reflect real prior turns. ❌: "0 → 0".
6. **Suspend honesty (CG-09/10).** `/background`. Note the run id. `git branch`.
   - ✅ Expect: still on your original branch; message says "suspension checkpoint, not
     background execution"; an audit event recorded. ❌: branch switched silently.

## B. `teaagent tui`

7. **No scrollback wipe (CG-06).** Resize to ≥120×30, submit several prompts.
   - ✅ Expect: history stays visible. ❌: screen clears each prompt.
8. **TUI cost (CG-11 — currently FAILING).** Run a task, `/cost`.
   - ✅ Target after TICKET-12: real non-zero cost. ⚠️ Today: shows `$0.00` (known issue —
     see `docs/daily-driver-known-issues-2026-06-01.md`).
9. **TUI undo (CG-15).** Same A/B edit test as step 3, via the TUI `/undo`.
   - Note which mechanism ran (git-stash today). After TICKET-12: journal-based, A preserved.
10. **Compact (CG-07).** With an active chat session, `compact`.
    - ✅ Expect: "session compacted (N → M messages)". ❌: stub/no-op.

## C. Agent mode & suspend→resume (AG-01…04 — currently BROKEN)

11. **Resume round-trip (AG-01).** From step 6's run id: `teaagent resume <id>`.
    - ✅ Target after TICKET-16: session rehydrates. ⚠️ Today: errors `{status:error}`.
12. **Background misuse (AG-02).** `teaagent agent run --background <id>`.
    - ⚠️ Today: starts a NEW run with the id as the literal task — **do not rely on this to
      resume**. After TICKET-16: errors with "did you mean `agent resume`?".
13. **Review path (AG-03, works).** `teaagent agent interactive-review <id>`.
    - ✅ Expect: lists changed files with y/e/r/n/q review commands.
14. **Governance (verified solid).** Resume a run with a pending approval but no
    `--approve-call-id`.
    - ✅ Expect: refuses to auto-approve legacy/redacted calls; asks for explicit approval.

---

## Pass/fail recording

For each step record: PASS / FAIL / KNOWN-ISSUE (with ticket). A release is blocked on any
**FAIL** in steps 1–7, 10, 13, 14 (the currently-correct behaviors). Steps 8, 9, 11, 12
are KNOWN-ISSUE until their tickets land — they must not *newly* fail in a way worse than
documented.

## Cross-references
- What each step guards: `daily-driver-findings-status-ledger-2026-06-01.md`.
- User-facing version of the known issues: `docs/daily-driver-known-issues-2026-06-01.md`.
- Automated counterparts: `daily-driver-acceptance-test-catalog-2026-06-01.md`.
