from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from teaagent.skill_loader import get_skill_diagnostics
from teaagent.tui import TeaAgentTUI
from teaagent.tui._commands import _COMMAND_DISPATCH


def _install_skill(base: Path, rel_dir: str, name: str, body: str) -> None:
    skill_dir = base / rel_dir / name
    skill_dir.mkdir(parents=True)
    (skill_dir / 'SKILL.md').write_text(
        f'---\nname: {name}\ndescription: {name} skill\n---\n{body}\n',
        encoding='utf-8',
    )


class DiagnosticsStructureTests(unittest.TestCase):
    def test_diagnostics_structure(self) -> None:
        """Diagnostics dict must have all expected top-level keys."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            diagnostics = get_skill_diagnostics(root)
            expected_keys = {
                'loaded_skills',
                'active_skill',
                'shadowed_skills',
                'skipped',
                'warnings',
                'searched_dirs',
                'governance_status',
                'candidates',
                'candidate_count',
                'long_result_artifacts',
                'output_verification',
            }
            self.assertTrue(expected_keys.issubset(diagnostics.keys()))

            # output_verification must include validators_available and status
            ov = diagnostics['output_verification']
            self.assertIn('validators_available', ov)
            self.assertIn('status', ov)
            self.assertIsInstance(ov['validators_available'], list)
            self.assertIn('FileExistsValidator', ov['validators_available'])


class DiagnosticsLoadedSkillsTests(unittest.TestCase):
    def test_diagnostics_loaded_skills(self) -> None:
        """Loaded skills appear in diagnostics output when a skill is present."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _install_skill(
                root,
                '.config/agent/skills',
                'test-skill',
                'Test skill body ' * 20,
            )
            # Force eager load by not passing selected_names
            diagnostics = get_skill_diagnostics(root)
            self.assertIsInstance(diagnostics, dict)
            self.assertIn('loaded_skills', diagnostics)
            self.assertIn('active_skill', diagnostics)

    def test_diagnostics_loaded_skills_with_patch(self) -> None:
        """Diagnostics reports loaded skills via patched explain_skill_activation."""
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        from teaagent.skill_loader import (
            SkillActivationExplain,
            SkillLoadedRecord,
        )

        loaded = (
            SkillLoadedRecord(
                name='alpha',
                path=Path('/tmp/alpha/SKILL.md'),
                source_dir=Path('/tmp/.config/agent/skills'),
                estimated_tokens=200,
                reason='mock',
                governance_status='direct_write',
                lifecycle_state='activated',
            ),
        )
        fake_explain = SkillActivationExplain(
            selection_mode='index_only',
            selected_names=(),
            loaded=loaded,
            shadowed=(),
            skipped=(),
            warnings=(),
            searched_dirs=(Path('/tmp'),),
            estimated_skill_tokens=200,
            index_count=1,
            write_targets={},
        )
        with patch(
            'teaagent.skill_loader.explain_skill_activation',
            return_value=fake_explain,
        ):
            tui.handle_command('skill-diagnostics')

        json_lines = [line for line in output if line.strip().startswith('{')]
        self.assertGreaterEqual(len(json_lines), 1)
        parsed = json.loads(json_lines[0])
        self.assertIsInstance(parsed, dict)
        loaded_skills = parsed.get('loaded_skills', [])
        self.assertEqual(len(loaded_skills), 1)


class DiagnosticsShadowedSkillsTests(unittest.TestCase):
    def test_diagnostics_shadowed_skills(self) -> None:
        """Shadow detection works — shadowed skills reported in diagnostics."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _install_skill(root, '.config/agent/skills', 'alpha', 'Config a ' * 50)
            _install_skill(root, '.claude/skills', 'alpha', 'Claude a ' * 50)
            diagnostics = get_skill_diagnostics(root)
            shadowed = diagnostics.get('shadowed_skills', [])
            self.assertEqual(len(shadowed), 1)
            self.assertEqual(shadowed[0]['name'], 'alpha')
            self.assertIn('winner_path', shadowed[0])
            self.assertIn('shadowed_path', shadowed[0])


class DiagnosticsNoSkillsTests(unittest.TestCase):
    def test_diagnostics_no_skills(self) -> None:
        """Empty directory returns empty lists, not errors."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            diagnostics = get_skill_diagnostics(root)
            self.assertEqual(diagnostics['loaded_skills'], [])
            self.assertIsNone(diagnostics['active_skill'])
            self.assertEqual(diagnostics['shadowed_skills'], [])
            self.assertEqual(diagnostics['candidates'], [])
            self.assertEqual(diagnostics['candidate_count'], 0)
            self.assertIsInstance(diagnostics['long_result_artifacts'], dict)


class TuiSkillsCommandRegisteredTests(unittest.TestCase):
    def test_tui_skills_command_registered(self) -> None:
        """skill-diagnostics command is in the dispatch table."""
        self.assertIn('skill-diagnostics', _COMMAND_DISPATCH)
        handler = _COMMAND_DISPATCH['skill-diagnostics']
        self.assertTrue(callable(handler))

    def test_tui_skills_command_returns_true(self) -> None:
        """skill-diagnostics handler returns True (keep TUI running)."""
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        from teaagent.skill_loader import SkillActivationExplain

        fake_explain = SkillActivationExplain(
            selection_mode='index_only',
            selected_names=(),
            loaded=(),
            shadowed=(),
            skipped=(),
            warnings=(),
            searched_dirs=(Path('/tmp'),),
            estimated_skill_tokens=0,
            index_count=0,
            write_targets={},
        )
        with patch(
            'teaagent.skill_loader.explain_skill_activation',
            return_value=fake_explain,
        ):
            result = tui.handle_command('skill-diagnostics')
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
