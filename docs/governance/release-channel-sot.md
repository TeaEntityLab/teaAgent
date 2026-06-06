# Release Channel Source of Truth

> **Claim class:** Governance rule
> **Owner:** Release maintainer
> **Last reviewed:** 2026-06-06
> **Review trigger:** Addition, removal, or policy change for any release channel.
> **References:** [release-process.md](release-process.md), [daily-driver-release-gates-2026-06-02.md](daily-driver-release-gates-2026-06-02.md)

This document is the single source of truth for TeaAgent release channels. Any automation, CI pipeline, or external integration that publishes or redistributes TeaAgent artifacts must reference this definition. Deviations from the stability guarantees, signing methods, or update cadence defined here require an ADR.

---

## Canonical Release Channels

| # | Channel | Purpose | Primary consumer | Stability guarantee | Update cadence | Signing / attestation |
|---|---------|---------|------------------|---------------------|----------------|----------------------|
| 1 | **PyPI** (`pip install teaagent`) | Standard distribution for end users and downstream packages | Solo CLI users, team operators, CI/CD pipelines | SemVer 2.0 — same as git tag; no pre-release artifacts published | Per git tag (`vX.Y.Z`) | OIDC trusted publishing (no API key in CI); `actions/attest-build-provenance@v4`; `gh attestation verify` supported |
| 2 | **GitHub Releases** (`https://github.com/TeaEntityLab/teaAgent/releases`) | Human-readable release notes, release artifact archive, and attestation provenance | Security reviewers, forensic auditors, compliance scans | Tag-anchored; release body mirrors CHANGELOG.md section | Per git tag | GPG-signed annotated tag (`git tag -s`); GitHub Release body + `.whl`/`.tar.gz` assets |
| 3 | **Source install** (`pip install -e .`) | Development, editable install, local forks | Contributors, plugin authors, early adopters | `main` branch — CI-green only; no stability guarantee beyond CI gate | Continuous (every merge to `main`) | Git commit SHA; verified via CI status badge on `main` |
| 4 | **GitHub source archive** (`https://github.com/TeaEntityLab/teaAgent/archive/refs/tags/vX.Y.Z.tar.gz`) | Reproducible build from source tarball | Package maintainers (e.g. Homebrew, Linux distros), offline air-gapped deployments | Byte-for-byte reproducible from tag | Per git tag | GitHub auto-generated tarball from signed tag; checksum available via `gh release download --archive=tar.gz` |
| 5 | **Wheel from CI artifacts** (GitHub Actions run artifacts) | Pre-release verification, downstream integration testing, CI consumption | CI pipelines of dependent projects, acceptance test runners | Ephemeral — may be pruned by GitHub's 90-day artifact retention; no stability claim | Per CI run on `main` and PR branches | GitHub Actions run ID + workflow provenance; not signed (CI-internal only) |

---

## Channel Details

### 1. PyPI — Primary Distribution Channel

- **Identifier:** `pip install teaagent` (or `pip install teaagent==X.Y.Z`)
- **Purpose:** Standard Python packaging for all users. This is the recommended installation method for any non-development use.
- **Stability:** Every PyPI release passes the full [pre-release checklist](release-process.md#pre-release-checklist). No pre-release, alpha, beta, or dev versions are published to PyPI. Every published version is a tagged release from `main`.
- **Attestation model:** Publishing uses [OIDC trusted publishing](https://docs.pypi.org/trusted-publishers/) — the `pypi` GitHub Environment controls which tags can trigger publication. No long-lived API key is stored in CI secrets. Build provenance is attested via `actions/attest-build-provenance@v4`.
- **Verification command:**
  ```bash
  gh attestation verify teaagent-X.Y.Z-py3-none-any.whl \
    --repo TeaEntityLab/teaAgent
  ```
- **CI pipeline reference:** `.github/workflows/release.yml` (triggered by `v*` tag push)

### 2. GitHub Releases — Human-Facing Distribution

- **Identifier:** `https://github.com/TeaEntityLab/teaAgent/releases/tag/vX.Y.Z`
- **Purpose:** Official release announcement, changelog body, and archive store. This channel is the authoritative source for release notes. The `.whl` and `.tar.gz` artifacts attached here are the same artifacts published to PyPI.
- **Stability:** Identical to PyPI; same release artifacts. The GitHub Release is created as part of the `release.yml` workflow.
- **Attestation model:** The release tag must be GPG-signed by a maintainer (`git tag -s vX.Y.Z -m "Release vX.Y.Z"`). GitHub's tag verification badge confirms maintainer signature.
- **CI pipeline reference:** `.github/workflows/release.yml` (creates the release, uploads artifacts)

### 3. Source Install — Development Channel

- **Identifier:** `pip install -e .` from a clone of the repository
- **Purpose:** Development, editable install for contributors, local experimentation. This is the channel for running tests, iterating on the codebase, and verifying unreleased changes.
- **Stability:** No stability guarantee. `main` is assumed to always be CI-green, but unreleased commits may contain breaking changes, experimental features, or incomplete mitigations. Users who need stability must pin to a release tag.
- **Attestation model:** None beyond git commit SHA. Trust is derived from the repository source, CI status, and code review.
- **CI pipeline reference:** `.github/workflows/ci.yml` (runs on every push to `main` and every PR)

### 4. GitHub Source Archive — Reproducible Build Channel

- **Identifier:** `https://github.com/TeaEntityLab/teaAgent/archive/refs/tags/vX.Y.Z.tar.gz`
- **Purpose:** Reproducible build from a signed tag for downstream packagers (Homebrew, Linux distributions), air-gapped deployments, and compliance-controlled environments.
- **Stability:** Byte-for-byte identical to the tagged commit. Since tags are immutable and GPG-signed, the archive content is verifiable.
- **Attestation model:** GitHub auto-generates the archive from the signed tag. SHA-256 checksum can be obtained from the GitHub Release assets or via `gh release download`.
- **CI pipeline reference:** None (GitHub generates the archive automatically from the tag)

### 5. CI Artifact Wheel — Pre-Release Verification Channel

- **Identifier:** GitHub Actions run artifacts (e.g., `artifact-teaagent-py3-none-any.whl`)
- **Purpose:** Pre-release validation by downstream CI pipelines, integration test harnesses, and acceptance test runners that need to test against the latest `main` or a specific PR before a release tag is cut.
- **Stability:** Ephemeral. GitHub retains artifacts for 90 days by default. These artifacts are not cryptographically signed and carry no stability claim. They must never be distributed to end users.
- **Attestation model:** GitHub Actions run provenance only. The artifact is downloadable only by authenticated users with repository access.
- **CI pipeline reference:** `.github/workflows/ci.yml` (upload-artifact step)

---

## Non-Channels (Explicitly Not Supported)

These distribution methods must not be represented as TeaAgent release channels:

| Method | Why not a channel |
|--------|-------------------|
| `brew install teaagent` | No Homebrew formula exists; not maintained by the TeaEntityLab org. May be added in future — requires an ADR and dedicated CI pipeline. |
| Docker Hub / `docker pull` | No official TeaAgent Docker image is published. Docker is used as a subagent isolation backend, not as a distribution channel. |
| `npm install teaagent` | TeaAgent is a Python project only. There is no JavaScript/Node.js distribution. |
| Conda / conda-forge | Not maintained. A community-contributed `conda-forge` recipe would require explicit maintainer approval and CI integration. |
| PyPI pre-release (`--pre`) | No alpha/beta/rc versions are published to PyPI. If pre-release publishing is introduced, it must be defined as a new channel in this document first. |

---

## Channel Selection Guide

| Use case | Recommended channel |
|----------|---------------------|
| I want to use TeaAgent as a tool | PyPI (`pip install teaagent`) |
| I want to read the changelog for a release | GitHub Releases |
| I want to contribute code or run tests | Source install (`pip install -e .`) |
| I want to package TeaAgent for a Linux distro | GitHub source archive |
| I want to test my downstream tool against the latest `main` | CI artifact wheel |
| I want to verify a release artifact's provenance | PyPI wheel + `gh attestation verify` |

---

## Governance

- **Additions or removals** of a release channel require an ADR and an update to this document.
- **Policy changes** (e.g., changing signing method, dropping OIDC, adding pre-release publishing) require an ADR and a corresponding CI pipeline change.
- **Compliance** with the channel definitions in this document is verified by:
  - `governance-gate` CI job (validates that the release process matches this definition)
  - `release.yml` workflow (enforces OIDC, attestation, and tag-signing requirements)
  - Manual maintainer review before each release tag

Cross-reference with:
- [Release Process](release-process.md) — step-by-step release checklist
- [Daily-Driver Release Gates](daily-driver-release-gates-2026-06-02.md) — gates for TUI/chat/agent changes
- [Compliance Checklist](compliance-checklist.md) — release gates, deployment gates, sign-off
- [Documentation Operating Model](documentation-operating-model-2026-06-04.md) — claim classes and evidence hierarchy
