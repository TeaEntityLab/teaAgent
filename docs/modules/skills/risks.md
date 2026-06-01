# skills — Risk Vectors & Known Issues

## R1: Native skill execution runs in the same process
**File**: `skill_executor.py`
**Risk**: `NATIVE` sandbox type imports and calls `tool.py` in the same Python process. A buggy skill can crash the agent, corrupt global state, or access any file the agent can access.
**Failure mode**: Agent crash, privilege escalation, unintended file writes.
**Mitigation**: Use `DOCKER` or `WASM` for untrusted skills.

## R2: Docker build requires network access
**File**: `skill_executor.py` — `_build_docker_runner_code`
**Risk**: Skills that require additional pip packages need Docker to pull from the internet. Offline or air-gapped environments fail.
**Failure mode**: `DockerSandboxError`, skill not executable.

## R3: WASM runtime availability is runtime-detected
**File**: `skill_executor.py:18` — `is_wasm_available()`
**Risk**: If the WASM runtime is not installed, skill isolation silently falls back to Docker or Native without the caller knowing the isolation guarantee changed.
**Failure mode**: Expected WASM isolation not enforced.

## R4: Skill manifest validation is weak
**File**: `skill_loader.py`
**Risk**: `skill.yaml` is parsed but schema validation may be loose. A malformed manifest could register a skill with incorrect metadata.
**Failure mode**: Wrong skill invoked, wrong isolation plan applied.

## R5: Memory limit parsing fails silently
**File**: `skill_executor.py:60-71` — `_parse_memory_mb`
**Risk**: If the memory limit string is malformed (e.g., `"512 mb"` with a space), `_MEMORY_PATTERN` doesn't match and returns `None`. Docker then uses no memory limit.
**Failure mode**: OOM-killed container or host memory exhaustion.

## R6: skill_rag.py semantic search may return wrong skill
**File**: `skill_rag.py`
**Risk**: If skill descriptions are similar, semantic routing may invoke the wrong skill.
**Failure mode**: Unexpected behavior; hard to debug since skill name is not shown by default.
