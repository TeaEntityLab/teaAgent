# Dependabot alert #10 — CVE-2026-23949 (`jaraco.context`)

## Status: fixed on `main` (dismiss in GitHub UI)

| Check | Result |
|-------|--------|
| `uv.lock` | `jaraco-context` **6.1.2** |
| Constraint | `pyproject.toml` → `[tool.uv] constraint-dependencies` → `>=6.1.0` |
| Selftest | `teaagent selftest` → `jaraco_context.ok: true` when installed |

## Dismiss (maintainer)

GitHub → **Security** → **Dependabot** → alert **#10** → **Close as fixed**

Reason: *Vulnerability is patched in default branch (jaraco-context 6.1.2).*

Or with authenticated `gh`:

```bash
gh api -X PATCH repos/TeaEntityLab/teaAgent/dependabot/alerts/10 \
  -f state=fixed \
  -f dismissed_reason=fix_started \
  -f dismissed_comment='uv.lock pins jaraco-context 6.1.2 (>=6.1.0)'
```
