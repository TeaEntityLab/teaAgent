# Daily-Driver Thought Log
# 2026-06-02

This is a plain-language thought log for the current docs expansion. It records advice,
reclassification, and risk reasoning that may otherwise be lost between ticket files.

## TL-001: More docs are useful only when they reduce ambiguity

The docs package is already deep. New docs should either guide a daily user, create a
ticket, define a contract, or preserve a newly discovered risk.

## TL-002: The working tree improved, so stale bug language must soften

Chat positional task forwarding and TUI cost accumulation appear partially patched.
Docs should say verify/close rather than keep claiming pure absence.

## TL-003: Root correctness should precede most fixes

If the TUI can operate in the wrong root, every later task can be correct in the wrong
workspace. Root state is therefore first in the June 2 sequence.

## TL-004: False zero is worse than unknown

For spend, a blank or unknown state invites checking. A zero invites trust.

## TL-005: Approval scope is product UX, not just security plumbing

The user experience of approval is the security model. If users cannot understand the
scope, the approval is not meaningful.

## TL-006: Dry-run side effects are a daily-driver trust issue

Creating `.teaagent` during dry-run may be technically harmless, but the surprise matters.
Either avoid it or announce it.

## TL-007: Evidence labels need semantic precision

`read_only: true` can be read as "this operation did not write." If the field means
"this object is an evidence pack," rename or document it.

## TL-008: Local state corruption should be noisy

Daily cockpit output should show degraded health when memory or run-store files are
corrupt. Clean silence is misleading.

## TL-009: Memory relevance needs negative tests

Failure cards are valuable only when relevant. Raw common-word matching needs guardrails
so yesterday's failure does not bias today's unrelated task.

## TL-010: Parallel review worked

The writer lane produced operator guide proposals, the planner lane reclassified partial
fixes and sequencing, and the reviewer lane surfaced five new risk items. The merged
docs now separate user guidance, specs, risk logs, and tickets.
