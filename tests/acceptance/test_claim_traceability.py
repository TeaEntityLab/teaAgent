"""W12: Claim-to-test traceability — drift detection gate.

Validates that docs/architecture/claim-to-test-traceability.yaml is self-consistent:
- Every claim has at least one acceptance_test reference.
- Every acceptance_test referenced exists on disk.
- No claim with status "shipping" has a null or missing acceptance_tests list.
- The YAML is parseable and contains all top-10 claim IDs.

If this test fails, a product claim has lost its evidence reference. Fix by either:
  a) Adding/restoring the acceptance test, or
  b) Downgrading the claim status to "roadmap" in the YAML.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_REPO = Path(__file__).resolve().parents[2]
_MATRIX_YAML = _REPO / 'docs' / 'architecture' / 'claim-to-test-traceability.yaml'
_REQUIRED_CLAIM_IDS = {f'C{i}' for i in range(1, 11)}


def _load_matrix() -> dict:
    assert _MATRIX_YAML.exists(), (
        f'Missing traceability matrix: {_MATRIX_YAML}\n'
        'Run W12 deliverable generation or restore the file from git.'
    )
    with _MATRIX_YAML.open(encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def test_matrix_yaml_is_parseable_and_has_required_structure() -> None:
    data = _load_matrix()
    assert 'claims' in data, "matrix YAML missing top-level 'claims' key"
    assert 'version' in data, "matrix YAML missing 'version' key"
    assert isinstance(data['claims'], list), "'claims' must be a list"
    assert len(data['claims']) >= 10, 'matrix must contain at least 10 claims'


def test_all_top10_claim_ids_present() -> None:
    data = _load_matrix()
    found_ids = {c['id'] for c in data['claims']}
    missing = _REQUIRED_CLAIM_IDS - found_ids
    assert not missing, (
        f'Missing claim IDs in traceability matrix: {sorted(missing)}\n'
        'Each of C1–C10 must have an entry in claim-to-test-traceability.yaml.'
    )


def test_all_top10_claims_have_acceptance_test_reference() -> None:
    data = _load_matrix()
    top10 = {c['id']: c for c in data['claims'] if c['id'] in _REQUIRED_CLAIM_IDS}
    failures = []
    for claim_id, claim in sorted(top10.items()):
        tests = claim.get('acceptance_tests') or []
        if not tests:
            failures.append(
                f'{claim_id} ({claim["name"]}): no acceptance_tests listed — '
                "add a test reference or set status to 'roadmap'"
            )
    assert not failures, 'Claims without acceptance test references:\n' + '\n'.join(
        failures
    )


def test_no_shipping_claim_lacks_acceptance_test_reference() -> None:
    data = _load_matrix()
    failures = []
    for claim in data['claims']:
        if claim.get('status') != 'shipping':
            continue
        tests = claim.get('acceptance_tests') or []
        if not tests:
            failures.append(
                f'{claim["id"]} ({claim["name"]}): status=shipping but no acceptance_tests — '
                "downgrade to 'experimental' or 'roadmap', or add a test reference"
            )
    assert not failures, (
        'Shipping claims without test references (receipt required before rhetoric):\n'
        + '\n'.join(failures)
    )


def test_no_shipping_claim_references_nonexistent_test_file() -> None:
    data = _load_matrix()
    failures = []
    for claim in data['claims']:
        if claim.get('status') != 'shipping':
            continue
        for test_path in claim.get('acceptance_tests') or []:
            full = _REPO / test_path
            if not full.exists():
                failures.append(
                    f"{claim['id']} ({claim['name']}): references missing file '{test_path}'"
                )
    assert not failures, (
        'Shipping claims reference test files that do not exist:\n'
        + '\n'.join(failures)
        + '\nEither restore the file or downgrade claim status to roadmap.'
    )


def test_experimental_claims_have_gap_documented() -> None:
    data = _load_matrix()
    failures = []
    for claim in data['claims']:
        if claim.get('status') not in ('experimental', 'roadmap'):
            continue
        gap = claim.get('gap') or ''
        if not gap.strip():
            failures.append(
                f"{claim['id']} ({claim['name']}): status={claim['status']} but no 'gap' "
                'description — document what test/evidence is needed'
            )
    assert not failures, (
        'Experimental/roadmap claims missing gap documentation:\n' + '\n'.join(failures)
    )


def test_each_claim_has_evidence_command_or_explicit_gap() -> None:
    data = _load_matrix()
    top10 = {c['id']: c for c in data['claims'] if c['id'] in _REQUIRED_CLAIM_IDS}
    failures = []
    for claim_id, claim in sorted(top10.items()):
        has_command = bool((claim.get('evidence_command') or '').strip())
        has_gap = bool((claim.get('gap') or '').strip())
        if not has_command and not has_gap:
            failures.append(
                f'{claim_id} ({claim["name"]}): neither evidence_command nor gap is set — '
                'every claim must be verifiable or explicitly deferred'
            )
    assert not failures, (
        'Claims with neither evidence command nor gap note:\n' + '\n'.join(failures)
    )


@pytest.mark.parametrize(
    'claim',
    [
        c
        for c in _load_matrix()['claims']
        if c.get('status') == 'shipping' and c['id'] in _REQUIRED_CLAIM_IDS
    ],
)
def test_shipping_claim_test_files_all_exist(claim: dict) -> None:
    missing = [
        t for t in (claim.get('acceptance_tests') or []) if not (_REPO / t).exists()
    ]
    assert not missing, (
        f'Claim {claim["id"]} ({claim["name"]}) references non-existent test files: '
        f"{missing}\nRestore the files or downgrade status to 'roadmap'."
    )
