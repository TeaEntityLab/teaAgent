# TASK-DD2-009: Fix ContextPack Read-Only Truth Label

**Priority:** P1
**Status:** Newly discovered
**Primary files:** `teaagent/context_pack.py`, `tests/*context*`

## Problem

`ContextPack.read_only` defaults to `True`, but `build_context_pack()` accepts a
`readonly` argument without passing it into the returned object. Serialized evidence can
therefore imply read-only behavior even when the builder was not called that way.

## Scope

- Decide whether `read_only` means artifact type or side-effect behavior.
- If it means side-effect behavior, pass the caller's `readonly` argument through.
- If it means artifact type, rename the field to avoid misleading evidence.
- Update tests and docs.

## Acceptance criteria

- `build_context_pack(readonly=False)` no longer serializes a misleading read-only label.
- Evidence docs define the field's meaning.
- Preflight/daily evidence does not overclaim no side effects.

## Verification

```bash
python3 -m pytest tests -k context_pack
```

## Risks

- Renaming can break consumers.
- Keeping the current label can undermine evidence-bundle trust.
