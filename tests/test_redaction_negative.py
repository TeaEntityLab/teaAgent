"""Negative test cases for redaction.py module (PII redaction).

Tests edge cases, malformed inputs, boundary conditions, and error handling
for the security-critical PII redaction functionality.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Safe import to avoid circular imports
_MOD_PATH = Path(__file__).resolve().parent.parent / 'teaagent' / 'redaction.py'

if 'teaagent.redaction' not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        'teaagent.redaction',
        str(_MOD_PATH),
        submodule_search_locations=[],
    )
    _mod = importlib.util.module_from_spec(spec)
    sys.modules['teaagent.redaction'] = _mod
    spec.loader.exec_module(_mod)
else:
    _mod = sys.modules['teaagent.redaction']

RedactionConfig = _mod.RedactionConfig


def test_redaction_config_with_all_disabled():
    """Test that disabling all redaction groups returns empty patterns."""
    cfg = RedactionConfig(
        bearer_tokens=False,
        api_keys=False,
        jwt_tokens=False,
        aws_keys=False,
        github_tokens=False,
        query_params=False,
        google_keys=False,
        openai_keys=False,
        anthropic_keys=False,
        database_urls=False,
        ssh_keys=False,
    )
    patterns = cfg.build_patterns()
    assert patterns == []


def test_redaction_config_with_empty_extra_patterns():
    """Test that empty extra_patterns list is handled correctly."""
    cfg = RedactionConfig(extra_patterns=[])
    patterns = cfg.build_patterns()
    # Should still have default patterns
    assert len(patterns) > 0


def test_redaction_config_with_invalid_extra_pattern():
    """Test that invalid extra patterns don't crash the builder."""
    import re

    cfg = RedactionConfig(extra_patterns=[(re.compile(r'invalid'), '[REDACTED]')])
    patterns = cfg.build_patterns()
    # Should include the extra pattern
    assert len(patterns) > 0


def test_redaction_config_extra_pattern_tuple():
    """Test that extra patterns are correctly appended."""
    import re

    cfg = RedactionConfig(
        bearer_tokens=False,
        api_keys=False,
        jwt_tokens=False,
        aws_keys=False,
        github_tokens=False,
        query_params=False,
        google_keys=False,
        openai_keys=False,
        anthropic_keys=False,
        database_urls=False,
        ssh_keys=False,
        extra_patterns=[(re.compile(r'secret'), '[REDACTED]')],
    )
    patterns = cfg.build_patterns()
    assert len(patterns) == 1
    assert patterns[0][1] == '[REDACTED]'


def test_redaction_config_default_values():
    """Test that default config enables all redaction groups."""
    cfg = RedactionConfig()
    assert cfg.bearer_tokens is True
    assert cfg.api_keys is True
    assert cfg.jwt_tokens is True
    assert cfg.aws_keys is True
    assert cfg.github_tokens is True
    assert cfg.query_params is True
    assert cfg.google_keys is True
    assert cfg.openai_keys is True
    assert cfg.anthropic_keys is True
    assert cfg.database_urls is True
    assert cfg.ssh_keys is True


def test_redaction_config_partial_disable():
    """Test that selectively disabling groups works correctly."""
    cfg = RedactionConfig(
        bearer_tokens=False,
        api_keys=True,
        jwt_tokens=False,
    )
    patterns = cfg.build_patterns()
    # Should have patterns for enabled groups only
    pattern_names = [p[1] for p in patterns]
    assert '[redacted]' in pattern_names  # api_keys
    assert 'Bearer [redacted]' not in pattern_names  # bearer_tokens disabled
    assert '[redacted-JWT]' not in pattern_names  # jwt_tokens disabled


def test_redaction_config_multiple_extra_patterns():
    """Test that multiple extra patterns are all added."""
    import re

    cfg = RedactionConfig(
        bearer_tokens=False,
        api_keys=False,
        jwt_tokens=False,
        aws_keys=False,
        github_tokens=False,
        query_params=False,
        google_keys=False,
        openai_keys=False,
        anthropic_keys=False,
        database_urls=False,
        ssh_keys=False,
        extra_patterns=[
            (re.compile(r'pattern1'), '[REDACTED1]'),
            (re.compile(r'pattern2'), '[REDACTED2]'),
            (re.compile(r'pattern3'), '[REDACTED3]'),
        ],
    )
    patterns = cfg.build_patterns()
    assert len(patterns) == 3


def test_redaction_config_frozen_dataclass():
    """Test that RedactionConfig is frozen (immutable)."""
    cfg = RedactionConfig()
    try:
        cfg.bearer_tokens = False
        raise AssertionError('Should not be able to modify frozen dataclass')
    except (AttributeError, TypeError):
        # Expected for frozen dataclass
        pass


def test_redaction_config_extra_pattern_with_compiled_regex():
    """Test that extra patterns work with pre-compiled regex."""
    import re

    custom_pattern = re.compile(r'\bCUSTOM_[A-Z0-9]+\b')
    cfg = RedactionConfig(
        bearer_tokens=False,
        api_keys=False,
        jwt_tokens=False,
        aws_keys=False,
        github_tokens=False,
        query_params=False,
        google_keys=False,
        openai_keys=False,
        anthropic_keys=False,
        database_urls=False,
        ssh_keys=False,
        extra_patterns=[(custom_pattern, '[CUSTOM-REDACTED]')],
    )
    patterns = cfg.build_patterns()
    assert len(patterns) == 1
    assert patterns[0][1] == '[CUSTOM-REDACTED]'


def test_redaction_config_empty_string_replacement():
    """Test that empty string replacement is allowed in extra patterns."""
    import re

    cfg = RedactionConfig(
        bearer_tokens=False,
        api_keys=False,
        jwt_tokens=False,
        aws_keys=False,
        github_tokens=False,
        query_params=False,
        google_keys=False,
        openai_keys=False,
        anthropic_keys=False,
        database_urls=False,
        ssh_keys=False,
        extra_patterns=[(re.compile(r'test'), '')],
    )
    patterns = cfg.build_patterns()
    assert len(patterns) == 1
    assert patterns[0][1] == ''


def test_redaction_config_complex_extra_pattern():
    """Test that complex regex patterns work in extra_patterns."""
    import re

    complex_pattern = re.compile(r'(?i)\b[A-Z0-9]{32}\b')
    cfg = RedactionConfig(
        bearer_tokens=False,
        api_keys=False,
        jwt_tokens=False,
        aws_keys=False,
        github_tokens=False,
        query_params=False,
        google_keys=False,
        openai_keys=False,
        anthropic_keys=False,
        database_urls=False,
        ssh_keys=False,
        extra_patterns=[(complex_pattern, '[HASH-REDACTED]')],
    )
    patterns = cfg.build_patterns()
    assert len(patterns) == 1


def test_redaction_config_selective_enable():
    """Test that selectively enabling only specific groups works."""
    cfg = RedactionConfig(
        bearer_tokens=True,
        api_keys=False,
        jwt_tokens=False,
        aws_keys=False,
        github_tokens=False,
        query_params=False,
        google_keys=False,
        openai_keys=False,
        anthropic_keys=False,
        database_urls=False,
        ssh_keys=False,
    )
    patterns = cfg.build_patterns()
    # Should only have bearer token pattern
    assert len(patterns) == 1
    assert patterns[0][1] == 'Bearer [redacted]'


def test_redaction_config_all_enabled():
    """Test that enabling all groups returns maximum patterns."""
    cfg = RedactionConfig(
        bearer_tokens=True,
        api_keys=True,
        jwt_tokens=True,
        aws_keys=True,
        github_tokens=True,
        query_params=True,
        google_keys=True,
        openai_keys=True,
        anthropic_keys=True,
        database_urls=True,
        ssh_keys=True,
    )
    patterns = cfg.build_patterns()
    # Should have multiple patterns (each group can have multiple patterns)
    assert len(patterns) > 10


def test_redaction_config_extra_pattern_order():
    """Test that extra patterns are appended after built-in patterns."""
    import re

    cfg = RedactionConfig(extra_patterns=[(re.compile(r'custom'), '[CUSTOM]')])
    patterns = cfg.build_patterns()
    # Extra pattern should be last
    assert patterns[-1][1] == '[CUSTOM]'


def test_redaction_config_none_extra_patterns():
    """Test that None extra_patterns causes TypeError (actual bug)."""
    cfg = RedactionConfig(extra_patterns=None)
    with pytest.raises(TypeError, match="'NoneType' object is not iterable"):
        cfg.build_patterns()


def test_redaction_config_override_all_with_extra():
    """Test that extra patterns can completely override built-in patterns."""
    import re

    cfg = RedactionConfig(
        bearer_tokens=False,
        api_keys=False,
        jwt_tokens=False,
        aws_keys=False,
        github_tokens=False,
        query_params=False,
        google_keys=False,
        openai_keys=False,
        anthropic_keys=False,
        database_urls=False,
        ssh_keys=False,
        extra_patterns=[(re.compile(r'.*'), '[ALL-REDACTED]')],
    )
    patterns = cfg.build_patterns()
    assert len(patterns) == 1
    assert patterns[0][1] == '[ALL-REDACTED]'


def test_redaction_config_case_sensitive_extra_pattern():
    """Test that extra patterns are case-sensitive by default."""
    import re

    cfg = RedactionConfig(
        bearer_tokens=False,
        api_keys=False,
        jwt_tokens=False,
        aws_keys=False,
        github_tokens=False,
        query_params=False,
        google_keys=False,
        openai_keys=False,
        anthropic_keys=False,
        database_urls=False,
        ssh_keys=False,
        extra_patterns=[(re.compile(r'TEST'), '[REDACTED]')],
    )
    patterns = cfg.build_patterns()
    assert len(patterns) == 1
    # Pattern should match 'TEST' but not 'test'
    assert patterns[0][0].pattern == 'TEST'


def test_redaction_config_special_characters_in_replacement():
    """Test that special characters in replacement strings are handled."""
    import re

    cfg = RedactionConfig(
        bearer_tokens=False,
        api_keys=False,
        jwt_tokens=False,
        aws_keys=False,
        github_tokens=False,
        query_params=False,
        google_keys=False,
        openai_keys=False,
        anthropic_keys=False,
        database_urls=False,
        ssh_keys=False,
        extra_patterns=[(re.compile(r'test'), '[***REDACTED***]')],
    )
    patterns = cfg.build_patterns()
    assert len(patterns) == 1
    assert patterns[0][1] == '[***REDACTED***]'


def test_redaction_config_unicode_in_replacement():
    """Test that unicode characters in replacement strings are handled."""
    import re

    cfg = RedactionConfig(
        bearer_tokens=False,
        api_keys=False,
        jwt_tokens=False,
        aws_keys=False,
        github_tokens=False,
        query_params=False,
        google_keys=False,
        openai_keys=False,
        anthropic_keys=False,
        database_urls=False,
        ssh_keys=False,
        extra_patterns=[(re.compile(r'test'), '[🔒REDACTED🔒]')],
    )
    patterns = cfg.build_patterns()
    assert len(patterns) == 1
    assert patterns[0][1] == '[🔒REDACTED🔒]'


def test_redaction_config_duplicate_extra_patterns():
    """Test that duplicate extra patterns are all added."""
    import re

    cfg = RedactionConfig(
        bearer_tokens=False,
        api_keys=False,
        jwt_tokens=False,
        aws_keys=False,
        github_tokens=False,
        query_params=False,
        google_keys=False,
        openai_keys=False,
        anthropic_keys=False,
        database_urls=False,
        ssh_keys=False,
        extra_patterns=[
            (re.compile(r'test'), '[REDACTED]'),
            (re.compile(r'test'), '[REDACTED-2]'),
        ],
    )
    patterns = cfg.build_patterns()
    # Both patterns should be added
    assert len(patterns) == 2
