# skills — Behavior Specification

## Purpose

Discovers, routes, and executes skill tool modules — reusable, composable agent behaviors packaged as Python or WASM files. Skills are isolated from the main agent and run in sandboxed environments.

## Behavior Contract

### Skill Routing (`skill_router.py`)
1. **Isolation planning** — `plan_skill_isolation(skill_path)` inspects the skill manifest to determine the sandbox type: `NATIVE`, `DOCKER`, or `WASM`.
2. **Risk-based routing** — skill risk level (from `consensus.RiskLevel`) influences whether Docker isolation is required.
3. **Fallback** — if Docker is unavailable and the plan says DOCKER, falls back to NATIVE with a warning.

### Skill Execution (`skill_executor.py`)
1. **Tool file discovery** — looks for `tool.py` (primary) or any `.py` in the skill directory.
2. **WASM execution** — if skill has `tool.wasm` and WASM runtime is available, runs in WASM sandbox.
3. **Docker execution** — injects payload as a JSON argument into the container; captures stdout as JSON.
4. **Native execution** — imports `tool.py` and calls `run(payload) -> Any`.
5. **Result wrapping** — always returns `SkillExecutionResult(success, sandbox_type, output, error)`.

### Skill Loading (`skill_loader.py`)
1. **Discovery** — scans `~/.teaagent/skills/` and project `.teaagent/skills/` for skill directories.
2. **Manifest parsing** — reads `skill.yaml` or `manifest.json` for metadata.
3. **RAG indexing** — indexes skill descriptions for semantic routing via `skill_rag.py`.

### Skill Router (`skill_router.py`)
1. **Semantic matching** — `SkillRouter.route(query)` returns ranked skills by description similarity.
2. **Exact match** — skill name matches take priority over semantic matches.

## Invariants

- Skill execution never modifies the main agent's workspace directly (isolation guarantee).
- `SkillExecutionResult.success=False` always has a non-empty `error` string.
- Native execution timeout is enforced (subprocess or thread limit).
