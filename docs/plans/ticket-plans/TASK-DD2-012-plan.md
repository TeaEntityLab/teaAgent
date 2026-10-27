# TASK-DD2-012: Bound Failure-Card Matching

**Priority:** P2
**Status:** In Progress — partial (re-verified 2026-10-27): stopwords, a 2-shared-word threshold and `limit=3` bound matching, but `get_failure_warnings` injects `error_message`/`task_description` without truncation. No friction entry; held under DR-006
**Primary files:** `teaagent/memory/failure_card.py`, `teaagent/cli/_handlers/chat_commands.py`

## Problem

Failure-card matching can score raw word overlap, including common words, and then
inject prior error/task text into a new prompt. This can make unrelated failures sticky.

## Scope

- Add stopword filtering or stronger tokenization.
- Require a minimum relevance threshold.
- Bound and redact injected warning text.
- Add negative tests for unrelated tasks sharing common words.

## Acceptance criteria

- Unrelated tasks with common words do not receive failure-card warnings.
- Related failures still surface.
- Injected warning text is short and avoids sensitive raw dumps.

## Verification

```bash
python3 -m pytest tests -k failure_card
```

## Risks

- Too strict matching can hide helpful lessons.
- Too loose matching can bias daily tasks toward stale failures.
