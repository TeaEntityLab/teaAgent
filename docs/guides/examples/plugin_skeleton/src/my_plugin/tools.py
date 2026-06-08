"""Plugin entry-point for teaagent.tools.

TeaAgent discovers this via the entry-point group 'teaagent.tools'
defined in pyproject.toml. The register() function is called once
at startup with the shared ToolRegistry.
"""

from __future__ import annotations

from teaagent.types import ToolAnnotations, ToolRegistry


def register(registry: ToolRegistry) -> None:
    """Register all tools provided by this plugin."""
    registry.register(
        name='my_plugin_greet',
        description=(
            'Return a personalised greeting. '
            'Use when the user wants to be greeted by name.'
        ),
        input_schema={
            'type': 'object',
            'properties': {
                'name': {
                    'type': 'string',
                    'description': 'Name of the person to greet.',
                    'minLength': 1,
                    'maxLength': 100,
                },
                'formal': {
                    'type': 'boolean',
                    'description': 'If true, use formal language.',
                    'default': False,
                },
            },
            'required': ['name'],
        },
        output_schema={
            'type': 'object',
            'properties': {
                'greeting': {'type': 'string'},
            },
            'required': ['greeting'],
        },
        annotations=ToolAnnotations(read_only=True, idempotent=True),
        handler=_greet,
    )


def _greet(args: dict) -> dict:
    name = args['name'].strip()
    if not name:
        raise ValueError('name must not be blank')
    formal = args.get('formal', False)
    if formal:
        return {'greeting': f'Good day, {name}.'}
    return {'greeting': f'Hello, {name}!'}
