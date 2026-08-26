from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
_VALIDATE_SCRIPT = _SCRIPTS / 'validate_docs_consistency.py'
_TIER_SCRIPT = _SCRIPTS / 'run_acceptance_tier.py'

_VALIDATE_SPEC = spec_from_file_location('validate_docs_consistency', _VALIDATE_SCRIPT)
assert _VALIDATE_SPEC and _VALIDATE_SPEC.loader
_VALIDATE_MODULE = module_from_spec(_VALIDATE_SPEC)
_VALIDATE_SPEC.loader.exec_module(_VALIDATE_MODULE)
validate_docs_consistency = _VALIDATE_MODULE.validate_docs_consistency

_TIER_SPEC = spec_from_file_location('run_acceptance_tier', _TIER_SCRIPT)
assert _TIER_SPEC and _TIER_SPEC.loader
_TIER_MODULE = module_from_spec(_TIER_SPEC)
_TIER_SPEC.loader.exec_module(_TIER_MODULE)
render_tier_markdown = _TIER_MODULE.render_tier_markdown


def test_validate_docs_consistency_passes_when_inputs_match(tmp_path: Path) -> None:
    readme = tmp_path / 'README.md'
    acceptance = tmp_path / 'acceptance.md'
    matrix = tmp_path / 'matrix.md'
    roadmap = tmp_path / 'roadmap-status.md'
    acceptance_dir = tmp_path / 'acceptance_tests'
    acceptance_dir.mkdir()
    (acceptance_dir / 'test_a.py').write_text(
        'def test_a():\n    assert True\n', encoding='utf-8'
    )
    (acceptance_dir / 'test_b.py').write_text(
        'def test_b():\n    assert True\n', encoding='utf-8'
    )

    readme.write_text(
        'owner-operator\n(2 providers)\nexport A_API_KEY=\nexport B_API_KEY=\n',
        encoding='utf-8',
    )
    tier_block = render_tier_markdown()
    acceptance.write_text(
        '`2 passed`\n'
        '<!-- ACCEPTANCE_TIERS:START -->\n\n'
        f'{tier_block}\n\n'
        '<!-- ACCEPTANCE_TIERS:END -->\n',
        encoding='utf-8',
    )
    matrix.write_text('| Use Case | Covered |\n| yes |\n', encoding='utf-8')
    roadmap.write_text(
        '# Roadmap Status\n\n'
        'owner-operator\n'
        '| H0 | Claim and risk hygiene | documentation-current-truth |\n'
        'doc-vs-HEAD guard\n',
        encoding='utf-8',
    )

    errors = validate_docs_consistency(
        readme_path=readme,
        acceptance_doc_path=acceptance,
        use_case_matrix_path=matrix,
        acceptance_tests_dir=acceptance_dir,
        roadmap_status_path=roadmap,
        check_providers=False,
        check_survey=False,
        check_mode_matrix=False,
        check_surface_recipes=False,
        check_catalog=False,
        check_repo_governance=False,
    )
    assert errors == []


def test_validate_docs_consistency_detects_mismatch(tmp_path: Path) -> None:
    readme = tmp_path / 'README.md'
    acceptance = tmp_path / 'acceptance.md'
    matrix = tmp_path / 'matrix.md'
    acceptance_dir = tmp_path / 'acceptance_tests'
    acceptance_dir.mkdir()
    (acceptance_dir / 'test_a.py').write_text(
        'def test_a():\n    assert True\n', encoding='utf-8'
    )

    readme.write_text(
        'owner-operator\n(3 providers)\nexport A_API_KEY=\n', encoding='utf-8'
    )
    acceptance.write_text(
        '`2 passed`\n<!-- ACCEPTANCE_TIERS:START -->\nwrong\n<!-- ACCEPTANCE_TIERS:END -->',
        encoding='utf-8',
    )
    matrix.write_text('| x | no |', encoding='utf-8')

    errors = validate_docs_consistency(
        readme_path=readme,
        acceptance_doc_path=acceptance,
        use_case_matrix_path=matrix,
        acceptance_tests_dir=acceptance_dir,
        check_providers=False,
        check_survey=False,
        check_mode_matrix=False,
        check_surface_recipes=False,
        check_repo_governance=False,
    )
    assert len(errors) == 3  # status, tier sync, uncovered matrix row


def test_validate_inline_todo_catalog_detects_source_drift(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / 'teaagent').mkdir()
    (repo / 'scripts').mkdir()
    (repo / 'teaagent' / 'module.py').write_text(
        '# TODO: wire the real implementation\n', encoding='utf-8'
    )
    (repo / 'scripts' / 'script.py').write_text('print("ok")\n', encoding='utf-8')

    catalog = (
        '| Category | Count |\n'
        '|----------|-------|\n'
        '| Explicit `# TODO` in production (`teaagent/`) | 0 |\n'
        '| Explicit `# TODO` in scripts (unfixed stubs) | 0 |\n'
    )

    errors = _VALIDATE_MODULE.validate_inline_todo_catalog(catalog, repo_root=repo)

    assert errors == [
        'Inline TODO catalog mismatch for Explicit `# TODO` in production (`teaagent/`): '
        'catalog says 0, source scan found 1.'
    ]


def test_validate_inline_todo_catalog_passes_when_counts_match(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / 'teaagent').mkdir()
    (repo / 'scripts').mkdir()
    (repo / 'teaagent' / 'module.py').write_text(
        '# TODO: wire the real implementation\n', encoding='utf-8'
    )
    (repo / 'scripts' / 'script.py').write_text(
        '# FIXME: replace scaffolding\n', encoding='utf-8'
    )

    catalog = (
        '| Category | Count |\n'
        '|----------|-------|\n'
        '| Explicit `# TODO` in production (`teaagent/`) | 1 |\n'
        '| Explicit `# TODO` in scripts (unfixed stubs) | 1 |\n'
    )

    errors = _VALIDATE_MODULE.validate_inline_todo_catalog(catalog, repo_root=repo)

    assert errors == []


def test_validate_provider_docs_consistency_passes_for_repo_docs() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / 'README.md').read_text(encoding='utf-8')
    architecture = (root / 'docs' / 'architecture.md').read_text(encoding='utf-8')
    usage = (root / 'docs' / 'USAGE.md').read_text(encoding='utf-8')
    errors = _VALIDATE_MODULE.validate_provider_docs_consistency(
        readme_text=readme,
        architecture_text=architecture,
        usage_text=usage,
    )
    assert errors == []


def test_validate_plugin_skill_catalog_passes_for_repo_catalog() -> None:
    root = Path(__file__).resolve().parents[1]
    catalog = (root / 'docs' / 'plugin-skill-catalog.md').read_text(encoding='utf-8')
    errors = _VALIDATE_MODULE.validate_plugin_skill_catalog(catalog, repo_root=root)
    assert errors == []


def test_validate_survey_doc_passes_for_repo_survey() -> None:
    root = Path(__file__).resolve().parents[1]
    survey = (root / 'scripts' / 'refresh_agent_readme_survey.md').read_text(
        encoding='utf-8'
    )
    errors = _VALIDATE_MODULE.validate_survey_doc(survey)
    assert errors == []


def test_validate_mode_safety_matrix_passes_for_repo_usage() -> None:
    root = Path(__file__).resolve().parents[1]
    usage = (root / 'docs' / 'USAGE.md').read_text(encoding='utf-8')
    errors = _VALIDATE_MODULE.validate_mode_safety_matrix(usage)
    assert errors == []


def test_validate_surface_recipes_passes_for_repo_usage() -> None:
    root = Path(__file__).resolve().parents[1]
    usage = (root / 'docs' / 'USAGE.md').read_text(encoding='utf-8')
    errors = _VALIDATE_MODULE.validate_surface_recipes(usage)
    assert errors == []


def test_validate_roadmap_status_passes_for_repo_roadmap() -> None:
    root = Path(__file__).resolve().parents[1]
    roadmap = (root / 'docs' / 'roadmap-status.md').read_text(encoding='utf-8')
    errors = _VALIDATE_MODULE.validate_roadmap_status(roadmap)
    assert errors == []


def test_validate_operator_friction_log_passes_for_repo_log() -> None:
    root = Path(__file__).resolve().parents[1]
    log = (root / 'docs' / 'work-log' / 'operator-friction-log.md').read_text(
        encoding='utf-8'
    )
    errors = _VALIDATE_MODULE.validate_operator_friction_log(log)
    assert errors == []


def test_validate_operator_friction_log_detects_closed_without_links() -> None:
    log = (
        '# Operator Friction Log\n\n'
        '## Owner Evidence Entries\n\n'
        '### 2026-06-14 - Missing closeout\n\n'
        '- **Type:** evidence\n'
        '- **Source:** owner real use\n'
        '- **Status:** closed\n'
        '- **Closure evidence:** n/a\n'
        '- **Promoted to:** n/a\n'
    )
    errors = _VALIDATE_MODULE.validate_operator_friction_log(log)
    assert any('Closure evidence' in err for err in errors)
    assert any('promoted ticket or acceptance-gap artifact' in err for err in errors)


def test_validate_operator_friction_log_rejects_closed_hypothesis() -> None:
    log = (
        '# Operator Friction Log\n\n'
        '## Competitor-Derived Hypotheses\n\n'
        '### 2026-06-14 - Competitor clue\n\n'
        '- **Type:** hypothesis\n'
        '- **Source:** [hypothesis: example, 2026-06-14]\n'
        '- **Status:** closed\n'
        '- **Closure evidence:** tests/test_example.py\n'
        '- **Promoted to:** docs/work-log/example-ticket.md\n'
    )
    errors = _VALIDATE_MODULE.validate_operator_friction_log(log)
    assert any(
        'hypothesis entry' in err and 'cannot be marked closed' in err for err in errors
    )


def test_validate_operator_friction_log_allows_open_unpromoted_entry() -> None:
    log = (
        '# Operator Friction Log\n\n'
        '## Owner Evidence Entries\n\n'
        '### 2026-06-14 - Still investigating\n\n'
        '- **Type:** evidence\n'
        '- **Source:** owner real use\n'
        '- **Status:** open\n'
        '- **Closure evidence:** n/a\n'
        '- **Promoted to:** n/a\n'
    )
    errors = _VALIDATE_MODULE.validate_operator_friction_log(log)
    assert errors == []


def test_validate_operator_friction_log_detects_malformed_heading() -> None:
    log = (
        '# Operator Friction Log\n\n'
        '## Owner Evidence Entries\n\n'
        '### June 14, 2026 - Missing ISO date\n\n'
        '- **Type:** evidence\n'
        '- **Source:** owner real use\n'
        '- **Status:** open\n'
    )
    errors = _VALIDATE_MODULE.validate_operator_friction_log(log)
    assert any('YYYY-MM-DD' in err for err in errors)


def test_validate_operator_friction_log_detects_missing_type_field() -> None:
    log = (
        '# Operator Friction Log\n\n'
        '## Owner Evidence Entries\n\n'
        '### 2026-06-14 - Bad bullet syntax\n\n'
        '- Type: evidence\n'
        '- **Source:** owner real use\n'
        '- **Status:** open\n'
    )
    errors = _VALIDATE_MODULE.validate_operator_friction_log(log)
    assert any('invalid Type' in err for err in errors)


def test_validate_operator_friction_log_checks_type_source_consistency() -> None:
    log = (
        '# Operator Friction Log\n\n'
        '## Competitor-Derived Hypotheses\n\n'
        '### 2026-06-14 - Bad source\n\n'
        '- **Type:** hypothesis\n'
        '- **Source:** owner real use\n'
        '- **Status:** open\n'
    )
    errors = _VALIDATE_MODULE.validate_operator_friction_log(log)
    assert any('[hypothesis: source, date]' in err for err in errors)


def test_validate_operator_friction_log_ignores_template_code_fence() -> None:
    log = (
        '# Operator Friction Log\n\n'
        '```markdown\n'
        '### YYYY-MM-DD - Short title\n'
        '- **Status:** closed\n'
        '- **Closure evidence:** n/a\n'
        '- **Promoted to:** n/a\n'
        '```\n'
    )
    errors = _VALIDATE_MODULE.validate_operator_friction_log(log)
    assert errors == []


def test_current_roadmap_stays_owner_operator_harness_first() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / 'README.md').read_text(encoding='utf-8')
    index = (root / 'docs' / 'INDEX.md').read_text(encoding='utf-8')
    roadmap = (root / 'docs' / 'roadmap-status.md').read_text(encoding='utf-8')

    errors = _VALIDATE_MODULE.validate_current_direction_claims(
        readme_text=readme,
        docs_index_text=index,
        roadmap_text=roadmap,
    )
    assert errors == []
    assert 'owner-operator' in roadmap
    assert 'owner packaging and local distribution'.lower() in roadmap.lower()
    assert 'general-user trust onboarding' not in roadmap
    assert 'Packaging and adoption' not in roadmap
    assert 'external-facing release channels' not in roadmap


def test_intent_review_candidate_adoption_state() -> None:
    root = Path(__file__).resolve().parents[1]
    review = (
        root / 'docs' / 'analysis' / 'intent-roadmap-socratic-survey-2026-07-22.md'
    ).read_text(encoding='utf-8')
    roadmap = (root / 'docs' / 'roadmap-status.md').read_text(encoding='utf-8')
    release_checklist = (root / 'docs' / 'release-checklist.md').read_text(
        encoding='utf-8'
    )
    friction_log = (root / 'docs' / 'work-log' / 'operator-friction-log.md').read_text(
        encoding='utf-8'
    )

    assert '## Candidate Adoption Ledger' in review
    for candidate_id in ('C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7'):
        assert f'| {candidate_id} |' in review

    assert 'A trigger opens evaluation' in roadmap
    assert 'it does not create implementation authority' in roadmap
    assert 'A survey priority label alone never authorizes work.' in release_checklist
    assert 'Which recent run ID best represents actual daily use?' in friction_log
    assert 'a new strategy doc, separate execution-plan doc' in review


def test_durable_effect_review_candidate_adoption_state() -> None:
    root = Path(__file__).resolve().parents[1]
    review = (
        root
        / 'docs'
        / 'analysis'
        / 'durable-effect-roadmap-socratic-review-2026-08-25.md'
    ).read_text(encoding='utf-8')
    roadmap = (root / 'docs' / 'roadmap-status.md').read_text(encoding='utf-8')
    backlog = (root / 'docs' / 'backlog-priority.md').read_text(encoding='utf-8')
    held = (
        root / 'docs' / 'specs' / 'held-roadmap-forward-spec-index-2026-07-11.md'
    ).read_text(encoding='utf-8')
    daily = (root / 'docs' / 'daily-driver-current-status.md').read_text(
        encoding='utf-8'
    )
    recovery = (root / 'docs' / 'recovery-and-continuity-guide.md').read_text(
        encoding='utf-8'
    )

    assert '## Candidate Adoption Ledger' in review
    for candidate_id in ('C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9'):
        assert f'| {candidate_id} |' in review

    assert 'durable run-state continuity' in roadmap
    assert 'Run continuity does not imply exactly-once tool execution' in roadmap
    for item_id in ('EFX-001', 'EFX-002', 'EFX-003', 'EFX-FUTURE'):
        assert item_id in roadmap
        assert item_id in backlog
    assert 'generic effect service, outbox daemon' in held
    assert 'historical evidence, not an active scheduling authority' in daily
    assert '## Interrupted mutating tool execution' in recovery
    assert 'Blindly rerunning the same logical mutation' in recovery


def test_roadmap_rethink_lens_review_candidate_adoption_state() -> None:
    """2026-08-26 parallel-lens panel: adopted wording pinned at named surfaces."""
    root = Path(__file__).resolve().parents[1]
    lens_review = (
        root / 'docs' / 'analysis' / 'roadmap-rethink-lens-review-2026-08-26.md'
    ).read_text(encoding='utf-8')
    roadmap = (root / 'docs' / 'roadmap-status.md').read_text(encoding='utf-8')
    backlog = (root / 'docs' / 'backlog-priority.md').read_text(encoding='utf-8')
    held = (
        root / 'docs' / 'specs' / 'held-roadmap-forward-spec-index-2026-07-11.md'
    ).read_text(encoding='utf-8')
    daily = (root / 'docs' / 'daily-driver-current-status.md').read_text(
        encoding='utf-8'
    )

    assert '## Candidate Adoption Ledger' in lens_review
    assert '| L1 |' in lens_review
    assert '| L2 |' in lens_review
    # L1: OperatorUsability — stale vacuous gate replaced.
    assert 'until live-credential dry-run proof exists' in daily
    assert 'until acceptance-tier evidence exists' not in daily
    # L2: StrategicSynthesis — H4 gate qualified; ADR-0031 review named.
    assert 'EFX live-proof closure' in roadmap
    assert 'live-provider proof pending' in roadmap
    assert 'ADR-0031 review due 2026-09-12' in backlog
    assert '(decision packet review)' in held


def test_consensus_validation_deletion_preserves_recovery_record() -> None:
    root = Path(__file__).resolve().parents[1]
    spec = (
        root / 'docs' / 'specs' / 'consensus-validation-disposition-spec-2026-07-11.md'
    ).read_text(encoding='utf-8')
    adr = (root / 'docs' / 'adr' / '0029-consensus-validation-deferred.md').read_text(
        encoding='utf-8'
    )
    assert '### 2.1 Pre-deletion preservation record (2026-07-22)' in spec
    assert '`ConsensusRuleType`: `N_OF_M`, `UNANIMOUS`, `MAJORITY`' in spec
    assert '`ConsensusValidator`: `create_rule`, `request_consensus`' in spec
    assert '`SUPERMAJORITY` counted only votes cast' in spec
    assert 'Revival needs an\n  audited revote' in spec
    assert 'git show 7a7799d:teaagent/consensus/consensus_validation.py' in spec
    assert 'git restore --source=<deletion_commit>^' in spec
    assert 'Restoring from history is evidence\nrecovery, not authority' in spec
    assert 'Preservation requirement before deletion' in adr
    assert 'symbol-level\ninventory, wire-blockers, and git recovery commands' in adr


def test_h4_evidence_prep_surfaces_are_documented() -> None:
    root = Path(__file__).resolve().parents[1]
    matrix_md = (
        root / 'docs' / 'architecture' / 'claim-to-test-traceability-matrix.md'
    ).read_text(encoding='utf-8')
    matrix_yaml = (
        root / 'docs' / 'architecture' / 'claim-to-test-traceability.yaml'
    ).read_text(encoding='utf-8')
    spec = (
        root / 'docs' / 'specs' / 'rbac-shadow-to-enforce-promotion-spec-2026-07-11.md'
    ).read_text(encoding='utf-8')

    assert '## H4 Policy/RBAC Coverage Declarations (ADR-0031 Criterion 2)' in matrix_md
    assert 'h4_policy_rbac_coverage:' in matrix_yaml
    for script in (
        'scripts/prepare_h4_evidence.py',
        'scripts/check_h4_coverage.py',
        'scripts/benchmark_h4_policy.py',
        'scripts/verify_h4_rollback.py',
        'scripts/build_h4_decision_packet.py',
    ):
        assert script in spec
    for test_file in (
        'tests/test_h4_evidence.py',
        'tests/test_h4_coverage.py',
        'tests/test_h4_performance.py',
        'tests/test_h4_rollback.py',
        'tests/test_h4_decision_packet.py',
    ):
        assert test_file in spec


def test_doc_cross_references_fail_for_non_historical_docs(tmp_path: Path) -> None:
    docs = tmp_path / 'docs'
    docs.mkdir()
    (docs / 'guide.md').write_text('[missing](missing.md)\n', encoding='utf-8')

    errors = _VALIDATE_MODULE.validate_doc_cross_references(
        repo_root=tmp_path,
        emit_historical_warnings=False,
    )

    assert len(errors) == 1
    assert 'docs/guide.md' in errors[0]


def test_doc_cross_references_keep_historical_links_non_blocking(
    tmp_path: Path,
) -> None:
    plans = tmp_path / 'docs' / 'plans'
    plans.mkdir(parents=True)
    (plans / 'old.md').write_text('[missing](missing.md)\n', encoding='utf-8')

    errors = _VALIDATE_MODULE.validate_doc_cross_references(
        repo_root=tmp_path,
        emit_historical_warnings=False,
    )

    assert errors == []


def test_doc_cross_references_ignore_fenced_examples(tmp_path: Path) -> None:
    (tmp_path / 'README.md').write_text(
        '```markdown\n[template](missing.md)\n```\n',
        encoding='utf-8',
    )

    errors = _VALIDATE_MODULE.validate_doc_cross_references(
        repo_root=tmp_path,
        emit_historical_warnings=False,
    )

    assert errors == []


def test_current_direction_guard_detects_old_adoption_framing() -> None:
    errors = _VALIDATE_MODULE.validate_current_direction_claims(
        readme_text=(
            '# TeaAgent\n'
            '> **Direction record:** owner-operator harness-first current direction, '
            'aspirational adoption\n'
        ),
        docs_index_text=(
            '# Index\n'
            '## Start Here\n'
            '| What can a daily user trust today? | x | y |\n'
            '## Current Truth\n'
            '| Current daily-driver behavior | x |\n'
        ),
        roadmap_text=(
            '# Roadmap Status\n'
            'owner-operator is the current validated persona; not current goals\n'
            '## Purpose\n'
            'owner-operator roadmap\n'
            '## Roadmap Horizons\n'
            '| H6 | Packaging and adoption | external-facing release channels |\n'
            'general-user trust onboarding\n'
        ),
    )
    assert any('aspirational adoption' in err for err in errors)
    assert any('Packaging and adoption' in err for err in errors)
    assert any('external-facing release channels' in err for err in errors)
    assert any('general-user trust onboarding' in err for err in errors)


def test_current_direction_guard_ignores_historical_evidence_mentions() -> None:
    errors = _VALIDATE_MODULE.validate_current_direction_claims(
        readme_text=(
            '# TeaAgent\n'
            '> **Direction record:** owner-operator harness-first current direction\n'
        ),
        docs_index_text=(
            '# Index\n'
            '## Start Here\n'
            '| What can the owner-operator trust today? | x | y |\n'
            '## Current Truth\n'
            '| Current owner-operated daily behavior | x |\n'
            '## Evidence And Review\n'
            '| June 10 conversation experience refresh | '
            'General-User Conversation Experience Refresh |\n'
        ),
        roadmap_text=(
            '# Roadmap Status\n'
            'owner-operator is the current validated persona; not current goals\n'
            '## Purpose\n'
            'Roadmap purpose.\n'
            '## Roadmap Horizons\n'
            '| H6 | Owner packaging and local distribution | owner-operated use |\n'
        ),
    )
    assert errors == []


def test_validate_roadmap_status_detects_missing_h0_truth_links() -> None:
    roadmap = (
        '# Roadmap Status\n\n'
        '| H0 | Claim and risk hygiene | Public claims are owned |\n'
    )
    errors = _VALIDATE_MODULE.validate_roadmap_status(roadmap)
    assert (
        'Roadmap status missing documentation-current-truth work reference.' in errors
    )
    assert 'Roadmap status missing doc-vs-HEAD guard reference.' in errors


def test_validate_roadmap_required_fields_detects_missing_owner() -> None:
    roadmap = (
        '# Roadmap Status\n\n'
        '| ID | Work Item | Owner | Status | Confidence | Next Gate | Risk |\n'
        '|---|---|---|---|---|---|---|\n'
        '| GOV-001 | Example |  | Pending | Medium | GOV-002 | Medium |\n'
    )
    errors = _VALIDATE_MODULE.validate_roadmap_required_fields(roadmap)
    assert any('missing required field' in err and 'Owner' in err for err in errors)


def test_validate_roadmap_required_fields_detects_invalid_status() -> None:
    roadmap = (
        '# Roadmap Status\n\n'
        '| ID | Work Item | Owner | Status | Confidence | Next Gate | Risk |\n'
        '|---|---|---|---|---|---|---|\n'
        '| GOV-001 | Example | docs | Shipped | Medium | GOV-002 | Medium |\n'
    )
    errors = _VALIDATE_MODULE.validate_roadmap_required_fields(roadmap)
    assert any('unrecognized Status' in err for err in errors)


def test_validate_roadmap_required_fields_passes_for_valid_track_row() -> None:
    roadmap = (
        '# Roadmap Status\n\n'
        '| ID | Work Item | Owner | Status | Confidence | Next Gate | Risk |\n'
        '|---|---|---|---|---|---|---|\n'
        '| GOV-001 | Example | docs | Pending | Medium | GOV-002 | Medium |\n'
    )
    errors = _VALIDATE_MODULE.validate_roadmap_required_fields(roadmap)
    assert errors == []


def test_validate_coverage_omit_ledger_passes_for_repo_docs() -> None:
    root = Path(__file__).resolve().parents[1]
    pyproject = (root / 'pyproject.toml').read_text(encoding='utf-8')
    ledger = (root / 'docs' / 'governance' / 'coverage-omit-ledger.md').read_text(
        encoding='utf-8'
    )
    errors = _VALIDATE_MODULE.validate_coverage_omit_ledger(
        pyproject_text=pyproject,
        ledger_text=ledger,
    )
    assert errors == []


def test_validate_coverage_omit_ledger_detects_missing_pattern() -> None:
    pyproject = (
        '[tool.coverage.run]\n'
        'omit = [\n'
        '    "teaagent/tui/*",\n'
        '    "teaagent/wasm_runtime.py",\n'
        ']\n'
    )
    ledger = (
        '| Omit Pattern | Owner | Reason | Risk | Expected Return Milestone | '
        'Smoke-Test Candidate |\n'
        '|---|---|---|---|---|---|\n'
        '| `teaagent/tui/*` | Platform UX Team | Hard to cover. | Medium | '
        'Phase 1 | `tests/acceptance/test_headless_tui.py` |\n'
    )
    errors = _VALIDATE_MODULE.validate_coverage_omit_ledger(
        pyproject_text=pyproject,
        ledger_text=ledger,
    )
    assert any('teaagent/wasm_runtime.py' in err for err in errors)


def _repo_guarded_registry_text() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / 'docs' / 'governance' / 'guarded-claims-registry.md').read_text(
        encoding='utf-8'
    )


def test_validate_guarded_claims_passes_for_repo_docs() -> None:
    root = Path(__file__).resolve().parents[1]
    errors = _VALIDATE_MODULE.validate_guarded_claims(
        registry_text=_repo_guarded_registry_text(),
        repo_root=root,
    )
    assert errors == []


def test_validate_guarded_claims_detects_stale_failure_prose(tmp_path: Path) -> None:
    (tmp_path / 'docs').mkdir()
    # A current-truth front door that keeps a stale, non-zero full-suite result.
    (tmp_path / 'docs' / 'daily-driver-current-status.md').write_text(
        'The full suite reported 120 passed, 26 failed last week.\n',
        encoding='utf-8',
    )
    errors = _VALIDATE_MODULE.validate_guarded_claims(
        registry_text=_repo_guarded_registry_text(),
        repo_root=tmp_path,
    )
    assert any('26 failed' in err for err in errors)


def test_validate_guarded_claims_allows_green_and_exempt_lines(tmp_path: Path) -> None:
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'docs' / 'daily-driver-current-status.md').write_text(
        'The full suite reported 3396 passed, 0 failed, 22 skipped.\n'
        'Historical note: an old run once had 26 failed entries.\n',
        encoding='utf-8',
    )
    errors = _VALIDATE_MODULE.validate_guarded_claims(
        registry_text=_repo_guarded_registry_text(),
        repo_root=tmp_path,
    )
    assert errors == []


def test_validate_guarded_claims_detects_missing_registry_entry(tmp_path: Path) -> None:
    errors = _VALIDATE_MODULE.validate_guarded_claims(
        registry_text='# Registry with no guarded document rows\n',
        repo_root=tmp_path,
    )
    assert any('README.md' in err for err in errors)


def test_validate_dependency_audit_policy_passes_for_repo_docs() -> None:
    root = Path(__file__).resolve().parents[1]
    policy = (root / 'docs' / 'security' / 'dependency-audit-policy.md').read_text(
        encoding='utf-8'
    )
    workflow = (root / '.github' / 'workflows' / 'security.yml').read_text(
        encoding='utf-8'
    )
    errors = _VALIDATE_MODULE.validate_dependency_audit_policy(
        policy_text=policy,
        security_workflow_text=workflow,
    )
    assert errors == []


def test_validate_dependency_audit_policy_rejects_unscoped_editable_audit() -> None:
    policy = (
        '# Dependency Audit Policy\n'
        '## Base Install Audit\n'
        '## Lockfile and Dev Environment Audit\n'
        '## Optional-Extra Runtime Audit\n'
        'managed-google-adk managed-vertex playwright telemetry oauth wasm\n'
    )
    workflow = (
        'jobs:\n  pip-audit:\n    steps:\n      - run: pip-audit --skip-editable\n'
    )
    errors = _VALIDATE_MODULE.validate_dependency_audit_policy(
        policy_text=policy,
        security_workflow_text=workflow,
    )
    assert any('unscoped `pip-audit --skip-editable`' in err for err in errors)


def test_validate_provider_docs_detects_stale_llm_adapter_count() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / 'README.md').read_text(encoding='utf-8')
    architecture = (root / 'docs' / 'architecture.md').read_text(encoding='utf-8')
    usage = (root / 'docs' / 'USAGE.md').read_text(encoding='utf-8')
    stale = architecture.replace('14 providers', '15 providers', 1)
    stale = stale.replace(
        'across 14 registered providers', 'across 15 registered providers', 1
    )
    stale = stale.replace('14 LLM providers', '15 LLM providers', 1)
    errors = _VALIDATE_MODULE.validate_provider_docs_consistency(
        readme_text=readme,
        architecture_text=stale,
        usage_text=usage,
    )
    assert any('mismatch' in err for err in errors)


def test_validate_date_coherence_detects_use_cases_survey_drift() -> None:
    root = Path(__file__).resolve().parents[1]
    survey = (root / 'scripts' / 'refresh_agent_readme_survey.md').read_text(
        encoding='utf-8'
    )
    matrix = (root / 'docs' / 'use-case-matrix.md').read_text(encoding='utf-8')
    catalog = (root / 'docs' / 'plugin-skill-catalog.md').read_text(encoding='utf-8')
    use_cases = (root / 'docs' / 'use-cases.md').read_text(encoding='utf-8')
    architecture = (root / 'docs' / 'architecture.md').read_text(encoding='utf-8')
    stale = use_cases.replace(
        'Landscape survey (reviewed 2026-06-06)',
        'Landscape survey (reviewed 2026-06-01)',
        1,
    )
    errors = _VALIDATE_MODULE.validate_date_coherence(
        survey_text=survey,
        matrix_text=matrix,
        catalog_text=catalog,
        use_cases_text=stale,
        architecture_text=architecture,
    )
    assert any('Date drift detected' in err for err in errors)


def test_validate_matrix_open_gap_count_detects_stale_matrix() -> None:
    root = Path(__file__).resolve().parents[1]
    matrix = (root / 'docs' / 'use-case-matrix.md').read_text(encoding='utf-8')
    stale = matrix.replace(
        'Open partial/planned gaps (P1/P2): **3**',
        'Open partial/planned gaps (P1/P2): **0**',
        1,
    )
    errors = _VALIDATE_MODULE.validate_matrix_open_gap_count(
        matrix_text=stale,
        use_cases_path=root / 'docs' / 'use-cases.md',
    )
    assert any('open gap count mismatch' in err for err in errors)


def test_open_partial_planned_gap_count_matches_use_cases_section() -> None:
    root = Path(__file__).resolve().parents[1]
    build_matrix = _VALIDATE_MODULE._load_build_use_case_matrix_module()
    count = build_matrix._open_backlog_gap_count(root / 'docs' / 'use-cases.md')
    assert count == 3


def test_validate_doc_code_references_flags_missing_file(tmp_path: Path) -> None:
    doc = 'Evidence at `foo.py:99999` for the fix.'
    errors = _VALIDATE_MODULE.validate_doc_code_references(doc, repo_root=tmp_path)
    assert any('foo.py:99999' in err and 'missing file' in err for err in errors)


def test_validate_doc_code_references_passes_for_valid_refs(tmp_path: Path) -> None:
    repo = tmp_path
    target = repo / 'teaagent' / 'sample.py'
    target.parent.mkdir(parents=True)
    target.write_text('line1\nline2\nline3\n', encoding='utf-8')
    doc = 'Fixed in `teaagent/sample.py:2`.'
    errors = _VALIDATE_MODULE.validate_doc_code_references(doc, repo_root=repo)
    assert errors == []


def test_roadmap_status_code_references_pass_for_repo_doc() -> None:
    root = Path(__file__).resolve().parents[1]
    roadmap = (root / 'docs' / 'roadmap-status.md').read_text(encoding='utf-8')
    errors = _VALIDATE_MODULE.validate_doc_code_references(roadmap, repo_root=root)
    assert errors == []
