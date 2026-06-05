"""Tests for role-based model routing resolution.

Verifies that the model routing system resolves the correct model/provider
for each agent role (plan, execution, review, security).
"""

from __future__ import annotations

from teaagent.model_routing import route_model
from teaagent.run_evidence import ModelRouteEvidence, extract_routes


def test_plan_role_resolves_correct_model() -> None:
    """Plan role resolves to general/default category with correct model."""
    route = route_model('plan the project', provider='gpt')
    assert route.category == 'general'
    assert route.model == 'gpt-4o-mini'
    assert route.complexity == 'medium'
    assert route.provider == 'gpt'
    assert 'general' in route.reason

    route_c = route_model('plan the project', provider='claude')
    assert route_c.category == 'general'
    assert route_c.model == 'claude-3-5-sonnet-latest'
    assert route_c.provider == 'claude'


def test_execution_role_resolves_correct_model() -> None:
    """Execution role resolves to code category with correct model."""
    route = route_model('implement the new feature', provider='gpt')
    assert route.category == 'code'
    assert route.model is not None
    assert route.provider == 'gpt'
    assert 'code' in route.reason

    route_g = route_model('implement the new feature', provider='gemini')
    assert route_g.category == 'code'
    assert route_g.model == 'gemini-1.5-flash'
    assert route_g.provider == 'gemini'

    route_c = route_model('implement the new feature', provider='claude')
    assert route_c.category == 'code'
    assert route_c.model == 'claude-3-5-sonnet-latest'
    assert route_c.provider == 'claude'


def test_review_role_resolves_correct_model() -> None:
    """Review role resolves to review category with correct model."""
    route = route_model('review the pull request', provider='gpt')
    assert route.category == 'review'
    assert route.model is not None
    assert route.provider == 'gpt'
    assert 'review' in route.reason

    route_c = route_model('review the pull request', provider='claude')
    assert route_c.category == 'review'
    assert route_c.model == 'claude-3-5-sonnet-latest'
    assert route_c.provider == 'claude'

    route_o = route_model('review the system architecture', provider='openrouter')
    assert route_o.category == 'review'
    assert route_o.model == 'anthropic/claude-3.5-sonnet'
    assert route_o.complexity == 'high'
    assert route_o.provider == 'openrouter'


def test_security_role_resolves_correct_model() -> None:
    """Security role routes to review category (security keyword) with high-complexity model."""
    route = route_model('security audit the system', provider='gpt')
    assert route.category == 'review'
    assert route.model == 'gpt-4o'
    assert route.complexity == 'high'
    assert route.provider == 'gpt'

    route_c = route_model('security audit the system', provider='claude')
    assert route_c.category == 'review'
    assert route_c.model == 'claude-3-5-sonnet-latest'
    assert route_c.complexity == 'high'

    route_g = route_model('security audit the system', provider='gemini')
    assert route_g.category == 'review'
    assert route_g.model == 'gemini-1.5-pro'
    assert route_g.complexity == 'high'


def test_role_routing_produces_model_route_evidence() -> None:
    """Each role produces a ModelRouteEvidence with correct fields."""
    route = route_model('review the code', provider='gpt')

    evidence = ModelRouteEvidence(
        requested_provider='gpt',
        requested_model='',
        resolved_provider=route.provider,
        resolved_model=route.model or '',
        role=route.category,
        routing_reason=route.reason,
        policy_source='complexity',
    )
    assert evidence.role == 'review'
    assert evidence.resolved_provider == 'gpt'
    assert evidence.resolved_model == route.model
    assert evidence.requested_provider == 'gpt'
    assert evidence.policy_source == 'complexity'
    assert evidence.fallback_used is False
    assert evidence.routing_reason == route.reason

    events = [
        {
            'event_type': 'model_route',
            'payload': {
                'requested_provider': 'gpt',
                'requested_model': '',
                'resolved_provider': route.provider,
                'resolved_model': route.model or '',
                'role': route.category,
                'routing_reason': route.reason,
                'policy_source': 'complexity',
                'estimated_cost_cents': 0.0,
                'actual_cost_cents': 0.0,
                'fallback_used': False,
            },
            'created_at': 1700000000.0,
        }
    ]
    extracted = extract_routes(events)
    assert len(extracted) == 1
    assert extracted[0].role == 'review'
    assert extracted[0].resolved_model == route.model
    assert extracted[0].policy_source == 'complexity'


def test_role_routing_preserves_all_roles_in_evidence() -> None:
    """ModelRouteEvidence preserves role information across all role types."""
    roles = {
        'plan': 'plan the project',
        'execute': 'build the module',
        'review': 'audit the codebase',
        'security': 'security review',
    }

    for _role_name, task in roles.items():
        route = route_model(task, provider='gpt')
        evidence = ModelRouteEvidence(
            requested_provider='gpt',
            requested_model='',
            resolved_provider=route.provider,
            resolved_model=route.model or '',
            role=route.category,
            routing_reason=route.reason,
            policy_source='complexity',
        )
        assert evidence.role == route.category
        assert evidence.resolved_provider == 'gpt'
        assert evidence.resolved_model is not None
        assert evidence.routing_reason


def test_role_routing_serializes_to_dict() -> None:
    """ModelRouteEvidence serialization includes role and model fields."""
    route = route_model('review the code', provider='gpt')
    evidence = ModelRouteEvidence(
        requested_provider='gpt',
        requested_model='',
        resolved_provider=route.provider,
        resolved_model=route.model or '',
        role=route.category,
        routing_reason=route.reason,
        policy_source='complexity',
        estimated_cost_cents=5.0,
        actual_cost_cents=0.0,
        fallback_used=False,
        timestamp=1700000000.0,
    )
    data = evidence.__dict__
    assert data['role'] == 'review'
    assert data['resolved_model'] == route.model
    assert data['policy_source'] == 'complexity'
    assert data['estimated_cost_cents'] == 5.0
    assert data['fallback_used'] is False


def test_unknown_role_falls_back_to_default() -> None:
    """Unknown/unrecognized task falls back to general category with default model."""
    route = route_model('xyzzy flobnar grue blorb', provider='gpt')
    assert route.category == 'general'
    assert route.model == 'gpt-4o-mini'
    assert route.complexity == 'medium'

    route_unk = route_model('review the code', provider='unknown_provider')
    assert route_unk.model is None
    assert route_unk.category == 'review'
    assert route_unk.provider == 'unknown_provider'

    route_unk2 = route_model('do something', provider='nonexistent')
    assert route_unk2.model is None
    assert route_unk2.category == 'general'
