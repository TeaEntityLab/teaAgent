# Backlog Priority

Prioritized by impact order: security and production risk → core platform capabilities → developer experience and ecosystem.

Last updated: 2026-05-22 (daily-use ergonomics revised)

---

## Implemented

Items below were deferred at baseline and have since been implemented in-repo.

| Item | Sprint | Files |
|------|--------|-------|
| Key ring CLI support (`--oauth-key-ring-file`, `--oauth-active-kid`, fail-closed validation) | P0-r1 | `cli/_mcp_parsers.py`, `cli/_handlers/_mcp.py` |
| External state checkpoint store (`InMemoryCheckpointStore`, `SQLiteCheckpointStore`, `--checkpoint-store` CLI) | P0-r1 | `teaagent/checkpoint.py`, `runner/_core.py`, `chat_agent.py` |
| DPoP replay TTL configurable (`dpop_replay_ttl` + `--oauth-dpop-replay-ttl` CLI) | P0-r1 | `oauth21/_server.py`, `cli/_mcp_parsers.py` |
| OAuth key rotation overlap window (`OAuthKeyRing.rotate`, `key_for_validation`, `--oauth-rotation-window`) | P0-r2 | `oauth21/_store.py`, `oauth21/_server.py`, `oauth21/_resource.py` |
| Code Mode sandbox profile matrix (`SandboxProfile` enum, `default_sandbox`, `validate_runtime_support`) | P0-r2 | `code_mode/_types.py`, `code_mode/__init__.py` |
| LLM-as-Judge scoring (`JudgeScore`, `run_eval_with_judge`, `make_llm_judge_fn`) | P1-r1 | `teaagent/eval.py` |
| AgentCard + InMemoryAgentRegistry + `agent card` CLI | P1-r1 | `teaagent/agentcard.py`, `cli/_agent_parsers.py` |
| Managed runtime interface (`ManagedRuntimeAdapter` Protocol, `ManagedAgentRunner`, provider stubs) | P1-r2 | `teaagent/managed_runtime.py` |
| LATENCY conformance tier (p50/p95 sampling, threshold check, `latency_samples`/`latency_threshold_ms` params) | P1-r2 | `llm_conformance/_types.py`, `llm_conformance/_runner.py` |
| SQLiteAgentRegistry + A2ADispatcher (persistent A2A registry, in-process routing) | P1-r2 | `teaagent/agentcard.py` |
| Extended conformance tiers: `STREAMING`, `STRUCTURED_OUTPUT` | P2-r1 | `llm_conformance/_types.py`, `llm_conformance/_runner.py` |
| OpenAPI 3.1 schema auto-generation from `ToolRegistry` + `workspace openapi` CLI | P2-r1 | `teaagent/openapi.py`, `cli/_misc_parsers.py` |
| Web audit viewer (`AuditViewerServer`, HTML/JSON routes, `audit serve` CLI) | P2-r2 | `teaagent/audit_viewer.py`, `cli/_handlers/_audit.py` |
| Schema migration framework (`SchemaMigration`, `SQLiteMigrationStore`, `MigrationRunner`, `doctor migration` CLI) | P2-r2 | `teaagent/schema_migration.py`, `cli/_handlers/_doctor.py` |
| Code Mode kernel sandbox hardening (`seccomp_profile`, `apparmor_profile`, `selinux_label`, `oci_runtime` on `ContainerCodeModeBackend`; `IsolateCodeModeBackend` gVisor wrapper; `sandbox_profile_selected`/`sandbox_violation` audit events; `profile`+`audit_logger` params on `execute_code_mode`) | P0-r3 | `code_mode/_types.py`, `code_mode/_container.py`, `code_mode/_isolate.py`, `code_mode/__init__.py` |
| Cross-host OAuthStore persistence (`PostgreSQLOAuthStore` with `DELETE…RETURNING` atomic consume; `RedisOAuthStore` with Lua-script atomic consume, NX nonce/code saves, configurable key prefix) | P0-r3 | `oauth21/_pg_store.py`, `oauth21/_redis_store.py`, `oauth21/__init__.py` |
| Managed runtime audit events (`managed_task_started/completed/failed` on `ManagedAgentRunner.run`; `audit_logger`+`run_id` params); tool-context forwarding for Anthropic and OpenAI runtimes | P1-r3 | `teaagent/managed_runtime.py` |
| Extended conformance tiers: `TOOL_CALLING` (invokes `get_current_time` tool, checks `tool_calls`); `SAFETY` (API-level block + text refusal taxonomy); `LLMToolDefinition`, `LLMToolCall`, `SafetyCategory`, `LLMSafetyBlock` types; tool wiring in all three adapters | P1-r3 | `llm/_types.py`, `llm/_adapters.py`, `llm/__init__.py`, `llm_conformance/_types.py`, `llm_conformance/_runner.py` |
| A2A HTTP discovery + wire protocol: `A2ADiscoveryServer` (serves `/.well-known/agent.json`, handles POST `/a2a/task`); `A2AClient` (`fetch_card`, `delegate`); `FederatedAgentRegistry` (TTL-cached pulls from remote endpoints) | P1-r3 | `teaagent/agentcard.py` |
| GraphQLite production deployment (`GraphQLitePersistentStore`, `GraphQLiteProductionConfig`, index strategy, migration integration, `graphqlite migrate` CLI, production deployment guide) | P2-r3 | `teaagent/graphqlite_production.py`, `docs/graphqlite-production.md`, `cli/_handlers/_misc.py`, `cli/_misc_parsers.py` |
| IDE integration - VS Code extension (command palette, task provider, terminal profile, TeaAgent output channel) | P2-r3 | `vscode/package.json`, `vscode/src/extension.ts` |
| Hosted doc site infrastructure (`pdoc` dependency, `scripts/build_docs.py` build script, class-level docstrings on core modules) | P2-r3 | `pyproject.toml`, `scripts/build_docs.py`, `teaagent/tools.py`, `teaagent/runner/_core.py`, `teaagent/budget.py`, `teaagent/policy.py`, `teaagent/memory.py` |
| ANP bidirectional adapter governed federation (`ANPGovernedService`, audit correlation, approval/budget invariants) | P1 | `teaagent/anp_adapter.py`, `tests/acceptance/test_anp_adapter_flow.py`, `docs/adr/0007-anp-adapter-boundary.md` |

---

## Open — High (P0)

_No open P0 items._

---

## Open — Daily-use ergonomics (2026-05-22)

Surveyed agents (deepwiki, 2026-05-22):
- **Batch 1**: Aider, OpenCode, Codex, Cline, Continue, OpenHands
- **Batch 2**: Goose, Crush, Gemini CLI, Roo Code, Plandex, Sourcegraph Amp/Cody

Cross-cutting patterns from both surveys (present in 3+ agents):
- **One-command start** — every tool has an obvious single entry (`aider`, `opencode`, `codex`, `goose session`, `crush`, `gemini`, `plandex`).
- **Safe-by-default** — approvals/sandboxing/checkpoints are standard; explicit opt-ins for speed (`--yolo`, `auto-approve`).
- **Resume is first-class** — history, continue, resume, fork, reconnectable streams show up in **every** surveyed agent.
- **Explicit approval ladder** — per-turn, per-session, smart-approve; not just a binary safe/unsafe.
- **Multi-surface UX** — CLI + TUI + IDE + MCP + background/remote is the common stack.
- **Recipe workflows beat generic chat** — refactor/test/docs/review/security are packaged as commands/modes, not ad-hoc prompts.
- **Context injection surfaces** — `@` file refs, editor selections, git/diagnostic/terminal state pulled in naturally.

Competitive parity is shipped; the next bar is **time-to-daily-habit** plus
**session continuity**. The items below close that ergonomics gap without
expanding the harness boundary.

### P1 — first daily session in under 60 seconds

| Item | Why it matters | Likely files |
|------|----------------|--------------|
| `teaagent init --root .` one-shot project bootstrap | Today users run three separate `doctor` wizards (providers, project, mcp). A single chained init writing `.teaagent/env` + `.teaagent/config.toml` + stub `AGENTS.md` collapses minutes of setup into one command — matches `aider --install` / `opencode init` ergonomics. | `cli/_handlers/_doctor.py` (new `init` orchestrator), `teaagent/config_loader.py` |
| Project defaults in `.teaagent/config.toml` | Persist `provider`, `context_profile`, `permission_mode`, `heartbeat`, `root`, `daily_cost_cap_cents`. Reduces `agent run gpt "..." --permission-mode workspace-write --context-profile balanced --root .` to `run "..."`. | `teaagent/config_loader.py`, `cli/_agent_parsers.py` |
| Top-level shortcuts: `teaagent daily`, `teaagent run`, `teaagent ask`, `teaagent resume` | Aliases for `agent daily/run/ask/resume` that read provider from config. README "Daily Use in 5 Commands" already shows the muscle memory we want; CLI should match. | `cli/__init__.py`, `cli/_agent_parsers.py` |
| Shell completion (`teaagent completion zsh\|bash\|fish`) | Autocomplete for commands, providers, permission modes, run-ids. Single biggest ergonomics win for terminal-first agents (Codex, opencode, crush, Goose all ship completion). | `cli/_handlers/_misc.py` (new `completion` handler) |
| `--dry-run` on `agent run` / `agent daily` | Print assembled prompt + estimated cost + tool list without invoking the model. Builds trust before spending tokens; consistent with `token_budget` JSON contract already shipped. | `cli/_handlers/_agent.py`, `teaagent/daily.py` |

### P1 — persistent daily habit

| Item | Why it matters | Likely files |
|------|----------------|--------------|
| Persistent "today" digest at `.teaagent/daily/YYYY-MM-DD.md` | Daily brief is currently a one-shot stdout dump. Writing a markdown file lets users re-read it, share it, diff yesterday vs today, and pipe to mail/Slack. | `teaagent/daily.py`, new `teaagent/daily_journal.py` |
| `teaagent yesterday` / `teaagent recall <N>` | Surface yesterday's runs/decisions/approvals from `RunStore` for stand-ups. Builds on existing run history; no new persistence. | `cli/_handlers/_agent.py`, `teaagent/run_store.py` |
| `teaagent status --short` for shell prompt integration | One-line traffic-light: token-pressure colour + pending-approval count + active run id. Lets users see harness state without leaving their prompt. | `cli/_handlers/_agent.py`, `teaagent/daily.py` |
| Desktop / system notifications on approval-needed and run-done | macOS `osascript`, Linux `notify-send`, Windows toast. Critical when running `prompt` mode in background; users currently must tail the audit log. | `teaagent/heartbeat.py`, new `teaagent/notify.py` |
| Daily cost cap (`daily_cost_cap_cents` config + `--daily-cap` flag) | Budget reporter already estimates per-run cost. Add a per-day rollup that warns at 80% and blocks at 100% unless `--override-cap`. | `teaagent/budget.py`, `teaagent/config_loader.py` |

### P1 — session continuity (upgraded from P2, all surveyed agents agree)

| Item | Why it matters | Likely files |
|------|----------------|--------------|
| Session browser: `teaagent session list/show/resume` | Every surveyed agent ships first-class session resume/fork. TeaAgent run store already persists runs; add a session layer that lists recent sessions, shows context/status, and resumes by ID with restored context + pending approvals. Aider's auto-commit, Codex's resume/fork threads, Crush's background streams, and Plandex's `ps/connect` all converge on this. | New `cli/_handlers/_sessions.py`, `teaagent/run_store.py` |
| Background/attach: `agent run --background` + `agent attach <id>` | Long-running `prompt` runs need to survive a closed terminal. Detached run returns an ID; `attach` streams live events; run continues after client exits. Goose (`schedule add`), Crush (`ps → connect`), Plandex (`--bg → connect`), and OpenHands (V1 sessions) all support this as a daily-use feature — not a power-user option. | `runner/_core.py`, `teaagent/heartbeat.py`, new `teaagent/session_stream.py` |
| Approval presets + audit trail | Per-tool + per-mode allow/deny with session-persistent grants ("allow once / session / always deny"). Clear audit trail showing action/path/diff for every approval decision. Codex's approval policies, Cline's checkpoints, and Goose's `smart_approve` all converge on persistent approval state as a daily-safety baseline. | `teaagent/policy.py`, `teaagent/audit.py`, `cli/_handlers/_agent.py` |

### P1 — recipe-first workflow

| Item | Why it matters | Likely files |
|------|----------------|--------------|
| Recipe registry + `teaagent recipes list\|run <name>` | The USAGE recipe table is documentation only. Promote each row (review-diff, fix-failing-test, summarize-repo, map-architecture, safe-cleanup) to a first-class recipe = SKILL with prompt template + permission mode + context profile. Users invoke `teaagent recipes run review-diff` without remembering 4 flags. Surveyed agents (Roo Code modes, Cody `/explain`, Cline's plan/act split) all package workflows as first-class commands. | New `teaagent/recipes/`, `skills/recipes/*.md` |
| Git hook recipes (`scripts/hooks/pre-commit`, `prepare-commit-msg`, `pre-push`) | Drop-in hooks that call `agent run --permission-mode read-only` to review staged diffs and optionally inject a commit-message draft. Mirrors what Aider users hand-roll today. | `scripts/hooks/`, `docs/USAGE.md` |
| `teaagent ci review` headless PR review | Reads `GITHUB_BASE_REF`/`GITHUB_HEAD_REF` (or `git diff origin/main...HEAD`), runs read-only review, prints markdown comment to stdout. Pairs with a one-file GitHub Action recipe. | `cli/_handlers/_agent.py`, `examples/github-action.yml` |
| Editor context injection (`@`-mentions, selection, git diff, diagnostics) | Roo Code's context menus, Gemini CLI's `@file`, and Cody's `/explain` all surface editor state directly into prompts. ACP already transports IDE state; expose a TUI `@` system + CLI flag for injecting file/selection/diff/diagnostic/terminal-output blocks into the prompt preamble. | `teaagent/context_pack.py`, `cli/_agent_parsers.py`, `teaagent/acp_adapter.py` |

### P2 — passive / always-on surfaces

| Item | Why it matters | Likely files |
|------|----------------|--------------|
| `teaagent watch --interval 6h` cron-friendly daily brief | Headless variant of `agent daily` that emits JSON/markdown on a schedule. Pairs with cron/launchd/systemd timers for morning email. | `cli/_handlers/_agent.py`, `teaagent/daily.py` |
| Auto-compaction summaries for long resumed runs | Long runs should automatically summarize old turns when resumed. Manual compact exists; automated summaries on resume + resumption-context trimming match Gemini CLI and Codex's rollout-replay compaction patterns. | `teaagent/context.py`, `teaagent/daily.py` |
| Workspace guidance file convention | Standardized project-instructions file (`.teaagent/guide.md` or `AGENTS.md`) auto-loaded and honored by preflight/run. Gemini CLI ships `GEMINI.md`, OpenHands has `.openhands_instructions`. TeaAgent reads `AGENTS.md` in system prompt but should document the convention and support per-subdir overrides. | `teaagent/config_loader.py`, `docs/USAGE.md` |
| First-launch greeting / version-change "what's new" | One-time stdout banner per version listing new providers, new recipes, deprecations. Cuts docs hunting for users who upgrade weekly. | `cli/__init__.py`, new `teaagent/whats_new.py` |
| Raycast extension / macOS Shortcuts recipes | One-keystroke launch of daily/preflight/run from anywhere. Bigger payoff per LoC than a new IDE plugin. | `examples/raycast/`, `examples/shortcuts/` |
| JetBrains + Zed + Neovim recipes over existing ACP / MCP HTTP | ACP and MCP HTTP transports already exist; ship a one-page recipe per IDE plus a minimal Neovim plugin in `examples/`. Most users live in one of these three editors. | `examples/jetbrains/`, `examples/zed/`, `examples/nvim/` |
| Chat-surface bridge (Slack / Discord / Telegram) — opt-in skill | Daily brief + `prompt`-mode runs via chat. Ship as a skill that wraps `mcp serve --http` rather than baking into the core. | `skills/chat-bridge/`, `docs/USAGE.md` |

### Cross-cutting process

| Process | Why it matters | Trigger |
|---------|----------------|---------|
| Re-run `refresh_agent_readme_survey.md` whenever a new ergonomics item ships | Keeps deepwiki survey honest; confirms the gap we just closed wasn't simultaneously closed in two competitor agents (which would shift priorities). | Before merging any P1 daily-use item |
| Add an "ergonomics smoke" acceptance flow (`test_daily_ergonomics_flow.py`) | One end-to-end test that runs `init` → `daily` → `recipes run review-diff` → `yesterday` to prevent silent regressions in the daily path. | After `init` + recipe registry land |
| Track time-to-first-useful-run in `docs/use-case-matrix.md` | Numeric KPI (seconds from `pip install -e .` to first `agent daily` exit). Surveyed agents implicitly compete on this; we should measure it. | After `init` lands |

Implementation order recommendation: **`init` → config defaults → top-level shortcuts → shell completion → session continuation (resume/fork + background/attach + approval presets) → recipe registry**. Each unlocks the next; together they collapse the daily entry from a 5-flag command to two words, with full session continuity throughout the day.

---

## Recently completed (competitive refresh, 2026-05-22)

| Item | Notes |
|------|-------|
| Docs/provider architecture drift guard | `scripts/validate_docs_consistency.py` now checks README/USAGE/architecture counts against `PROVIDER_CONFIGS`, unique credential env vars (including shared `CLOUDFLARE_API_TOKEN` / `OPENCODEZEN_API_KEY`), and survey doc freshness; `docs/architecture.md` updated to 13 providers. |
| Mode and safety comparison matrix | `docs/USAGE.md` matrix maps permission modes, Plan/Auto/Code lanes, shell mutation, approvals, audit, and rollback; validator enforces every `PermissionMode` value and required topics. |
| Multi-surface launch recipes | `docs/USAGE.md` “Choose Your Surface” table with CLI/TUI/VS Code/MCP/ACP/A2A/ANP/managed-runtime recipes; `validate_surface_recipes` + `test_surface_launch_recipes_flow.py` smoke local commands. |
| Subagent lineage and isolation hardening | Child runs record lineage metadata; `isolation: shared`, `worktree`, or `container` snapshot; `worktree_path`/`container_path` in lineage; `test_subagent_worktree_isolation_flow.py`, `test_subagent_container_isolation_flow.py`. |
| Repo-map / context pack for coding runs | `build_context_pack` on `agent preflight`; candidate files, memories, optional LSP symbols, hybrid/knowledge/GraphQLite read-only hits; `test_context_pack_read_only_flow.py`. |
| Plugin/skill compatibility catalog | `docs/plugin-skill-catalog.md` with fixture-backed `validate_plugin_skill_catalog`. |
| Competitive use-case dashboard refresh | Matrix/HTML include survey review date and open P1/P2 gap counts via `build_use_case_matrix.py` + `render_use_case_dashboard.py`. |
| Periodic mainstream-agent refresh cadence | `docs/release-checklist.md` requires survey refresh before minor releases or protocol ADRs. |
| Everyday usage onboarding | README “Daily Use in 5 Commands”, USAGE daily section, cli recipe table, TUI `daily → preflight → ask → resume` flow. |

---

## Ongoing maintenance (competitive refresh complete)

Competitive-refresh feature work is shipped. Before minor releases or protocol ADRs, run:

```bash
python3 scripts/refresh_competitive_docs.py
```

Then manually refresh [scripts/refresh_agent_readme_survey.md](../scripts/refresh_agent_readme_survey.md) when upstream signals change (see [docs/release-checklist.md](release-checklist.md)).

| Cadence | What to keep in sync |
|---------|----------------------|
| Survey | `Last reviewed` date, source table, `docs/use-cases.md` differentiators |
| Docs drift | `validate_docs_consistency.py` (providers, mode matrix, surface recipes, catalog) |
| Coverage artifacts | `docs/acceptance.md` count, `docs/use-case-matrix.md`, `docs/use-case-matrix.html` via `refresh_competitive_docs.py --check` (CI/review) and `refresh_competitive_docs.py` (intentional regeneration) |
| Extension surfaces | `docs/plugin-skill-catalog.md`, `docs/USAGE.md`, `docs/cli.md` when hooks, isolation modes, or preflight/context APIs change |
| New index backends | `teaagent/context_pack.py` read-only graph evidence when adding search stores |
| Strategic P2 research | hosted/cloud surface docs, background sessions, desktop/client-server packaging, repo-map quality evaluation |
