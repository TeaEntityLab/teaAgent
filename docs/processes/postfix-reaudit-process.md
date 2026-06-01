# Post-Fix Re-Audit Process

**Status:** Active process
**Frequency:** After any batch of fixes lands against a prior code-grounded review
**Owner:** TBD
**Last reviewed:** 2026-06-01

## Purpose

When a maintainer fixes findings from a code-grounded review, the review docs go stale
and the fixes themselves can introduce new defects or be only partially applied. This
process re-establishes ground truth without re-deriving the whole review, and reliably
catches the two most common post-fix failure modes:

1. **Partial application** — a fix lands on one surface/path but not its twin (the
   2026-06-01 case: `ChatSessionController` adopted by the REPL, not the TUI → CG-11/12/15).
2. **Masking tests** — a test passes because it injects the state it asserts, hiding the
   bug it appears to cover (CG-16).

## When to run

- The codebase changed since a `*-findings-*.md` or `*-review-*.md` doc was written.
- A PR claims to "fix" review findings.
- Before citing any review doc as current truth.

## Procedure

### 1. Re-anchor before trusting any prior claim
- `git log --oneline` and `git diff --stat <prior-review-point>..HEAD` to see what moved.
- For each finding, **re-grep the symbol, not the line number** — line numbers drift.
  Treat every `file:line` in old docs as a hint, not a fact, until re-confirmed.

### 2. Verify presence ≠ correctness
- A fix being *present* (a comment "CG-06 fix", a new function) does not mean it is
  *correct* or *complete*. Read the actual code region and confirm the behavior.
- For each "fixed" finding, write one sentence of evidence with a fresh `file:line`.

### 3. Check both surfaces / all paths
- For any shared-behavior fix, confirm **every** surface adopted it. Grep for the old
  direct call (e.g. `run_chat_agent(`) to find paths that bypass the new abstraction.
- A deprecation warning at call time is a strong signal a path was left un-migrated.

### 4. Audit the tests that "prove" the fix
- For each user-visible value, find the test that covers it and ask: *does it drive the
  production path, or inject the value and assert formatting?* Injection-only tests mask
  bugs (see `docs/analysis/daily-driver-test-integrity-audit-2026-06-01.md`).
- Run the suite; a green suite with a known live bug means coverage is the problem too.

### 5. Look for fixes that introduced new risk
- Test-detection logic in production paths (`except (AttributeError, TypeError): pass` to
  "detect mocks") can swallow real errors — flag it.
- Redundant artifacts left behind by a fix (e.g. a JSON `audit_trail` field superseded by
  a real audit event) — flag for cleanup; they mislead future readers.

### 6. Record the delta, don't rewrite the review
- Produce one *third-pass* doc that states: what is now FIXED (close it), what is NEW,
  and re-anchored evidence. Update the index, the recommendation log roll-up, and memory
  so the next session starts from current truth.
- Convert new findings into tickets with exact file:line and a falsifiable test name.

## Definition of done for a re-audit

- [ ] Every prior finding marked FIXED / STILL-OPEN / SHIFTED with fresh evidence.
- [ ] New findings have IDs, tickets, and named tests.
- [ ] At least one masking-test check performed on the changed surface.
- [ ] Index + memory updated to point at the current-truth doc.

## Example application

`docs/analysis/daily-driver-third-pass-postfix-audit-2026-06-01.md` is a worked instance
of this process: it closed CG-01/02/03(REPL)/04/06/07/09/10, opened CG-11…CG-16 (partial
application + masking test), and emitted TICKET-12…15.

## References
- ADR 0025 (ChatSessionController unification — the partially-applied fix this process caught).
- `docs/analysis/daily-driver-test-integrity-audit-2026-06-01.md` (step 4 detail).
- `docs/processes/opencode-gap-watch.md`, `community-presence.md` (sibling processes).
