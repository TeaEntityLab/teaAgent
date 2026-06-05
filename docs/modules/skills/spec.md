# skills — Behavior Specification

## Purpose

Discovers, routes, evaluates, installs, and in some cases executes reusable
agent capabilities. TeaAgent currently has two related skill surfaces:

1. **Agent Skills prompt packages**: directories containing `SKILL.md` and
   optional references/scripts/assets. These are discovered by `skill_loader.py`
   and injected into agent context.
2. **Executable skill tools**: Python/WASM/Docker callable modules handled by
   `skill_executor.py` and `skill_router.py`.

The daily-driver skill path should prefer the governed Agent Skills candidate
workflow before a skill becomes active in a project.

Strategic direction and current gaps are recorded in:

- `docs/strategy/agent-ecosystem-core-values-2026-06-05.md`
- `docs/analysis/rss-failure-case-study-2026-06-05.md`
- `docs/architecture/dynamic-skill-lifecycle-and-result-flow-2026-06-05.md`
- `docs/plans/dynamic-skill-and-long-result-work-items-2026-06-05.md`

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
1. **Discovery** — scans project and user skill directories in priority order (first match wins per skill name):
   - Project scope: `.config/agent/skills/`, `.claude/skills/`, `.opencode/skill/`, `.opencode/skills/`
   - User scope: `~/.config/agent/skills/`, `~/.claude/skills/`, `~/.config/opencode/skills/`
2. **Review gate** — loads only `SKILL.md` files that pass `review_skill()`.
3. **Candidate artifact gate** — installed candidate bundles with policy,
   provenance, cost, or contract artifacts must pass artifact validation.
4. **Prompt mode** — eager mode loads full skill text; index-only mode exposes
   metadata without injecting full instructions.
5. **Explainability** — `explain_skill_activation()` reports loaded skills,
   shadowed paths, searched directories, token estimates, governance status, and
   expected project write targets.

### Skill Candidate Governance (`skill_candidates.py`)
1. **Proposal** — creates a quarantined candidate under `.teaagent/skill-candidates/`.
2. **Artifact bundle** — requires `SKILL.md`, `REFERENCE.md`,
   `tool_call_contract.json`, `cost_profile.json`, `interaction_policy.json`,
   and `provenance.json`.
3. **Offline eval** — validates artifacts, size, review findings, provenance,
   reference content, and candidate-specific `eval_dataset.json` checks.
4. **Review** — a candidate must pass review before installation.
5. **Install** — project installs write to `.config/agent/skills/<name>`;
   personal installs require explicit personal-install attestation.
6. **Provenance** — installed candidates record install scope and candidate
   origin so CLI/TUI can distinguish reviewed skills from direct writes.

### Target Dynamic Skill Lifecycle
1. **Candidate proposal** — repeated successful procedures become quarantined
   candidate bundles, not direct active-skill writes.
2. **Artifact and eval gates** — structure, provenance, cost, interaction
   policy, reference content, and deterministic task behavior are checked before
   install.
3. **Reviewed install** — reviewed project installs write to
   `.config/agent/skills/<name>` with provenance.
4. **Activation evidence** — a later run must record skill selection,
   activation, resource reads, and output verification separately from load.
5. **Long-result preservation** — source-heavy skill outputs use preview plus
   artifact pointer, hash, and cursor when they exceed model-visible limits.

### Skill Router (`skill_router.py`)
1. **Semantic matching** — `SkillRouter.route(query)` returns ranked skills by description similarity.
2. **Exact match** — skill name matches take priority over semantic matches.

## Invariants

- Skill execution never modifies the main agent's workspace directly (isolation guarantee).
- `SkillExecutionResult.success=False` always has a non-empty `error` string.
- Native execution timeout is enforced (subprocess or thread limit).
- A reviewed candidate install must carry provenance next to `SKILL.md`.
- A loaded active skill without candidate provenance should be treated as an
  unmanaged/direct-write skill for explainability and review purposes.
- "Skill loaded" does not imply "skill used"; runtime activation and output
  verification require separate audit evidence.
- Long RSS/WebSearch/skill outputs must remain source-backed through artifact
  pointers and verification, not preview-only summarization.
