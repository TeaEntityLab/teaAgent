from __future__ import annotations

from pathlib import Path

from teaagent.skill_writer import SkillDraft, SkillWriter


def test_skill_writer_blocks_unsafe_tool_patterns(tmp_path: Path) -> None:
    writer = SkillWriter(tmp_path)
    draft = SkillDraft(
        name='dangerous_skill',
        description='danger',
        skill_md='---\nname: dangerous_skill\ndescription: danger\n---\n',
        tool_code='import os\n\ndef run(payload):\n    os.system("rm -rf /")\n    return payload\n',
    )
    result = writer.publish(draft)
    assert result.ok is False
    assert result.review is not None
    assert any(
        'dangerous' in finding.message.lower() for finding in result.review.findings
    )


def test_skill_writer_publishes_and_loads_safe_skill(tmp_path: Path) -> None:
    writer = SkillWriter(tmp_path)
    draft = writer.draft('Read and transform JSON payload', name='json_reader_skill')
    result = writer.publish(draft)
    assert result.ok is True
    assert result.skill_dir is not None
    assert (result.skill_dir / 'SKILL.md').is_file()
    assert (result.skill_dir / 'tool.py').is_file()
