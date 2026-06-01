# skills — Module Inspection

## Source Files

| File | Role |
|------|------|
| `teaagent/skill_executor.py` | `SkillExecutionResult`, `execute_skill`, Docker/WASM/native dispatch |
| `teaagent/skill_loader.py` | `SkillLoader` — discovery, manifest parsing |
| `teaagent/skill_router.py` | `SkillRouter`, `plan_skill_isolation`, `SandboxType`, `SkillIsolationPlan` |
| `teaagent/skill_candidates.py` | `SkillCandidate` — scored candidate wrapper |
| `teaagent/skill_candidate_artifacts.py` | Artifact extraction from skill outputs |
| `teaagent/skill_rag.py` | Semantic indexing and retrieval for skill routing |
| `teaagent/skill_eval.py` | Evaluation harness for skill quality |
| `teaagent/skill_eval_dataset.py` | Eval dataset management |
| `teaagent/skill_writer.py` | `SkillWriter` — generates new skill files |
| `teaagent/skill_review.py` | `SkillReviewer` — quality review before publishing |

## Key Exports

### `skill_executor.py`
- `SkillExecutionResult` — frozen dataclass: `success`, `sandbox_type`, `output`, `error`, `execution_backend`, `reason`
- `execute_skill(skill_path, payload, isolation_plan?) -> SkillExecutionResult`

### `skill_router.py`
- `SandboxType` — enum: `NATIVE`, `DOCKER`, `WASM`
- `SkillIsolationPlan` — dataclass: `sandbox_type`, `memory_limit_mb`, `timeout_seconds`, `network_access`
- `plan_skill_isolation(skill_path) -> SkillIsolationPlan`
- `SkillRouter` — `route(query) -> list[SkillCandidate]`, `register(skill)`

### `skill_loader.py`
- `SkillLoader` — `discover() -> list[SkillManifest]`, `load(name) -> SkillManifest`

## Dependencies

```
skill_executor.py
  ├── teaagent.consensus.RiskLevel
  ├── teaagent.docker_sandbox.DockerSandbox
  ├── teaagent.skill_router.SandboxType, SkillIsolationPlan, SkillRouter, plan_skill_isolation
  └── teaagent.wasm_runtime.WASMRuntime, is_wasm_available
```

## Entry Points

1. `runner/_core.py` — uses `SkillRouter.route(query)` to find and execute skills
2. `cli/_handlers/_skill.py` — `skill_run`, `skill_list`, `skill_install` commands
3. `tui/_commands.py` — `/skill` slash command dispatch
