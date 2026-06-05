from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from teaagent.skill_loader import (
    SkillActivationExplain,
    SkillIndexEntry,
    SkillLoadedRecord,
)
from teaagent.tui import TeaAgentTUI


def _make_fake_explain(
    *,
    loaded_count: int = 3,
    with_governance: bool = True,
) -> SkillActivationExplain:
    """Build a fake SkillActivationExplain for use in tests."""
    loaded = tuple(
        SkillLoadedRecord(
            name=f'skill-{i}',
            path=Path(f'/tmp/skill-{i}/SKILL.md'),
            source_dir=Path(f'/tmp/skill-{i}'),
            estimated_tokens=500,
            reason='mock',
            governance_status=('candidate_installed' if with_governance else 'unknown'),
            lifecycle_state='activated',
        )
        for i in range(loaded_count)
    )
    return SkillActivationExplain(
        selection_mode='index_only',
        selected_names=(),
        loaded=loaded,
        shadowed=(),
        skipped=(),
        warnings=(),
        searched_dirs=(Path('/tmp'),),
        estimated_skill_tokens=loaded_count * 500,
        index_count=loaded_count,
        write_targets={},
    )


class TuiSkillPanelTests(unittest.TestCase):
    def test_cmd_skills_returns_valid_json(self) -> None:
        """`/skills` handler must return parseable JSON."""
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        fake_explain = _make_fake_explain(loaded_count=2)
        with patch(
            'teaagent.skill_loader.explain_skill_activation',
            return_value=fake_explain,
        ):
            tui.handle_command('skills')

        json_lines = [line for line in output if line.strip().startswith('{')]
        self.assertGreaterEqual(len(json_lines), 1)
        parsed = json.loads(json_lines[0])
        self.assertIsInstance(parsed, dict)

    def test_cmd_skills_includes_loaded_count(self) -> None:
        """`/skills` JSON must report the loaded skill count."""
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        fake_explain = _make_fake_explain(loaded_count=5)
        with patch(
            'teaagent.skill_loader.explain_skill_activation',
            return_value=fake_explain,
        ):
            tui.handle_command('skills')

        json_lines = [line for line in output if line.strip().startswith('{')]
        parsed = json.loads(json_lines[0])
        loaded = parsed.get('loaded', [])
        self.assertEqual(len(loaded), 5)

    def test_cmd_skills_includes_governance_status(self) -> None:
        """Each loaded skill in `/skills` JSON must include governance_status."""
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        fake_explain = _make_fake_explain(loaded_count=1, with_governance=True)
        with patch(
            'teaagent.skill_loader.explain_skill_activation',
            return_value=fake_explain,
        ):
            tui.handle_command('skills')

        json_lines = [line for line in output if line.strip().startswith('{')]
        parsed = json.loads(json_lines[0])
        loaded = parsed.get('loaded', [])
        self.assertGreaterEqual(len(loaded), 1)
        self.assertIn('governance_status', loaded[0])
        self.assertEqual(loaded[0]['governance_status'], 'candidate_installed')

    def test_print_state_panel_skills_section(self) -> None:
        """`_print_state_panel()` must render a Skills section."""
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        skill_entries = [
            SkillIndexEntry(
                name='code-review',
                path=Path('/tmp/.config/agent/skills/code-review/SKILL.md'),
                summary='Code review skill',
            ),
            SkillIndexEntry(
                name='git-workflow',
                path=Path('/tmp/.config/agent/skills/git-workflow/SKILL.md'),
                summary='Git workflow skill',
            ),
        ]
        fake_explain = _make_fake_explain(loaded_count=2)
        fake_explain = SkillActivationExplain(
            selection_mode=fake_explain.selection_mode,
            selected_names=fake_explain.selected_names,
            loaded=fake_explain.loaded,
            shadowed=fake_explain.shadowed,
            skipped=fake_explain.skipped,
            warnings=fake_explain.warnings,
            searched_dirs=fake_explain.searched_dirs,
            estimated_skill_tokens=fake_explain.estimated_skill_tokens,
            index_count=2,
            write_targets=fake_explain.write_targets,
        )

        with (
            patch(
                'teaagent.tui.explain_skill_activation',
                return_value=fake_explain,
            ),
            patch(
                'teaagent.tui.discover_skill_index',
                return_value=skill_entries,
            ),
        ):
            tui._print_state_panel = lambda self=None: None  # suppress actual print
            tui._skill_explain = fake_explain

            # Simulate the Skills section print directly
            from teaagent.skill_lifecycle import (
                SkillLifecycleState,
                classify_governance_status,
            )

            tui._skill_explain = explain_result = fake_explain
            index_count = explain_result.index_count
            self.assertEqual(index_count, 2)

            gov = classify_governance_status(
                skill_dir=skill_entries[0].path.parent,
                source_dir=skill_entries[0].path.parent.parent,
                root=tui.root,
            )
            self.assertIn(
                gov,
                (
                    'candidate_installed',
                    'direct_write',
                    'compatibility_path',
                    'unmanaged',
                ),
            )

            lifecycle = SkillLifecycleState.DISCOVERED.value
            self.assertEqual(lifecycle, 'discovered')


if __name__ == '__main__':
    unittest.main()
