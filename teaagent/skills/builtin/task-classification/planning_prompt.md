Generate a structured workflow plan for the following task.

Task: {task_description}
Task Type: {task_type}
Complexity: {complexity}
Estimated Steps: {estimated_steps}

Available Agents: {available_agents}

Respond with JSON:
{{
    "steps": [
        {{
            "step_id": 1,
            "description": "Step description",
            "agent_name": "agent_name",
            "tools": ["tool1", "tool2"],
            "dependencies": []
        }}
    ],
    "estimated_duration_seconds": integer
}}
