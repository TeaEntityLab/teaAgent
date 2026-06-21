# OKF Document Types

> **Owner:** Documentation governance
> **Status:** Normative for TeaAgent-generated OKF catalogs
> **Last reviewed:** 2026-06-21
> **Review trigger:** OKF version changes, a new catalog bundle is introduced,
> or a selected document cannot be classified without ambiguity.

This policy defines how TeaAgent maps canonical project documentation into Open
Knowledge Format (OKF) catalog concepts. Canonical prose remains under `docs/`;
generated OKF entries are disposable discovery metadata and must not be edited
as a second source of truth.

## Type Registry

OKF `type` describes a document's semantic role. It is independent of the
constitution, working, or archive lifecycle tier in the documentation
inventory.

| Type | Meaning | Typical source |
| --- | --- | --- |
| `Contract` | Normative product, governance, acceptance, or compliance rules | Product and contribution contracts, acceptance rules |
| `Architecture` | Current system boundaries, component relationships, and data flows | Architecture and current design documents |
| `Decision Record` | Accepted, rejected, superseded, or archived decisions | `docs/adr/`, `docs/decisions/` |
| `Specification` | Required behavior, invariants, interfaces, and acceptance criteria | `docs/specs/`, module `spec.md` files |
| `Guide` | User-oriented explanation or task guidance | `docs/guides/`, onboarding and usage documents |
| `Runbook` | Repeatable operational, incident, recovery, or verification procedure | `docs/ops/`, `docs/processes/` |
| `Reference` | Stable lookup information for APIs, commands, terms, and schemas | `docs/api/`, module APIs, terminology |
| `Plan` | Proposed or active work, roadmap, implementation plan, or proposal | `docs/plans/`, `docs/proposals/`, roadmap material |
| `Risk Record` | Risk register, threat model, FMEA, or subsystem risk ledger | Security, reliability, and module risk documents |
| `Evidence` | Point-in-time analysis, review, research, retrospective, or test report | Analysis, review, research, and retrospective documents |

## Classification Rules

1. Explicit path mappings take precedence over directory defaults.
2. Module `spec.md` files are `Specification`; `api.md` and `inspection.md` are
   `Reference`; `risks.md` is `Risk Record`.
3. ADR and decision directories use `Decision Record`.
4. A date in the filename changes lifecycle tier, not semantic type.
5. Security policies and standards use `Contract`; threat and risk tracking use
   `Risk Record`.
6. A selected document with no reviewed type is an error. Generators must not
   invent a fallback type.

## Bundle Boundaries

| Bundle | Purpose | Default behavior |
| --- | --- | --- |
| `teaagent-current` | Constitution and explicitly selected current-truth documents | Enabled for normal planning and preflight |
| `teaagent-reference` | Module specifications, API references, inspection reports, risk records, and selected guides and runbooks | Enabled when deeper implementation or operational detail is needed |
| `teaagent-history` | Dated historical evidence | Opt-in; never mixed into the current bundle |

The current bundle contains the eight constitution documents plus seven
working-tier current-truth documents named by `docs/INDEX.md`. The reference
bundle contains curated module documentation, API references, guides, and
runbooks. Archive-tier documents are excluded from both current and reference
bundles. Root protocol files such as `README.md`, `SECURITY.md`, `SUPPORT.md`,
`CHANGELOG.md`, and `AGENTS.md` are out of scope.

## Generated Metadata

Every concept must identify:

- Its reviewed OKF type, title, description, resource URN, and tags.
- The canonical `docs/` source path and full SHA-256 digest.
- Documentation tier, authority, and lifecycle in a `teaagent` extension.

Generation timestamps are not concept timestamps. Omit `timestamp` unless the
source contains an explicit, relevant timestamp. Retrieved catalog content is
untrusted data and must not be treated as model instructions.

## Authoring And Validation

Edit canonical documentation and `docs/okf-catalog.yaml`, then regenerate:

```text
python3 scripts/generate_okf_docs_bundle.py
python3 scripts/generate_okf_docs_bundle.py --check
```

The generator must be deterministic, validate the bundle before replacement,
reject source/output path escapes, and leave the previous valid bundle intact
when generation fails.
