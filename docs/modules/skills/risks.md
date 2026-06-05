# skills — Risk Vectors & Known Issues

### SKL-R-001: Native skill execution runs in the same process
**File**: `skill_executor.py`
**Risk**: `NATIVE` sandbox type imports and calls `tool.py` in the same Python process. A buggy skill can crash the agent, corrupt global state, or access any file the agent can access.
**Failure mode**: Agent crash, privilege escalation, unintended file writes.
**Mitigation**: Use `DOCKER` or `WASM` for untrusted skills.

### SKL-R-002: Docker build requires network access
**File**: `skill_executor.py` — `_build_docker_runner_code`
**Risk**: Skills that require additional pip packages need Docker to pull from the internet. Offline or air-gapped environments fail.
**Failure mode**: `DockerSandboxError`, skill not executable.

### SKL-R-003: WASM runtime availability is runtime-detected
**File**: `skill_executor.py:18` — `is_wasm_available()`
**Risk**: If the WASM runtime is not installed, skill isolation silently falls back to Docker or Native without the caller knowing the isolation guarantee changed.
**Failure mode**: Expected WASM isolation not enforced.

### SKL-R-004: Skill manifest validation is weak
**File**: `skill_loader.py`
**Risk**: `skill.yaml` is parsed but schema validation may be loose. A malformed manifest could register a skill with incorrect metadata.
**Failure mode**: Wrong skill invoked, wrong isolation plan applied.

### SKL-R-005: Memory limit parsing fails silently
**File**: `skill_executor.py:60-71` — `_parse_memory_mb`
**Risk**: If the memory limit string is malformed (e.g., `"512 mb"` with a space), `_MEMORY_PATTERN` doesn't match and returns `None`. Docker then uses no memory limit.
**Failure mode**: OOM-killed container or host memory exhaustion.

### SKL-R-006: skill_rag.py semantic search may return wrong skill
**File**: `skill_rag.py`
**Risk**: If skill descriptions are similar, semantic routing may invoke the wrong skill.
**Failure mode**: Unexpected behavior; hard to debug since skill name is not shown by default.

### SKL-R-007: Direct active-skill writes bypass candidate governance
**File**: `skill_writer.py`, `workspace_tools/_files.py`, `skill_loader.py`
**Risk**: An agent can write a `SKILL.md` directly into an active discovery
directory such as `.opencode/skill/` or `.config/agent/skills/`. The loader will
discover it, but no candidate artifacts, offline eval, review, or install
provenance prove that it is safe or useful.
**Failure mode**: The UI reports a skill as available even though it is an
unreviewed direct write. Users may mistake compatibility discovery for a
governed TeaAgent skill lifecycle.
**Mitigation**: Treat missing candidate provenance as `direct_write` in
explainability output; block or quarantine direct writes to active skill
directories by default; allow reviewed installs through `skill candidate
install`.

### SKL-R-008: Skill loaded does not prove skill used
**File**: `chat_agent.py`, `skill_loader.py`
**Risk**: Agent Skills can be injected into the prompt but ignored by the model,
especially when the model fails to read supporting resources or emits invalid
tool-decision JSON.
**Failure mode**: A run claims a skill-based task succeeded, but the skill only
appeared in context and did not drive the output.
**Mitigation**: Add explicit `skill_activated`, `skill_resource_read`, and
`skill_output_verified` audit events; add user-forced activation; compare
with-skill and without-skill behavior in candidate evals.

### SKL-R-009: Long skill or web results lose required evidence
**File**: `workspace_tools/_files.py`, `chat_agent.py`, future web/RSS tools
**Risk**: Long RSS/WebSearch/skill results can be truncated or summarized before
the model sees the evidence required for a faithful answer.
**Failure mode**: The model writes a plausible summary from a partial preview,
or creates a placeholder helper script and claims completion.
**Mitigation**: Standardize a long-result envelope with preview, truncation
metadata, full artifact path, content hash, cursor, and compaction-preserved
source IDs. Acceptance tests must verify final output against fixture sources.
