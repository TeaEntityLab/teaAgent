Classify the following task by type and complexity.

Task: {task_description}

Respond with JSON:
{{
    "task_type": "code_review|testing|documentation|refactoring|debugging|feature_implementation|general",
    "complexity": "simple|moderate|complex",
    "confidence": 0.0-1.0,
    "suggested_agent": "agent_name_or_null",
    "requires_multi_step": true|false,
    "estimated_steps": integer
}}
