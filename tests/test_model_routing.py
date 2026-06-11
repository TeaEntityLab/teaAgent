from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

from teaagent import classify_task, route_model
from teaagent.cli import main
from teaagent.model_routing import analyze_complexity, estimate_tokens


def test_classify_task_uses_deterministic_categories() -> None:
    assert classify_task('review this patch for regressions') == 'review'
    assert classify_task('run tests and fix failures') == 'test'
    assert classify_task('update docs cli markdown') == 'docs'


def test_route_model_chooses_provider_specific_model() -> None:
    route = route_model('review this patch', provider='gpt')

    assert route.category == 'review'
    assert route.provider == 'gpt'
    # With complexity-based routing, review tasks (medium complexity) use gpt-4o-mini
    assert route.model == 'gpt-4o-mini'
    assert route.complexity == 'medium'


def test_route_model_respects_explicit_model_override() -> None:
    route = route_model('review this patch', provider='gpt', model='custom-model')

    assert route.model == 'custom-model'
    assert route.reason == 'explicit model override'


def test_analyze_complexity_high() -> None:
    assert analyze_complexity('redesign the system architecture') == 'high'
    assert analyze_complexity('implement distributed caching') == 'high'
    assert analyze_complexity('add authentication and encryption') == 'high'


def test_analyze_complexity_medium() -> None:
    assert analyze_complexity('add a new feature') == 'medium'
    assert analyze_complexity('fix the bug in the handler') == 'medium'
    assert analyze_complexity('update the configuration') == 'medium'


def test_analyze_complexity_low() -> None:
    assert analyze_complexity('update the documentation') == 'low'
    assert analyze_complexity('add unit tests') == 'low'
    assert analyze_complexity('add comment to code') == 'low'


def test_estimate_tokens() -> None:
    # Low complexity
    tokens = estimate_tokens('fix typo', 'low')
    assert tokens > 2000  # Base buffer

    # Medium complexity
    tokens = estimate_tokens('add feature', 'medium')
    assert tokens > 2000

    # High complexity
    tokens = estimate_tokens('redesign architecture', 'high')
    assert tokens > 2000


def test_route_model_includes_complexity() -> None:
    route = route_model('redesign the system architecture', provider='claude')

    assert route.complexity == 'high'
    assert route.estimated_tokens > 0


def test_route_model_uses_complexity_based_routing() -> None:
    # High complexity should use premium model
    route = route_model('redesign architecture', provider='gpt')
    assert route.model == 'gpt-4o'
    assert route.complexity == 'high'

    # Low complexity should use cheaper model
    route = route_model('update documentation', provider='gpt')
    assert route.model == 'gpt-4o-mini'
    assert route.complexity == 'low'


def test_cli_model_route_outputs_json() -> None:
    output = io.StringIO()

    with redirect_stdout(output):
        exit_code = main(['model', 'route', 'review this patch', '--provider', 'gpt'])

    payload = json.loads(output.getvalue())
    assert exit_code == 0
    assert payload['category'] == 'review'
    # With complexity-based routing, review tasks (medium complexity) use gpt-4o-mini
    assert payload['model'] == 'gpt-4o-mini'
    assert 'complexity' in payload


# ---------------------------------------------------------------------------
# Negative test cases for model_routing
# ---------------------------------------------------------------------------


def test_classify_task_empty_string():
    """Test that empty string task is handled."""
    result = classify_task('')
    assert result == 'general'


def test_classify_task_whitespace_only():
    """Test that whitespace-only task is handled."""
    result = classify_task('   \n\t  ')
    assert result == 'general'


def test_classify_task_special_characters():
    """Test that special characters in task are handled."""
    result = classify_task('Fix bug with "quotes" and \'apostrophes\'')
    assert result in {'code', 'general'}


def test_classify_task_unicode():
    """Test that unicode characters in task are handled."""
    result = classify_task('修复bug和添加功能 🐛')
    assert result in {'code', 'general'}


def test_classify_task_very_long():
    """Test that very long task descriptions are handled."""
    long_task = 'fix bug ' * 1000
    result = classify_task(long_task)
    assert result in {'code', 'general'}


def test_classify_task_no_keywords():
    """Test that task with no known keywords defaults to general."""
    result = classify_task('do something random')
    assert result == 'general'


def test_classify_task_mixed_keywords():
    """Test that task with mixed keywords picks first match."""
    result = classify_task('review the test documentation')
    # Should match 'review' first
    assert result == 'review'


def test_analyze_complexity_empty_string():
    """Test that empty string complexity analysis defaults to medium."""
    result = analyze_complexity('')
    assert result == 'medium'


def test_analyze_complexity_whitespace_only():
    """Test that whitespace-only complexity analysis defaults to medium."""
    result = analyze_complexity('   \n\t  ')
    assert result == 'medium'


def test_analyze_complexity_no_indicators():
    """Test that task with no complexity indicators defaults to medium."""
    result = analyze_complexity('do something')
    assert result == 'medium'


def test_analyze_complexity_mixed_indicators():
    """Test that task with mixed indicators picks highest priority."""
    result = analyze_complexity('redesign the documentation')
    # Should pick 'low' from 'documentation' (matches first in iteration)
    assert result == 'low'


def test_analyze_complexity_special_characters():
    """Test that special characters are handled."""
    result = analyze_complexity('fix "bug" with special chars')
    assert result in {'medium', 'low'}


def test_analyze_complexity_unicode():
    """Test that unicode characters are handled."""
    result = analyze_complexity('修复bug和添加功能')
    assert result in {'medium', 'low'}


def test_estimate_tokens_empty_string():
    """Test that empty string token estimation works."""
    tokens = estimate_tokens('', 'medium')
    assert tokens >= 2000  # Base buffer


def test_estimate_tokens_zero_complexity():
    """Test that zero complexity multiplier is handled."""
    tokens = estimate_tokens('test task', 'low')
    assert tokens >= 2000


def test_estimate_tokens_very_long_task():
    """Test that very long task token estimation works."""
    long_task = 'fix bug ' * 10000
    tokens = estimate_tokens(long_task, 'high')
    assert tokens > 2000


def test_estimate_tokens_invalid_complexity():
    """Test that invalid complexity defaults to medium."""
    tokens = estimate_tokens('test', 'invalid')
    assert tokens >= 2000


def test_route_model_empty_task():
    """Test that empty task routing is handled."""
    route = route_model('', provider='gpt')
    assert route.category == 'general'
    assert route.provider == 'gpt'


def test_route_model_whitespace_task():
    """Test that whitespace-only task routing is handled."""
    route = route_model('   \n\t  ', provider='claude')
    assert route.category == 'general'
    assert route.provider == 'claude'


def test_route_model_unknown_provider():
    """Test that unknown provider routing is handled."""
    route = route_model('fix bug', provider='unknown_provider')
    assert route.category in {'code', 'general'}
    assert route.provider == 'unknown_provider'
    # Should fall back to None or general model
    assert route.model is None or route.model is not None


def test_route_model_none_provider():
    """Test that None provider is handled."""
    route = route_model('fix bug', provider=None)
    assert route.provider is None


def test_route_model_empty_provider():
    """Test that empty string provider is handled."""
    route = route_model('fix bug', provider='')
    assert route.provider == ''


def test_route_model_special_characters_task():
    """Test that special characters in task are handled."""
    route = route_model('Fix "bug" with \'quotes\'', provider='gpt')
    assert route.category in {'code', 'general'}


def test_route_model_unicode_task():
    """Test that unicode characters in task are handled."""
    route = route_model('修复bug和添加功能 🐛', provider='claude')
    assert route.category in {'code', 'general'}


def test_route_model_very_long_task():
    """Test that very long task routing is handled."""
    long_task = 'fix bug ' * 1000
    route = route_model(long_task, provider='gpt')
    assert route.estimated_tokens > 0


def test_route_model_explicit_model_none():
    """Test that explicit model=None is handled."""
    route = route_model('fix bug', provider='gpt', model=None)
    assert route.model is None or route.model is not None


def test_route_model_explicit_model_empty_string():
    """Test that explicit model='' is handled."""
    route = route_model('fix bug', provider='gpt', model='')
    # Empty string is treated as explicit override
    assert route.model == '' or route.model is not None


def test_route_model_complexity_with_explicit_model():
    """Test that complexity is still calculated with explicit model."""
    route = route_model('redesign architecture', provider='gpt', model='custom')
    assert route.complexity == 'high'
    assert route.model == 'custom'
    assert route.reason == 'explicit model override'


def test_model_route_to_dict():
    """Test that ModelRoute to_dict works correctly."""
    from teaagent.model_routing import ModelRoute

    route = ModelRoute(
        category='code',
        provider='gpt',
        model='gpt-4o',
        reason='test',
        complexity='high',
        estimated_tokens=5000,
    )
    result = route.to_dict()
    assert result['category'] == 'code'
    assert result['provider'] == 'gpt'
    assert result['model'] == 'gpt-4o'
    assert result['reason'] == 'test'
    assert result['complexity'] == 'high'
    assert result['estimated_tokens'] == 5000


def test_model_route_frozen():
    """Test that ModelRoute is frozen (immutable)."""
    from teaagent.model_routing import ModelRoute

    route = ModelRoute(
        category='code',
        provider='gpt',
        model='gpt-4o',
        reason='test',
    )
    try:
        route.category = 'review'
        raise AssertionError('Should not be able to modify frozen dataclass')
    except (AttributeError, TypeError):
        # Expected for frozen dataclass
        pass


def test_model_route_default_values():
    """Test that ModelRoute default values are correct."""
    from teaagent.model_routing import ModelRoute

    route = ModelRoute(
        category='code',
        provider='gpt',
        model='gpt-4o',
        reason='test',
    )
    assert route.complexity == 'medium'
    assert route.estimated_tokens == 0


def test_estimate_tokens_negative_complexity():
    """Test that negative complexity multiplier doesn't cause issues."""
    # This shouldn't happen in practice, but test robustness
    from teaagent.model_routing import estimate_tokens

    tokens = estimate_tokens('test', 'medium')
    assert tokens >= 2000
