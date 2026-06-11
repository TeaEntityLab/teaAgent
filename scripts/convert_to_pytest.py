#!/usr/bin/env python3
"""Script to convert unittest test files to pytest."""

import re
from pathlib import Path


def convert_file(file_path: Path) -> tuple[bool, str]:
    """Convert a single test file from unittest to pytest."""
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content

        # 1. Replace import unittest with import pytest
        content = re.sub(r'import unittest', 'import pytest', content)

        # 2. Remove class definitions and convert methods to functions
        # Find class definitions and their methods
        class_pattern = r'class (\w+)\(unittest\.TestCase\):\s*\n(.*?)(?=\nclass |\Z)'

        def replace_class(match):
            class_body = match.group(2)

            # Convert all methods in this class to standalone functions
            # Remove 'def test_' indentation and convert to module-level functions
            lines = class_body.split('\n')
            result = []
            for line in lines:
                if line.strip().startswith('def test_'):
                    # Remove indentation for test methods
                    result.append(re.sub(r'^\s+', '', line))
                elif line.strip().startswith('def _'):
                    # Convert helper methods to module-level
                    result.append(re.sub(r'^\s+', '', line))
                elif line.strip().startswith('@staticmethod'):
                    # Remove @staticmethod decorator
                    continue
                elif line.strip() and not line.strip().startswith('#'):
                    # Keep other lines but remove extra indentation
                    if (
                        line.strip().startswith('def ')
                        or line.strip().startswith('with ')
                        or line.strip().startswith('if ')
                        or line.strip().startswith('for ')
                        or line.strip().startswith('return ')
                        or line.strip().startswith('assert ')
                        or line.strip().startswith('raise ')
                    ):
                        result.append(re.sub(r'^\s+', '', line))
                    else:
                        result.append(line)

            return '\n'.join(result)

        content = re.sub(class_pattern, replace_class, content, flags=re.DOTALL)

        # 3. Replace self.assert* methods with plain assert statements
        replacements = [
            (r'self\.assertEqual\(([^,]+),\s*([^)]+)\)', r'assert \1 == \2'),
            (r'self\.assertNotEqual\(([^,]+),\s*([^)]+)\)', r'assert \1 != \2'),
            (r'self\.assertTrue\(([^)]+)\)', r'assert \1'),
            (r'self\.assertFalse\(([^)]+)\)', r'assert not \1'),
            (r'self\.assertIs\(([^,]+),\s*([^)]+)\)', r'assert \1 is \2'),
            (r'self\.assertIsNot\(([^,]+),\s*([^)]+)\)', r'assert \1 is not \2'),
            (r'self\.assertIsNone\(([^)]+)\)', r'assert \1 is None'),
            (r'self\.assertIsNotNone\(([^)]+)\)', r'assert \1 is not None'),
            (r'self\.assertIn\(([^,]+),\s*([^)]+)\)', r'assert \1 in \2'),
            (r'self\.assertNotIn\(([^,]+),\s*([^)]+)\)', r'assert \1 not in \2'),
            (
                r'self\.assertIsInstance\(([^,]+),\s*([^)]+)\)',
                r'assert isinstance(\1, \2)',
            ),
            (
                r'self\.assertRaises\(([^,]+),\s*([^)]+)\)',
                r'with pytest.raises(\1):\n        \2',
            ),
            (r'self\.assertGreater\(([^,]+),\s*([^)]+)\)', r'assert \1 > \2'),
            (r'self\.assertLess\(([^,]+),\s*([^)]+)\)', r'assert \1 < \2'),
            (r'self\.assertGreaterEqual\(([^,]+),\s*([^)]+)\)', r'assert \1 >= \2'),
            (r'self\.assertLessEqual\(([^,]+),\s*([^)]+)\)', r'assert \1 <= \2'),
            (
                r'self\.assertAlmostEqual\(([^,]+),\s*([^,]+),\s*places=(\d+)\)',
                r'assert \1 == pytest.approx(\2, abs=\3)',
            ),
            (
                r'self\.assertAlmostEqual\(([^,]+),\s*([^)]+)\)',
                r'assert \1 == pytest.approx(\2)',
            ),
            (
                r'self\.assertRaisesRegex\(([^,]+),\s*([^,]+),\s*([^)]+)\)',
                r'with pytest.raises(\1, match=\2):\n        \3',
            ),
            (r'self\.assertRegex\(([^,]+),\s*([^)]+)\)', r'assert re.search(\2, \1)'),
            (r'self\.assertDictEqual\(([^,]+),\s*([^)]+)\)', r'assert \1 == \2'),
            (r'self\.assertListEqual\(([^,]+),\s*([^)]+)\)', r'assert \1 == \2'),
            (
                r'self\.assertCountEqual\(([^,]+),\s*([^)]+)\)',
                r'assert sorted(\1) == sorted(\2)',
            ),
            (r'self\.assertMultiLineEqual\(([^,]+),\s*([^)]+)\)', r'assert \1 == \2'),
            (r'self\.assertSequenceEqual\(([^,]+),\s*([^)]+)\)', r'assert \1 == \2'),
            (r'self\.assertSetEqual\(([^,]+),\s*([^)]+)\)', r'assert \1 == \2'),
            (r'self\.assertTupleEqual\(([^,]+),\s*([^)]+)\)', r'assert \1 == \2'),
        ]

        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content)

        # 4. Replace self.assertRaises with pytest.raises (more complex cases)
        # Handle: with self.assertRaises(Exception) as ctx:
        content = re.sub(
            r'with self\.assertRaises\(([^)]+)\) as ctx:',
            r'with pytest.raises(\1) as ctx:',
            content,
        )
        # Handle: with self.assertRaises(Exception):
        content = re.sub(
            r'with self\.assertRaises\(([^)]+)\):', r'with pytest.raises(\1):', content
        )

        # 5. Replace self.assertIn with in operator
        content = re.sub(
            r'self\.assertIn\(([^,]+),\s*([^)]+)\)', r'assert \1 in \2', content
        )
        content = re.sub(
            r'self\.assertNotIn\(([^,]+),\s*([^)]+)\)', r'assert \1 not in \2', content
        )

        # 6. Remove if __name__ == '__main__': unittest.main() blocks
        content = re.sub(
            r"if __name__ == '__main__':\s*\n\s*unittest\.main\(\)", '', content
        )

        # 7. Convert helper methods from self._method() to _method()
        content = re.sub(r'self\._([a-zA-Z_][a-zA-Z0-9_]*)\(', r'_\1(', content)

        # 8. Remove self.skipTest and replace with pytest.skip
        content = re.sub(r'self\.skipTest\(([^)]+)\)', r'pytest.skip(\1)', content)

        # 9. Remove self.assertLogs and replace with caplog fixture
        # This is more complex, so we'll leave it for manual review
        # content = re.sub(r'with self\.assertLogs\(([^)]+)\) as (ctx|log_ctx):', r'', content)

        # 10. Clean up extra blank lines
        content = re.sub(r'\n\n\n+', '\n\n', content)

        # Write back if changed
        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            return True, 'Converted successfully'
        else:
            return False, 'No changes needed'

    except Exception as e:
        return False, f'Error: {e}'


def main():
    files = [
        'tests/test_audit.py',
        'tests/test_policy.py',
        'tests/test_budget.py',
        'tests/test_schema.py',
        'tests/test_errors.py',
        'tests/test_preflight.py',
        'tests/test_first_run.py',
        'tests/test_phase_budget.py',
        'tests/test_scope_creep.py',
        'tests/test_context_health.py',
    ]

    results = []
    for file_path_str in files:
        file_path = Path(file_path_str)
        if not file_path.exists():
            results.append((file_path_str, False, 'File not found'))
            continue

        success, message = convert_file(file_path)
        results.append((file_path_str, success, message))

    print('\nConversion Results:')
    print('=' * 60)
    for file_path, success, message in results:
        status = '✓' if success else '✗'
        print(f'{status} {file_path}: {message}')


if __name__ == '__main__':
    main()
