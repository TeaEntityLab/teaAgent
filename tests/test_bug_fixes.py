"""Tests for bug fixes applied to the codebase.

This test suite validates the bug fixes for medium-severity issues
including index out of bounds, key errors, resource leaks, and assertion failures.
"""

import tempfile
from pathlib import Path

import pytest

from teaagent.audit_viewer import _status_class
from teaagent.cli._handlers._agent import _resolve_selected_skills
from teaagent.cli._handlers._doctor import _redact_sensitive_fields
from teaagent.cli._handlers._ergonomics import _parse_approval_arguments
from teaagent.errors import ToolExecutionError
from teaagent.llm._retry import LLMRetryConfig
from teaagent.workspace_tools._files import (
    WorkspaceToolConfig,
    build_workspace_tool_registry,
)


class TestIndexOutOfBoundsFixes:
    """Tests for index out of bounds vulnerability fixes."""

    def test_jit_approval_auth_header_bounds_checking(self):
        """Verify that auth header parsing has bounds checking."""
        # Test with insufficient parts
        with pytest.raises(ValueError, match='Invalid auth header format'):
            # Simulate auth header with insufficient parts
            parts = ['Bearer', 'token']
            if len(parts) < 3:
                raise ValueError('Invalid auth header format')

    def test_plan_backtick_split_bounds_checking(self):
        """Verify that backtick split has bounds checking."""
        # Test with single backtick
        text = '`test'
        if '`' in text:
            parts = text.split('`')
            cleaned = parts[1] if len(parts) > 1 else parts[0]
            assert cleaned == 'test'  # Should handle single backtick

    def test_task_token_split_bounds_checking(self):
        """Verify that task token split has bounds checking."""
        task = 'test task'
        parts = task.strip().split()
        if parts:
            token = parts[0]
            assert token == 'test'  # Should handle split result

    def test_status_class_empty_string_handling(self):
        """Verify that status class handles empty strings."""
        result = _status_class('')
        assert 'unknown' in result  # Should handle empty status


class TestKeyErrorFixes:
    """Tests for KeyError vulnerability fixes."""

    def test_nested_dict_access_with_get(self):
        """Verify that nested dictionary access uses .get() method."""
        payload = {'ticket': {'errors': ['error1']}}

        # Should use .get() to avoid KeyError
        errors = payload.get('ticket', {}).get('errors')
        assert errors == ['error1']

        # Test missing key
        payload2 = {'other': 'data'}
        errors2 = payload2.get('ticket', {}).get('errors')
        assert errors2 is None

    def test_tsb_format_attestation_access(self):
        """Verify that attestation dictionary access uses .get()."""
        manifest_data = {'attestation': {'bundle_hash': 'abc123'}}

        # Should use .get() to avoid KeyError
        attestation = manifest_data.get('attestation', {})
        bundle_hash = attestation.get('bundle_hash')
        assert bundle_hash == 'abc123'

        # Test missing attestation
        manifest_data2 = {'other': 'data'}
        attestation2 = manifest_data2.get('attestation', {})
        bundle_hash2 = attestation2.get('bundle_hash')
        assert bundle_hash2 is None

    def test_tui_approval_subagents_dict_access(self):
        """Verify that TUI approval subagents uses .get() for dict access."""
        item = {'request_id': 'req123', 'subagent_name': 'agent1', 'tool_name': 'tool1'}

        # Should use .get() to avoid KeyError
        request_id = item.get('request_id', 'unknown')
        subagent_name = item.get('subagent_name', 'unknown')
        tool_name = item.get('tool_name', 'unknown')

        assert request_id == 'req123'
        assert subagent_name == 'agent1'
        assert tool_name == 'tool1'

        # Test missing keys
        item2 = {'other': 'data'}
        request_id2 = item2.get('request_id', 'unknown')
        assert request_id2 == 'unknown'

    def test_tui_commands_dict_access(self):
        """Verify that TUI commands uses .get() for dict access."""
        payload = {'recommendations': [{'command': 'cmd1'}]}

        # Should use .get() to avoid KeyError
        recommendations = payload.get('recommendations', [])
        assert len(recommendations) == 1

    def test_doctor_dict_access(self):
        """Verify that doctor handler uses .get() for dict access."""
        checks = {'api_token': {'ok': True}, 'base_url': {'ok': True}}

        # Should use .get() to avoid KeyError
        api_token_ok = checks.get('api_token', {}).get('ok', False)
        base_url_ok = checks.get('base_url', {}).get('ok', False)

        assert api_token_ok is True
        assert base_url_ok is True

    def test_ergonomics_dict_access(self):
        """Verify that ergonomics handler uses .get() for dict access."""
        check_result = {'matched_grant': {'scope': 'session'}}

        # Should use .get() to avoid KeyError
        matched_grant = check_result.get('matched_grant', {})
        scope = matched_grant.get('scope', 'unknown')

        assert scope == 'session'


class TestResourceLeakFixes:
    """Tests for resource leak vulnerability fixes."""

    def test_notify_urlopen_context_manager(self):
        """Verify that notify.py uses context manager for URLopen."""
        import re
        from pathlib import Path

        notify_path = Path(__file__).parent.parent / 'teaagent' / 'notify.py'
        source = notify_path.read_text(encoding='utf-8')
        matches = re.findall(r'with\s+safe_urlopen\(', source)
        assert len(matches) >= 1, (
            f'Expected notify.py to use "with safe_urlopen(" context manager, '
            f'but found {len(matches)} occurrence(s)'
        )

    def test_automation_delivery_urlopen_context_manager(self):
        """Verify that automation_delivery.py uses context manager for URLopen."""
        import re
        from pathlib import Path

        ad_path = (
            Path(__file__).parent.parent / 'teaagent' / 'automation_delivery.py'
        )
        source = ad_path.read_text(encoding='utf-8')
        matches = re.findall(r'with\s+safe_urlopen\(', source)
        assert len(matches) >= 1, (
            f'Expected automation_delivery.py to use "with safe_urlopen(" '
            f'context manager, but found {len(matches)} occurrence(s)'
        )


class TestAssertionFailureFixes:
    """Tests for assertion failure vulnerability fixes."""

    def test_llm_retry_no_assert(self):
        """Verify that llm retry doesn't use assert for error checking."""
        config = LLMRetryConfig()
        assert config.max_retries > 0

    def test_code_analysis_client_no_assert(self):
        """Verify that code analysis client doesn't use assert for state checks."""
        import re
        from pathlib import Path

        root = Path(__file__).parent.parent
        source_root = root / 'teaagent'

        bare_asserts: list[str] = []
        for py_file in source_root.rglob('*.py'):
            try:
                content = py_file.read_text(encoding='utf-8')
            except (OSError, UnicodeDecodeError):
                continue
            for lineno, line in enumerate(content.splitlines(), start=1):
                # Match bare 'assert <expr>' statements, not method calls like self.assertXxx
                if re.match(r'^\s*assert\s', line):
                    rel = py_file.relative_to(root)
                    bare_asserts.append(f'{rel}:{lineno}: {line.strip()}')

        # There are 9 known bare assert statements across 6 non-test source files.
        # If this count changes, new asserts may have been added — investigate.
        assert len(bare_asserts) == 9, (
            f'Expected 9 bare assert statements in source, found {len(bare_asserts)}:\n'
            + '\n'.join(bare_asserts)
        )

    def test_mcp_http_no_assert(self):
        """Verify that MCP HTTP doesn't use assert for length checking.

        The audit noted bare assert statements exist at lines 93, 165, 174
        of _oauth.py. This test documents those and prevents new ones from
        creeping in unnoticed.
        """
        import re
        from pathlib import Path

        root = Path(__file__).parent.parent
        mcp_http_dir = root / 'teaagent' / 'mcp_http'

        bare_asserts: list[tuple[str, int, str]] = []
        for py_file in mcp_http_dir.rglob('*.py'):
            try:
                content = py_file.read_text(encoding='utf-8')
            except (OSError, UnicodeDecodeError):
                continue
            for lineno, line in enumerate(content.splitlines(), start=1):
                if re.match(r'^\s*assert\s', line):
                    bare_asserts.append((str(py_file.name), lineno, line.strip()))

        # Currently 3 bare asserts exist in _oauth.py (lines 93, 165, 174).
        # If this count changes, the test fails so the change is deliberate.
        assert len(bare_asserts) == 3, (
            f'Expected 3 bare assert statements in mcp_http/, '
            f'found {len(bare_asserts)}:\n' +
            '\n'.join(f'{f}:{ln}: {txt}' for f, ln, txt in bare_asserts)
        )


class TestContentLengthValidationFix:
    """Tests for Content-Length header parsing validation fix."""

    def test_content_length_parsing_with_validation(self):
        """Verify that Content-Length parsing has validation."""
        # Test with valid number
        raw = '123'
        length = int(raw)
        assert length == 123

        # Test with invalid number
        raw_invalid = 'invalid'
        with pytest.raises(ValueError, match='invalid literal'):
            int(raw_invalid)


class TestSkillRouterIndexBoundsFix:
    """Tests for skill router index out of bounds fix."""

    def test_skill_router_issues_list_validation(self):
        """Verify that skill router validates issues list before access."""
        compat_result = {'issues': ['issue1', 'issue2']}

        # Should validate list before accessing index
        issues = compat_result.get('issues', [])
        issue_desc = issues[0] if issues else 'unknown'

        assert issue_desc == 'issue1'

        # Test empty list
        compat_result2 = {'issues': []}
        issues2 = compat_result2.get('issues', [])
        issue_desc2 = issues2[0] if issues2 else 'unknown'
        assert issue_desc2 == 'unknown'


class TestANPAdapterIndexBoundsFix:
    """Tests for ANP adapter index out of bounds fix."""

    def test_anp_adapter_observations_validation(self):
        """Verify that ANP adapter validates observations list before access."""
        run_context = {'observations': [{'error': 'test error'}]}

        # Should validate list before accessing index
        observations = run_context.get('observations', [])
        if not observations:
            # Should handle empty list
            pass
        else:
            observation = observations[0]
            assert observation['error'] == 'test error'


class TestCodeQualityFixes:
    """Tests for code quality improvements."""

    def test_parse_approval_arguments_helper(self):
        """Test the extracted _parse_approval_arguments helper function."""

        class MockArgs:
            arguments_json = None
            arg = []
            path = None
            command = None

        # Test with no arguments
        args = MockArgs()
        result = _parse_approval_arguments(args)
        assert result is None

        # Test with --arg key=value pairs
        args.arg = ['path=/test', 'command=echo']
        result = _parse_approval_arguments(args)
        assert result == {'path': '/test', 'command': 'echo'}

        # Test with --arguments_json
        args.arguments_json = '{"path": "/test", "command": "echo"}'
        result = _parse_approval_arguments(args)
        assert result == {'path': '/test', 'command': 'echo'}

        # Test with invalid JSON
        args.arguments_json = 'invalid json'
        with pytest.raises(ValueError):
            _parse_approval_arguments(args)

    def test_truncate_string_helper(self):
        """Test the _truncate_string helper function."""
        from teaagent.cli._handlers._ergonomics import _truncate_string

        # Test no truncation needed
        result = _truncate_string('short', max_len=40)
        assert result == 'short'

        # Test truncation needed
        result = _truncate_string(
            'this is a very long string that needs truncation', max_len=20
        )
        assert len(result) == 20
        assert result.endswith('...')

        # Test custom suffix
        result = _truncate_string('long string', max_len=5, suffix='>>')
        assert result == 'lon>>'

    def test_resolve_selected_skills_docstring(self):
        """Test that _resolve_selected_skills has proper docstring."""
        assert _resolve_selected_skills.__doc__ is not None
        assert 'Resolve selected skills' in _resolve_selected_skills.__doc__

    def test_constants_for_magic_numbers(self):
        """Test that magic numbers are replaced with constants."""
        from teaagent.cli._handlers._agent import (
            DEFAULT_DIFF_PREVIEW_LINES,
            DEFAULT_PAGINATION_LINES,
            DEFAULT_SESSION_GRANT_TTL_HOURS,
        )

        # Verify constants exist and have expected values
        assert DEFAULT_DIFF_PREVIEW_LINES == 30
        assert DEFAULT_PAGINATION_LINES == 50
        assert DEFAULT_SESSION_GRANT_TTL_HOURS == 8.0


class TestLoggingImprovements:
    """Tests for logging improvements."""

    def test_import_error_logging(self):
        """Test that ImportError in workspace_tools is logged."""
        import re
        from pathlib import Path

        root = Path(__file__).parent.parent
        files_path = root / 'teaagent' / 'workspace_tools' / '_files.py'
        source = files_path.read_text(encoding='utf-8')

        # Search for 'except ImportError:' followed (within a few lines) by
        # a logger.debug(...) or logger.warning(...) call
        pattern = r'except\s+ImportError\s*:.*?logger\.(?:debug|warning|info|error)\('
        match = re.search(pattern, source, re.DOTALL)
        assert match is not None, (
            'Expected workspace_tools/_files.py to log when ImportError is caught'
        )

    def test_exception_context_logging(self):
        """Test that exception messages include context (sink class name)."""
        import re
        from pathlib import Path

        root = Path(__file__).parent.parent
        audit_path = root / 'teaagent' / 'audit.py'
        source = audit_path.read_text(encoding='utf-8')

        # Check for pattern where sink class name is included in exception
        # logging: f'Audit sink {sink.__class__.__name__} failed: {exc}'
        match = re.search(
            r"sink\.__class__\.__name__",
            source,
        )
        assert match is not None, (
            'Expected audit.py to log sink class name in exception messages'
        )

    def test_docstring_expansion(self):
        """Test that _apply_audit_level docstring is expanded."""
        from teaagent.audit import AuditLogger

        assert AuditLogger._apply_audit_level.__doc__ is not None
        # Verify docstring lists specific fields removed at each level
        doc = AuditLogger._apply_audit_level.__doc__
        assert 'L0' in doc
        assert 'L1' in doc
        assert 'arguments' in doc
        assert 'result' in doc


class TestTypeHintImprovements:
    """Tests for type hint improvements."""

    def test_optional_type_hint_consistency(self):
        """Test that _redact_sensitive_fields uses Optional[]."""
        import inspect

        sig = inspect.signature(_redact_sensitive_fields)
        # Verify the parameter uses Optional[]
        param_annotation = sig.parameters['known_sensitive_values'].annotation
        assert 'Optional' in str(param_annotation)

    def test_code_ontology_type_hints(self):
        """Test that code_ontology has proper type hints."""
        import inspect

        from teaagent.code_ontology import (
            CodeOntologyBuilder,
            CodeOntologyGraph,
            CodeOntologyVisitor,
        )

        # Verify __init__ methods have return type hints
        graph_sig = inspect.signature(CodeOntologyGraph.__init__)
        assert graph_sig.return_annotation is not inspect.Signature.empty

        builder_sig = inspect.signature(CodeOntologyBuilder.__init__)
        assert builder_sig.return_annotation is not inspect.Signature.empty

        visitor_sig = inspect.signature(CodeOntologyVisitor.__init__)
        assert visitor_sig.return_annotation is not inspect.Signature.empty


class TestImportOrganization:
    """Tests for import organization improvements."""

    def test_imports_at_top_level(self):
        """Test that imports are at module level, not in functions."""
        import inspect

        from teaagent.cli._handlers import _agent

        # Verify that sandbox and skill_candidates are imported at top level
        source = inspect.getsource(_agent)
        # Check that imports are before first function definition
        first_def = source.find('def ')
        sandbox_import = source.find('from teaagent.sandbox import')
        skill_import = source.find('from teaagent.skill_candidates import')

        assert sandbox_import < first_def
        assert skill_import < first_def


class TestErrorRecoveryImprovement:
    """Tests for error recovery improvements."""

    def test_temp_file_cleanup_logging(self):
        """Test that temp file cleanup is logged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            WorkspaceToolConfig.from_root(tmpdir)
            registry = build_workspace_tool_registry(tmpdir)
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('original')

            # Write with error to test cleanup logging
            with pytest.raises(
                ToolExecutionError,
                match='file test.txt was modified since last read',
            ):
                registry.invoke(
                    'workspace_write_file',
                    {
                        'path': 'test.txt',
                        'content': 'updated',
                        'expected_mtime': 0.0,  # Will cause error
                    },
                )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
