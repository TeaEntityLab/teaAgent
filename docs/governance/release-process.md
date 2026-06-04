# Release Process

---

## Versioning

TeaAgent uses **Semantic Versioning 2.0** (`MAJOR.MINOR.PATCH`). The version in `pyproject.toml` is the single source of truth. Release tags are `v{MAJOR}.{MINOR}.{PATCH}`.

| Bump | When |
|---|---|
| `PATCH` | Bug fix with no API, schema, or audit-format change |
| `MINOR` | New backwards-compatible capability |
| `MAJOR` | Breaking change to public API, tool schema, audit format, or permission model |

A `MAJOR` bump requires a merged ADR before the release tag is created.

---

## Changelog format

`CHANGELOG.md` follows the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) convention.

```markdown
## Unreleased

- **<Feature group>**: one-line description. Module affected.

## [0.2.0] — 2026-MM-DD

### Added
- ...

### Fixed
- ...

### Security
- ...

### Breaking
- ...
```

Every PR that changes observable behaviour adds one entry under `## Unreleased`. Security fixes use the `### Security` subsection. Breaking changes use `### Breaking` and must include a migration note.

---

## Pre-release checklist

Run these steps in order before creating the release tag. Each step must pass before proceeding to the next.

### 1 — CI green on `main`

All blocking CI jobs must be green on the commit you intend to tag:

- `lint` (ruff + mypy + format)
- `test` (3.10, 3.11, 3.12, ≥ 75% coverage)
- `test-telemetry`
- `governance-gate`
- `acceptance-p0`
- `acceptance-p1`
- `acceptance-all`
- `package`
- Security `pip-audit` (base gate, dev/lockfile visibility, optional-extra review)
- Security `codeql`

### 2 — Competitive landscape hygiene

```bash
python3 scripts/refresh_competitive_docs.py --check
```

If the check reports drift, regenerate:

```bash
python3 scripts/refresh_competitive_docs.py
```

Confirm `Last reviewed:` date is updated in the survey artifact.

### 3 — Docs consistency

```bash
./scripts/verify_docs.sh
python3 scripts/validate_docs_consistency.py
python3 -m pytest tests/acceptance/test_provider_matrix_consistency_flow.py -q
```

Confirm `docs/acceptance.md` count matches `--collect-only` output:

```bash
python3 -m pytest tests/acceptance --collect-only -q | tail -5
```

### 4 — Version bump

Update `version` in `pyproject.toml`. Do not update any other file — version is read from `pyproject.toml` at import time.

```python
# pyproject.toml
[project]
version = "0.2.0"
```

### 5 — Changelog promotion

Move `## Unreleased` entries to a new versioned section:

```markdown
## [0.2.0] — 2026-MM-DD
```

Add the new `## Unreleased` header above it.

### 6 — Commit and tag

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "chore: release v0.2.0"
git tag -s v0.2.0 -m "Release v0.2.0"
git push origin main --tags
```

Signed tags (`-s`) are required for releases. Use the maintainer's GPG key.

### 7 — GitHub Release

Create a GitHub Release from the tag. Copy the relevant changelog section into the release notes. The `release.yml` workflow will:

1. Build wheel and sdist.
2. Check distributions with `twine check`.
3. Publish to PyPI via OIDC trusted publishing (no API key stored in CI).
4. Attest build provenance via `actions/attest-build-provenance`.

---

## Hotfix process

For critical security or correctness fixes:

1. Branch from the release tag: `git checkout -b security/CVE-XXXX-YYYY v0.1.3`.
2. Apply the minimal fix. Add a regression test.
3. Bump `PATCH`, update changelog with a `### Security` entry.
4. Open a PR targeting `main` (and optionally the release branch if long-lived).
5. Require 2 approvals (security fix rule).
6. Merge to `main` first, then backport if needed.
7. Tag from `main` after merge.

---

## Deprecation policy

1. A feature to be removed must be marked deprecated in a `MINOR` release with a deprecation notice in the changelog and (where applicable) a runtime warning via `warnings.warn(..., DeprecationWarning, stacklevel=2)`.
2. The removal may not happen until the next `MAJOR` release and must be documented in the `### Breaking` changelog section of that release.
3. There is no minimum deprecation window enforced by tooling; maintainers should allow at least one release cycle for users to adapt.

---

## PyPI and attestation

Releases are published to PyPI via [OIDC trusted publishing](https://docs.pypi.org/trusted-publishers/) — no API key is stored in CI secrets. The `pypi` GitHub Environment controls which tags can trigger publication.

Build provenance is attested via `actions/attest-build-provenance@v4` and can be verified by consumers:

```bash
gh attestation verify teaagent-0.2.0-py3-none-any.whl \
  --repo TeaEntityLab/teaAgent
```
