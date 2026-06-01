# Extension Activation Explainability
# 2026-06-01

**Fills:** Gap **F-ECO-007** — *"add unified extension activation explain output and
acceptance tests across hooks, skills, plugins, and MCP tools."* Daily users need to
know **why a hook fired, why a skill was loaded, which plugin registered a tool, and how
to disable one surface** without breaking the session.

**Grounding (current state, verified).** The reason data largely exists but is
**scattered and not surfaced**:
- **Hooks** — `teaagent/hooks.py` (495): `HookRegistry` + `HookEvent` enum
  (`SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PreCompact, Stop,
  SubagentStop, SessionEnd`); `run_pre_hooks`/`run_post_hooks`/… dispatch by event;
  `HookError` vetoes a tool call. **No record of which hook fired and why.**
- **Skills** — `teaagent/skill_loader.py` (643): `load_skills_with_report` →
  `SkillLoadReport` carrying `SkillLoadWarning` and `SkillLoadSkipped(reason)` (e.g.
  "provenance validation failed", "skill review failed"). `skill_index_to_prompt_section`
  injects skills into the prompt. **Load reasons exist; activation/selection reasons don't surface.**
- **Skill routing** — `teaagent/skill_router.py` (285): `RoutingDecision{sandbox_type,
  reason, fallback_available, warnings}` and `SkillIsolationPlan{isolation, reason, …}`
  — **already carry `reason` strings**, just not exposed to the operator.
- **Plugins** — `teaagent/plugin_system.py` (212): `PluginRegistry`, `discover_plugins`,
  `PluginManifest`, `register_command`/`register_agent`. **No "which plugin registered
  this tool/command" lookup is surfaced.**

So the gap is **aggregation + exposure**, not new instrumentation. Each subsystem
already knows its reason; nothing assembles them into one answer.

---

## The unified activation view

A single producer `build_activation_report(session) -> ActivationReport` and a surface
`teaagent explain activation [--tool X | --skill Y | --since-last-run]`:

```
ActivationReport
├── hooks_fired   [{event, hook_name, target_tool?, decision: ran|vetoed, reason}]
├── skills        [{name, source_dir, status: loaded|skipped, reason, isolation, sandbox}]
├── plugins       [{name, type, registered: [commands|agents|tools], manifest_path}]
├── mcp_tools     [{server, tool, trusted, allowed, expiry?}]    # from MCP trust spec
└── provenance    [{item, signed?, verified?, validation_errors[]}]
```

- **hooks_fired** is the only field needing a thin addition: `HookRegistry` records each
  dispatch (event, hook, outcome, reason) into a per-session ring buffer.
- **skills** reads directly from `SkillLoadReport` + `RoutingDecision.reason` +
  `SkillIsolationPlan.reason` (already present).
- **plugins** reads the `PluginRegistry` (which command/agent/tool came from which
  manifest — invert the existing registration map).
- **mcp_tools** reuses `MCPTrustPolicy` (see `mcp-trust-onboarding-journey` spec).

---

## "Why did X happen / how do I turn it off"

The view must answer four operator questions directly:

| Question | Answer source | Disable path |
|----------|---------------|--------------|
| Why did this hook fire? | `hooks_fired` (event + reason) | `--disable-hook <name>` for the session |
| Why was this skill loaded? | `skills` (matched + isolation reason) | `--disable-skill <name>` |
| Which plugin registered this tool/command? | `plugins` (inverted registry) | `--disable-plugin <name>` |
| Why is this MCP tool available? | `mcp_tools` (trust + scope) | revoke (MCP trust spec) |

**Disable is non-destructive and session-scoped** — it suppresses one surface for the
current session without uninstalling or breaking others (the explicit F-ECO-007 ask:
"disable one surface without breaking the session").

---

## Behavioral requirements

1. **Every active extension is attributable.** No tool/command/skill is active without
   an entry explaining its origin and reason.
2. **Vetoes are visible.** A `HookError` that blocked a tool call shows up in
   `hooks_fired` with `decision: vetoed` + reason — never a silent block.
3. **Provenance failures are explained, not hidden.** A skill skipped for provenance
   appears with `status: skipped` + the validation error (from `SkillLoadSkipped.reason`).
4. **Disable is reversible.** Re-enabling within the session restores the surface; the
   disable list is session-scoped state, not config mutation.

---

## Acceptance

- `test_activation_report_aggregates`: with a hook, a loaded skill, a plugin command,
  and an MCP tool present, the report lists all four with reasons.
- `test_hook_veto_explained`: a vetoing pre-hook appears as `vetoed` + reason.
- `test_skill_skip_reason_surfaced`: a provenance-failed skill shows `skipped` + the
  validation error.
- `test_plugin_origin_lookup`: `explain activation --tool <name>` returns the registering
  plugin + manifest path.
- `test_disable_surface_session_scoped`: `--disable-skill X` removes X from this
  session's prompt section without affecting other skills or persisting.

## Open decisions

- **DQ-EXT-1:** Should `hooks_fired` be a bounded ring buffer (last N) or full
  per-session log? Recommendation: bounded ring buffer (last N) + full in the audit log.
- **DQ-EXT-2:** Is `explain activation` a CLI verb, a TUI command, or both? Recommendation:
  both — it feeds the cockpit (CKP spec) as an "extensions" panel.

## Non-goals

- Not a permissions system — explainability *describes* activation; permission modes
  (PMR) and MCP trust *gate* it. Keep the concerns separate.
- Not a plugin marketplace/trust-scoring feature (that's `skill_review`/`mcp_trust`).

## Cross-references

- MCP tool rows: `mcp-trust-onboarding-journey-2026-06-01.md`.
- Cockpit "extensions" panel: `operator-cockpit-contract-2026-06-01.md`.
- Building blocks: `teaagent/hooks.py`, `teaagent/skill_loader.py`,
  `teaagent/skill_router.py`, `teaagent/plugin_system.py`.
</content>
