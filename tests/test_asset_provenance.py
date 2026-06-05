"""Tests for dynamic asset provenance (CPP-P0-006)."""

from __future__ import annotations

import time
from pathlib import Path

from teaagent.asset_provenance import (
    AssetProvenanceBundle,
    ProvenanceRecord,
    _revocation_status_for_skill,
    collect_provenance,
)
from teaagent.run_evidence import (
    RunEvidenceBundle,
    extract_provenance,
)
from teaagent.skill_lifecycle import SkillLifecycleState, SkillLifecycleTracker
from teaagent.skill_loader import (
    explain_skill_activation,
)


def _install_skill(base: Path, rel_dir: str, name: str, body: str) -> Path:
    skill_dir = base / rel_dir / name
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / 'SKILL.md'
    skill_md.write_text(
        f'---\nname: {name}\ndescription: {name} skill\n---\n{body}\n',
        encoding='utf-8',
    )
    return skill_dir


class TestProvenanceRecord:
    def test_creates_record_with_defaults(self) -> None:
        record = ProvenanceRecord(asset_type='skill', name='my-skill')
        assert record.asset_type == 'skill'
        assert record.name == 'my-skill'
        assert record.source_path == ''
        assert record.governance_status == 'unknown'
        assert record.activation_status == 'unknown'
        assert record.revocation_status == 'unknown'
        assert record.shadowed_paths == []
        assert record.loaded_at > 0

    def test_creates_record_with_all_fields(self) -> None:
        now = time.time()
        record = ProvenanceRecord(
            asset_type='mcp_server',
            name='github',
            source_path='https://example.com/mcp',
            governance_status='remote',
            activation_status='connected',
            revocation_status='active',
            shadowed_paths=[],
            loaded_at=now,
        )
        assert record.revocation_status == 'active'
        assert record.governance_status == 'remote'

    def test_to_dict_includes_all_fields(self) -> None:
        now = time.time()
        record = ProvenanceRecord(
            asset_type='skill',
            name='test-skill',
            source_path='/tmp/test-skill/SKILL.md',
            governance_status='direct_write',
            activation_status='activated',
            revocation_status='active',
            shadowed_paths=['/tmp/shadowed/SKILL.md'],
            loaded_at=now,
        )
        d = record.to_dict()
        assert d['asset_type'] == 'skill'
        assert d['name'] == 'test-skill'
        assert d['governance_status'] == 'direct_write'
        assert d['activation_status'] == 'activated'
        assert d['revocation_status'] == 'active'
        assert d['shadowed_paths'] == ['/tmp/shadowed/SKILL.md']
        assert d['loaded_at'] == now


class TestAssetProvenanceBundle:
    def test_empty_bundle(self) -> None:
        bundle = AssetProvenanceBundle()
        assert bundle.records == []
        assert bundle.captured_at > 0

    def test_bundle_with_records(self) -> None:
        r1 = ProvenanceRecord(asset_type='skill', name='s1')
        r2 = ProvenanceRecord(asset_type='mcp_server', name='mcp1')
        bundle = AssetProvenanceBundle(records=[r1, r2])
        assert len(bundle.records) == 2

    def test_to_dict(self) -> None:
        r1 = ProvenanceRecord(asset_type='skill', name='s1')
        bundle = AssetProvenanceBundle(records=[r1])
        d = bundle.to_dict()
        assert 'captured_at' in d
        assert len(d['records']) == 1
        assert d['records'][0]['name'] == 's1'


class TestRevocationStatusForSkill:
    def test_blocked_is_revoked(self) -> None:
        assert (
            _revocation_status_for_skill(
                'test', SkillLifecycleState.BLOCKED.value
            )
            == 'revoked'
        )

    def test_superseded_is_revoked(self) -> None:
        assert (
            _revocation_status_for_skill(
                'test', SkillLifecycleState.SUPERSEDED.value
            )
            == 'revoked'
        )

    def test_activated_is_active(self) -> None:
        assert (
            _revocation_status_for_skill(
                'test', SkillLifecycleState.ACTIVATED.value
            )
            == 'active'
        )

    def test_discovered_is_active(self) -> None:
        assert (
            _revocation_status_for_skill(
                'test', SkillLifecycleState.DISCOVERED.value
            )
            == 'active'
        )

    def test_unknown_state_returns_unknown(self) -> None:
        assert (
            _revocation_status_for_skill('test', 'bogus_state')
            == 'unknown'
        )


class TestCollectProvenance:
    def test_returns_empty_bundle_with_no_args(self) -> None:
        bundle = collect_provenance(Path('/tmp'))
        assert isinstance(bundle, AssetProvenanceBundle)
        assert bundle.records == []

    def test_collects_skills_from_activation(self, tmp_path: Path) -> None:
        _install_skill(tmp_path, '.config/agent/skills', 'alpha',
                       'Alpha skill body content here.')
        explain = explain_skill_activation(tmp_path, selected_names=frozenset(['alpha']))

        bundle = collect_provenance(tmp_path, skill_activation=explain)
        assert len(bundle.records) == 1
        record = bundle.records[0]
        assert record.asset_type == 'skill'
        assert record.name == 'alpha'
        assert record.governance_status in (
            'direct_write', 'candidate_installed', 'compatibility_path',
            'unmanaged',
        )
        assert record.activation_status == 'activated'
        assert record.revocation_status == 'active'

    def test_collects_shadowed_paths(self, tmp_path: Path) -> None:
        _install_skill(tmp_path, '.config/agent/skills', 'beta',
                       'Beta skill first.winner.')
        _install_skill(tmp_path, '.claude/skills', 'beta',
                       'Beta skill second.shadowed.')
        explain = explain_skill_activation(tmp_path, selected_names=frozenset(['beta']))

        bundle = collect_provenance(tmp_path, skill_activation=explain)
        assert len(bundle.records) == 1
        record = bundle.records[0]
        assert len(record.shadowed_paths) >= 1

    def test_collects_mcp_servers(self) -> None:
        mcp_servers = [
            {
                'name': 'github',
                'endpoint': 'https://github-mcp.example.com/mcp',
                'status': 'connected',
                'source_path': '/etc/mcp/github.json',
            },
            {
                'name': 'filesystem',
                'endpoint': '',
                'status': 'failed',
                'source_path': '/etc/mcp/filesystem.toml',
            },
        ]
        bundle = collect_provenance(
            Path('/tmp'), mcp_servers=mcp_servers,
        )
        assert len(bundle.records) == 2

        gh = bundle.records[0]
        assert gh.asset_type == 'mcp_server'
        assert gh.name == 'github'
        assert gh.governance_status == 'remote'
        assert gh.activation_status == 'connected'
        assert gh.revocation_status == 'active'

        fs = bundle.records[1]
        assert fs.asset_type == 'mcp_server'
        assert fs.name == 'filesystem'
        assert fs.governance_status == 'local'
        assert fs.activation_status == 'failed'
        assert fs.revocation_status == 'revoked'

    def test_collects_mcp_server_unknown_status(self) -> None:
        bundle = collect_provenance(
            Path('/tmp'),
            mcp_servers=[{'name': 'unknown-srv', 'status': 'pending'}],
        )
        record = bundle.records[0]
        assert record.revocation_status == 'unknown'
        assert record.activation_status == 'pending'

    def test_lifecycle_tracker_affects_state(self, tmp_path: Path) -> None:
        _install_skill(tmp_path, '.config/agent/skills', 'delta',
                       'Delta skill body content here.')
        explain = explain_skill_activation(tmp_path, selected_names=frozenset(['delta']))

        tracker = SkillLifecycleTracker()
        tracker.transition(
            'delta',
            SkillLifecycleState.BLOCKED.value,
            reason='revoked for test',
        )

        bundle = collect_provenance(
            tmp_path,
            skill_activation=explain,
            lifecycle_tracker=tracker,
        )
        record = bundle.records[0]
        assert record.name == 'delta'
        assert record.revocation_status == 'revoked'

    def test_collects_both_skills_and_mcp(self, tmp_path: Path) -> None:
        _install_skill(tmp_path, '.config/agent/skills', 'dual',
                       'Dual skill body content here.')
        explain = explain_skill_activation(tmp_path, selected_names=frozenset(['dual']))

        bundle = collect_provenance(
            tmp_path,
            skill_activation=explain,
            mcp_servers=[{'name': 'mcp1', 'status': 'connected'}],
        )
        types = {r.asset_type for r in bundle.records}
        assert types == {'skill', 'mcp_server'}
        assert len(bundle.records) == 2


class TestExtractProvenance:
    def test_extracts_from_audit_events(self) -> None:
        events = [
            {
                'event_type': 'provenance_collected',
                'payload': {
                    'snapshot': {
                        'captured_at': 1000.0,
                        'records': [
                            {
                                'asset_type': 'skill',
                                'name': 'extracted-skill',
                                'source_path': '/path/SKILL.md',
                                'governance_status': 'direct_write',
                                'activation_status': 'activated',
                                'revocation_status': 'active',
                                'shadowed_paths': [],
                                'loaded_at': 999.0,
                            }
                        ],
                    }
                },
            }
        ]
        records = extract_provenance(events)
        assert len(records) == 1
        assert records[0].asset_type == 'skill'
        assert records[0].name == 'extracted-skill'
        assert records[0].governance_status == 'direct_write'

    def test_ignores_other_event_types(self) -> None:
        events = [
            {'event_type': 'tool_use', 'payload': {}},
            {'event_type': 'run_completed', 'payload': {}},
        ]
        assert extract_provenance(events) == []

    def test_handles_non_dict_payload(self) -> None:
        events = [
            {
                'event_type': 'provenance_collected',
                'payload': 'not-a-dict',
            }
        ]
        assert extract_provenance(events) == []

    def test_handles_non_dict_snapshot(self) -> None:
        events = [
            {
                'event_type': 'provenance_collected',
                'payload': {'snapshot': 'not-a-dict'},
            }
        ]
        assert extract_provenance(events) == []

    def test_handles_non_dict_record_entries(self) -> None:
        events = [
            {
                'event_type': 'provenance_collected',
                'payload': {
                    'snapshot': {
                        'records': ['not-a-dict', 42, None],
                    }
                },
            }
        ]
        assert extract_provenance(events) == []

    def test_extracts_multiple_records_from_single_event(self) -> None:
        events = [
            {
                'event_type': 'provenance_collected',
                'payload': {
                    'snapshot': {
                        'records': [
                            {'asset_type': 'skill', 'name': 'a'},
                            {'asset_type': 'mcp_server', 'name': 'b'},
                        ]
                    }
                },
            }
        ]
        records = extract_provenance(events)
        assert len(records) == 2


class TestRunEvidenceBundleWithProvenance:
    def test_bundle_includes_provenance(self) -> None:
        record = ProvenanceRecord(asset_type='skill', name='test')
        bundle = RunEvidenceBundle(
            run_id='run-1',
            provenance=[record],
        )
        assert len(bundle.provenance) == 1
        assert bundle.provenance[0].name == 'test'

    def test_bundle_serializes_provenance(self) -> None:
        record = ProvenanceRecord(
            asset_type='skill',
            name='test',
            governance_status='direct_write',
        )
        bundle = RunEvidenceBundle(
            run_id='run-1',
            provenance=[record],
        )
        data = bundle.to_dict()
        assert len(data['provenance']) == 1
        assert data['provenance'][0]['name'] == 'test'
        assert data['provenance'][0]['governance_status'] == 'direct_write'

    def test_bundle_default_provenance_empty(self) -> None:
        bundle = RunEvidenceBundle(run_id='run-empty')
        assert bundle.provenance == []
        data = bundle.to_dict()
        assert data['provenance'] == []
