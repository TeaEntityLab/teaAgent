# Dependency Audit Scope Refresh
# 2026-06-04

## Purpose

This note records the dependency-audit correction made after the security
workflow reported a `starlette` vulnerability while running
`pip-audit --skip-editable`.

The conclusion is not "ignore `starlette`." The conclusion is that dependency
audit results must be scoped before they are interpreted.

## Verified Facts

- TeaAgent's base package still declares no forced runtime dependencies:
  `project.dependencies = []`.
- `uv.lock` contains `google-adk`, `fastapi`, and `starlette` because
  `google-adk` is an optional extra and is also included in the broad `dev`
  extra.
- `uv export --format requirements-txt --no-dev --no-emit-project` produces an
  empty base requirement surface for the current lockfile.
- `uv export --format requirements-txt --extra managed-google-adk --no-dev
  --no-emit-project` includes `starlette==0.52.1` through `google-adk` and
  `fastapi`.
- Therefore, a `starlette` advisory is currently an optional-extra/dev finding,
  not evidence that the base TeaAgent install is vulnerable.

## CI Change

The security workflow now uses three lanes:

| Lane | Command shape | Blocking behavior |
| --- | --- | --- |
| Base | `uv export --no-dev --no-emit-project --frozen` then `pip-audit -r` | Blocks every PR/push. |
| Dev/lockfile | `uv export --no-emit-project --frozen` then `pip-audit -r` | Runs on the weekly schedule. |
| Optional extras | `uv export --extra <extra> --no-dev --no-emit-project --frozen` then `pip-audit -r` | Non-blocking outside release; release-review input. |

The old unscoped `pip-audit --skip-editable` workflow was removed because it
can audit packages installed in the runner or audit-tool environment rather
than the project surface being claimed.

## Risk Interpretation

Base risk:

- Low for this specific `starlette` finding because the base export does not
  contain it.

Optional-extra risk:

- High for `managed-google-adk` users if the advisory is exploitable through
  the web stack that `google-adk` pulls in.
- Release packaging that advertises managed Google ADK support must review this
  finding before release.

Process risk:

- Medium. If future docs collapse the lanes again, maintainers can either block
  base users on optional transitive CVEs or miss optional runtime exposure.

## Next Actions

1. For `managed-google-adk`, check whether an upstream `google-adk` or
   `fastapi` release can move to a non-vulnerable `starlette` version.
2. If not, document the advisory as optional-extra accepted risk with owner,
   mitigation, and release decision.
3. Keep the optional-extra matrix non-blocking for normal PRs but blocking in
   the release checklist for advertised extras with High/Critical CVEs.
4. Add release-note wording whenever an optional extra ships with a known lower
   severity dependency advisory.

## Validation Hooks

The docs validator now checks that:

- The security workflow uses a base export with `--no-dev --no-emit-project`.
- The security workflow includes `optional-extra-pip-audit`.
- The optional-extra job is non-blocking outside release.
- Unscoped `pip-audit --skip-editable` is not present.
