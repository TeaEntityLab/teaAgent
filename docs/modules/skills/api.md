# skills — Public API Reference

## `SandboxType` (Enum)
**Location**: `skill_router.py`

```python
class SandboxType(str, Enum):
    NATIVE = 'native'    # same process, no isolation
    DOCKER = 'docker'    # Docker container
    WASM   = 'wasm'      # WASM runtime
```

---

## `SkillIsolationPlan` (dataclass)
**Location**: `skill_router.py`

```python
@dataclass
class SkillIsolationPlan:
    sandbox_type: SandboxType
    memory_limit_mb: Optional[float] = None
    timeout_seconds: int = 30
    network_access: bool = False
```

---

## `SkillExecutionResult` (frozen dataclass)
**Location**: `skill_executor.py:29`

```python
@dataclass(frozen=True)
class SkillExecutionResult:
    success: bool
    sandbox_type: SandboxType
    output: Any = None         # deserialized result from skill
    error: str = ''            # non-empty if success=False
    execution_backend: str = '' # e.g. 'docker:python:3.12-slim'
    reason: str = ''           # why this sandbox was chosen
```

---

## `plan_skill_isolation`
**Location**: `skill_router.py`

```python
def plan_skill_isolation(skill_path: Path) -> SkillIsolationPlan
```
Reads `skill.yaml` manifest, checks risk level, returns isolation plan. Falls back to `NATIVE` if Docker/WASM unavailable.

---

## `execute_skill`
**Location**: `skill_executor.py`

```python
def execute_skill(
    skill_path: Path,
    payload: dict[str, Any],
    isolation_plan: Optional[SkillIsolationPlan] = None,
) -> SkillExecutionResult
```
**Pre**: `skill_path` must contain a `tool.py` or `tool.wasm`.
**Post**: Returns `SkillExecutionResult`. Never raises (exceptions are captured into `error` field).

**Dispatch priority**:
1. WASM → `WASMRuntime.run(wasm_file, payload)`
2. DOCKER → `DockerSandbox.run(code, payload)`
3. NATIVE → `importlib.import_module(tool).run(payload)`

---

## `SkillRouter`
**Location**: `skill_router.py`

```python
class SkillRouter:
    def register(self, skill: SkillManifest) -> None
    def route(self, query: str, top_k: int = 3) -> list[SkillCandidate]
    def get(self, name: str) -> Optional[SkillManifest]
    def list_skills(self) -> list[SkillManifest]
```

---

## Skill Directory Layout

```
~/.teaagent/skills/<skill-name>/
  skill.yaml          # manifest (name, description, risk_level, sandbox)
  tool.py             # main entrypoint: def run(payload: dict) -> Any
  tool.wasm           # optional WASM binary
  requirements.txt    # optional: pip packages for Docker
```

## `skill.yaml` Schema

```yaml
name: my-skill
description: "What this skill does (used for semantic routing)"
version: "1.0.0"
risk_level: low      # low | medium | high
sandbox: native      # native | docker | wasm
timeout_seconds: 30
memory_limit: "512mb"
network_access: false
```
