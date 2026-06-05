"""Tests for model route receipt evidence extraction."""

import tempfile

from teaagent.run_evidence import (
    ModelRouteEvidence,
    RunEvidenceBundle,
    build_run_evidence_bundle,
    extract_routes,
)


def test_model_route_evidence_defaults():
    """Test ModelRouteEvidence default values."""
    route = ModelRouteEvidence(
        requested_provider='gpt',
        requested_model='',
        resolved_provider='gpt',
        resolved_model='gpt-4o',
        role='code',
        routing_reason='code task routed for gpt',
        policy_source='category',
    )
    assert route.requested_provider == 'gpt'
    assert route.requested_model == ''
    assert route.resolved_model == 'gpt-4o'
    assert route.role == 'code'
    assert route.estimated_cost_cents == 0.0
    assert route.actual_cost_cents == 0.0
    assert route.fallback_used is False
    assert route.timestamp is None


def test_extract_routes_single_event():
    """Test extracting a single model_route event."""
    events = [
        {
            'event_type': 'model_route',
            'payload': {
                'requested_provider': 'gpt',
                'requested_model': '',
                'resolved_provider': 'gpt',
                'resolved_model': 'gpt-4o',
                'role': 'code',
                'routing_reason': 'code task routed for gpt',
                'policy_source': 'category',
                'estimated_cost_cents': 0.0,
                'actual_cost_cents': 0.0,
                'fallback_used': False,
            },
            'created_at': 1700000000.0,
        }
    ]

    routes = extract_routes(events)
    assert len(routes) == 1
    assert routes[0].requested_provider == 'gpt'
    assert routes[0].resolved_model == 'gpt-4o'
    assert routes[0].role == 'code'
    assert routes[0].routing_reason == 'code task routed for gpt'
    assert routes[0].policy_source == 'category'
    assert routes[0].fallback_used is False
    assert routes[0].timestamp == 1700000000.0


def test_extract_routes_multiple_events():
    """Test extracting multiple model_route events."""
    events = [
        {
            'event_type': 'model_route',
            'payload': {
                'requested_provider': 'claude',
                'requested_model': '',
                'resolved_provider': 'claude',
                'resolved_model': 'claude-3-5-sonnet-latest',
                'role': 'review',
                'routing_reason': 'high complexity review task routed for claude',
                'policy_source': 'complexity',
                'estimated_cost_cents': 5.0,
                'actual_cost_cents': 0.0,
                'fallback_used': False,
            },
            'created_at': 1700000001.0,
        },
        {
            'event_type': 'model_route',
            'payload': {
                'requested_provider': 'gpt',
                'requested_model': 'gpt-4o',
                'resolved_provider': 'gpt',
                'resolved_model': 'gpt-4o',
                'role': 'code',
                'routing_reason': 'explicit model override',
                'policy_source': 'explicit_override',
                'estimated_cost_cents': 10.0,
                'actual_cost_cents': 0.0,
                'fallback_used': False,
            },
            'created_at': 1700000002.0,
        },
    ]

    routes = extract_routes(events)
    assert len(routes) == 2
    assert routes[0].role == 'review'
    assert routes[0].policy_source == 'complexity'
    assert routes[1].role == 'code'
    assert routes[1].policy_source == 'explicit_override'


def test_extract_routes_with_fallback():
    """Test extracting a route event where fallback was used."""
    events = [
        {
            'event_type': 'model_route',
            'payload': {
                'requested_provider': 'unknown_provider',
                'requested_model': '',
                'resolved_provider': 'unknown_provider',
                'resolved_model': '',
                'role': 'general',
                'routing_reason': 'general task routed for unknown_provider',
                'policy_source': 'category',
                'estimated_cost_cents': 0.0,
                'actual_cost_cents': 0.0,
                'fallback_used': True,
            },
            'created_at': 1700000003.0,
        }
    ]

    routes = extract_routes(events)
    assert len(routes) == 1
    assert routes[0].resolved_model == ''
    assert routes[0].fallback_used is True


def test_extract_routes_ignores_other_events():
    """Test that extract_routes ignores non-model_route events."""
    events = [
        {
            'event_type': 'run_started',
            'payload': {'task': 'test task'},
        },
        {
            'event_type': 'model_route',
            'payload': {
                'requested_provider': 'gpt',
                'requested_model': '',
                'resolved_provider': 'gpt',
                'resolved_model': 'gpt-4o-mini',
                'role': 'docs',
                'routing_reason': 'docs task routed for gpt',
                'policy_source': 'category',
                'estimated_cost_cents': 0.0,
                'actual_cost_cents': 0.0,
                'fallback_used': False,
            },
        },
        {
            'event_type': 'tool_use',
            'payload': {'tool_name': 'exec'},
        },
    ]

    routes = extract_routes(events)
    assert len(routes) == 1
    assert routes[0].resolved_model == 'gpt-4o-mini'


def test_extract_routes_missing_payload_fields():
    """Test that missing payload fields get default values."""
    events = [
        {
            'event_type': 'model_route',
            'payload': {
                'requested_provider': 'gpt',
            },
        }
    ]

    routes = extract_routes(events)
    assert len(routes) == 1
    assert routes[0].requested_provider == 'gpt'
    assert routes[0].requested_model == ''
    assert routes[0].resolved_model == ''
    assert routes[0].role == ''
    assert routes[0].policy_source == ''
    assert routes[0].estimated_cost_cents == 0.0
    assert routes[0].fallback_used is False


def test_extract_routes_non_dict_payload():
    """Test that non-dict payloads are skipped, None becomes empty dict."""
    events = [
        {
            'event_type': 'model_route',
            'payload': None,
        },
        {
            'event_type': 'model_route',
            'payload': 'not_a_dict',
        },
        {
            'event_type': 'model_route',
            'payload': {
                'requested_provider': 'claude',
                'requested_model': '',
                'resolved_provider': 'claude',
                'resolved_model': 'claude-3-5-sonnet-latest',
                'role': 'code',
                'routing_reason': 'medium complexity code task routed for claude',
                'policy_source': 'complexity',
                'estimated_cost_cents': 0.0,
                'actual_cost_cents': 0.0,
                'fallback_used': False,
            },
        },
    ]

    routes = extract_routes(events)
    assert len(routes) == 2
    assert routes[0].requested_provider == ''
    assert routes[1].resolved_model == 'claude-3-5-sonnet-latest'


def test_run_evidence_bundle_routes_serialization():
    """Test that routes appear in RunEvidenceBundle.to_dict()."""
    route = ModelRouteEvidence(
        requested_provider='gpt',
        requested_model='',
        resolved_provider='gpt',
        resolved_model='gpt-4o',
        role='code',
        routing_reason='code task routed for gpt',
        policy_source='category',
        estimated_cost_cents=5.0,
        actual_cost_cents=0.0,
        fallback_used=False,
        timestamp=1700000000.0,
    )
    bundle = RunEvidenceBundle(
        run_id='test-run-routes',
        routes=[route],
    )
    data = bundle.to_dict()
    assert data['run_id'] == 'test-run-routes'
    assert len(data['routes']) == 1
    assert data['routes'][0]['requested_provider'] == 'gpt'
    assert data['routes'][0]['resolved_model'] == 'gpt-4o'
    assert data['routes'][0]['role'] == 'code'
    assert data['routes'][0]['policy_source'] == 'category'
    assert data['routes'][0]['estimated_cost_cents'] == 5.0
    assert data['routes'][0]['fallback_used'] is False


def test_build_run_evidence_bundle_includes_routes():
    """Test that build_run_evidence_bundle extracts routes from stored events."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bundle = build_run_evidence_bundle(tmpdir, 'nonexistent-run')
        assert bundle.run_id == 'nonexistent-run'
        assert bundle.routes == []
