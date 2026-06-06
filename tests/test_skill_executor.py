from __future__ import annotations

from pathlib import Path

from teaagent.consensus import RiskLevel
from teaagent.skill_executor import execute_skill
from teaagent.skill_router import SandboxType
from teaagent.skill_writer import SkillWriter


def test_execute_skill_low_risk_code_mode(tmp_path: Path) -> None:
    skill_dir = tmp_path / 'helper'
    skill_dir.mkdir()
    (skill_dir / 'tool.py').write_text(
        'def run(payload):\n    return {"echo": payload.get("x")}\n',
        encoding='utf-8',
    )
    (skill_dir / 'SKILL.md').write_text('# helper\n', encoding='utf-8')

    result = execute_skill(skill_dir, {'x': 1}, risk_level=RiskLevel.LOW)
    assert result.success is True
    assert result.sandbox_type == SandboxType.DIRECTORY_SNAPSHOT
    assert result.output == {'echo': 1}


def test_execute_skill_high_risk_missing_isolation_fails_closed(tmp_path: Path) -> None:
    skill_dir = tmp_path / 'wasm_skill'
    skill_dir.mkdir()
    (skill_dir / 'tool.py').write_text(
        'def run(payload):\n    return {"ok": True, "n": payload["n"]}\n',
        encoding='utf-8',
    )
    (skill_dir / 'SKILL.md').write_text('# wasm skill\n', encoding='utf-8')

    result = execute_skill(skill_dir, {'n': 3}, risk_level=RiskLevel.HIGH)
    if result.success:
        assert result.execution_backend in {'wasm', 'docker'}
    else:
        assert result.execution_backend in {
            'docker_unavailable',
            'wasm_artifact_missing',
            'isolation_required',
        }


def test_skill_writer_publish_then_execute(tmp_path: Path) -> None:
    writer = SkillWriter(tmp_path)
    draft = writer.draft('Transform JSON payload', name='json_transform')
    published = writer.publish(draft)
    assert published.ok is True
    assert published.skill_dir is not None

    result = execute_skill(published.skill_dir, {'value': 42}, risk_level=RiskLevel.LOW)
    assert result.success is True
    assert result.output is not None
