from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ModelRoute:
    category: str
    provider: str
    model: Optional[str]
    reason: str
    complexity: str = 'medium'
    estimated_tokens: int = 0

    def to_dict(self) -> dict[str, Optional[str]]:
        return {
            'category': self.category,
            'provider': self.provider,
            'model': self.model,
            'reason': self.reason,
            'complexity': self.complexity,
            'estimated_tokens': self.estimated_tokens,
        }


CATEGORY_KEYWORDS = {
    'review': {'review', 'audit', 'risk', 'regression', 'security'},
    'test': {'test', 'tests', 'pytest', 'unittest', 'verify', 'failure', 'failing'},
    'code': {'add', 'build', 'change', 'fix', 'implement', 'refactor', 'update'},
    'docs': {'doc', 'docs', 'documentation', 'readme', 'markdown'},
    'search': {'inspect', 'list', 'read', 'search', 'summarize', 'explain'},
}

COMPLEXITY_INDICATORS = {
    'high': {
        'architecture', 'system', 'design', 'rewrite', 'migration',
        'integration', 'api', 'database', 'schema', 'performance',
        'optimization', 'scalability', 'security', 'authentication',
        'authorization', 'encryption', 'caching', 'queue', 'async',
        'concurrent', 'distributed', 'microservice', 'monolith',
        'refactor', 'restructure', 'reorganize', 'reimplement',
    },
    'medium': {
        'feature', 'function', 'method', 'class', 'module', 'component',
        'service', 'handler', 'controller', 'middleware', 'validator',
        'parser', 'formatter', 'converter', 'transformer', 'processor',
        'generator', 'builder', 'factory', 'adapter', 'decorator',
        'fix', 'bug', 'error', 'exception', 'validation', 'configuration',
    },
    'low': {
        'documentation', 'readme', 'comment', 'docstring', 'example',
        'test', 'unit', 'integration', 'e2e', 'mock', 'stub',
        'format', 'lint', 'style', 'naming', 'typo', 'spelling',
        'variable', 'constant', 'import', 'export', 'version',
    },
}

PROVIDER_CATEGORY_MODELS = {
    'claude': {
        'review': 'claude-3-5-sonnet-latest',
        'test': 'claude-3-5-sonnet-latest',
        'code': 'claude-3-5-sonnet-latest',
        'docs': 'claude-3-5-haiku-latest',
        'search': 'claude-3-5-haiku-latest',
        'general': 'claude-3-5-sonnet-latest',
    },
    'gpt': {
        'review': 'gpt-4o',
        'test': 'gpt-4o-mini',
        'code': 'gpt-4o',
        'docs': 'gpt-4o-mini',
        'search': 'gpt-4o-mini',
        'general': 'gpt-4o-mini',
    },
    'gemini': {
        'review': 'gemini-1.5-pro',
        'test': 'gemini-1.5-flash',
        'code': 'gemini-1.5-pro',
        'docs': 'gemini-1.5-flash',
        'search': 'gemini-1.5-flash',
        'general': 'gemini-1.5-flash',
    },
    'openrouter': {
        'review': 'anthropic/claude-3.5-sonnet',
        'test': 'openai/gpt-4o-mini',
        'code': 'anthropic/claude-3.5-sonnet',
        'docs': 'openai/gpt-4o-mini',
        'search': 'openai/gpt-4o-mini',
        'general': 'openai/gpt-4o-mini',
    },
    'opencodezen-go': {
        'review': 'opencodezen-go',
        'test': 'opencodezen-go',
        'code': 'opencodezen-go',
        'docs': 'opencodezen-go',
        'search': 'opencodezen-go',
        'general': 'opencodezen-go',
    },
    'opencodezen': {
        'review': 'opencodezen',
        'test': 'opencodezen',
        'code': 'opencodezen',
        'docs': 'opencodezen',
        'search': 'opencodezen',
        'general': 'opencodezen',
    },
}

# Complexity-based model overrides for cost optimization
COMPLEXITY_MODEL_OVERRIDES = {
    'claude': {
        'high': 'claude-3-5-sonnet-latest',
        'medium': 'claude-3-5-sonnet-latest',
        'low': 'claude-3-5-haiku-latest',
    },
    'gpt': {
        'high': 'gpt-4o',
        'medium': 'gpt-4o-mini',
        'low': 'gpt-4o-mini',
    },
    'gemini': {
        'high': 'gemini-1.5-pro',
        'medium': 'gemini-1.5-flash',
        'low': 'gemini-1.5-flash',
    },
    'openrouter': {
        'high': 'anthropic/claude-3.5-sonnet',
        'medium': 'openai/gpt-4o-mini',
        'low': 'openai/gpt-4o-mini',
    },
}


def classify_task(task: str) -> str:
    tokens = {token.strip('.,:;!?()[]{}"\'').lower() for token in task.split()}
    for category in ('review', 'test', 'docs', 'code', 'search'):
        if tokens & CATEGORY_KEYWORDS[category]:
            return category
    return 'general'


def analyze_complexity(task: str) -> str:
    """Analyze task complexity based on semantic indicators.

    Args:
        task: Task description.

    Returns:
        Complexity level: 'high', 'medium', or 'low'.
    """
    tokens = {token.strip('.,:;!?()[]{}"\'').lower() for token in task.split()}
    
    # Check for high complexity indicators
    if tokens & COMPLEXITY_INDICATORS['high']:
        return 'high'
    
    # Check for medium complexity indicators
    if tokens & COMPLEXITY_INDICATORS['medium']:
        return 'medium'
    
    # Check for low complexity indicators
    if tokens & COMPLEXITY_INDICATORS['low']:
        return 'low'
    
    # Default to medium for unknown tasks
    return 'medium'


def estimate_tokens(task: str, complexity: str) -> int:
    """Estimate token budget based on task length and complexity.

    Args:
        task: Task description.
        complexity: Complexity level.

    Returns:
        Estimated token count.
    """
    base_tokens = len(task.split()) * 4  # Rough estimate: 4 tokens per word
    
    complexity_multiplier = {
        'low': 1.0,
        'medium': 2.0,
        'high': 4.0,
    }
    
    estimated = int(base_tokens * complexity_multiplier.get(complexity, 2.0))
    
    # Add buffer for context and response
    return estimated + 2000


def route_model(task: str, *, provider: str, model: Optional[str] = None) -> ModelRoute:
    category = classify_task(task)
    complexity = analyze_complexity(task)
    estimated_tokens = estimate_tokens(task, complexity)
    
    if model:
        return ModelRoute(
            category=category,
            provider=provider,
            model=model,
            reason='explicit model override',
            complexity=complexity,
            estimated_tokens=estimated_tokens,
        )
    
    # Use complexity-based routing if available
    complexity_models = COMPLEXITY_MODEL_OVERRIDES.get(provider, {})
    if complexity_models and complexity in complexity_models:
        routed_model = complexity_models[complexity]
        return ModelRoute(
            category=category,
            provider=provider,
            model=routed_model,
            reason=f'{complexity} complexity {category} task routed for {provider}',
            complexity=complexity,
            estimated_tokens=estimated_tokens,
        )
    
    # Fall back to category-based routing
    provider_models = PROVIDER_CATEGORY_MODELS.get(provider, {})
    routed_model = provider_models.get(category) or provider_models.get('general')
    return ModelRoute(
        category=category,
        provider=provider,
        model=routed_model,
        reason=f'{category} task routed for {provider}',
        complexity=complexity,
        estimated_tokens=estimated_tokens,
    )
