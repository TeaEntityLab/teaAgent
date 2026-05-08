# TeaAgent Operating Rules

## Architecture

- Keep the harness thin: orchestration, tool governance, state boundaries, audit, and validation belong here; domain reasoning belongs in the model or skills.
- Prefer protocol assets over vendor-specific assets: MCP-style tool metadata, Skills, and portable run records.
- Do not add a second agent framework without an ADR.

## Tool Governance

- Tools must be registered through `ToolRegistry`.
- Each tool requires a name, description, input schema, output schema, and annotations.
- Destructive tools must not run unless an approval token is present for that exact tool call.
- Tool errors must be actionable and classified.

## Runtime Safety

- Every run must have an iteration limit and tool-call limit.
- Every tool call and final result must be recorded in the audit log.
- Long-lived state must be externalized; in-memory runner state is temporary only.

## Skills

- Keep `SKILL.md` short and route details into `REFERENCE.md` or examples.
- Treat skills as reviewed supply-chain assets, not casual prompt snippets.


<claude-mem-context>
# Memory Context

# [teaagent] recent context, 2026-05-08 8:07am GMT+8

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 10 obs (4,175t read) | 92,234t work | 95% savings

### May 8, 2026
22 12:31a 🟣 TeaAgent P0 Agent Harness — Initial Implementation
23 12:35a 🟣 teaagent P1 primitives: trace, context, eval, RAG, skill review, AI-BOM
24 12:54a 🟣 GraphQLite Graph RAG persistence layer added to teaagent
25 1:00a 🟣 TeaAgent CLI with GraphQLite subcommands added
S4 Generate commit message for staged changes adding interactive TUI to teaagent CLI (May 8 at 1:01 AM)
S3 Generate commit message for staged CLI additions to teaagent project (May 8 at 1:01 AM)
26 1:04a 🟣 Interactive TUI added to teaagent CLI
27 8:04a 🟣 Multi-Provider LLM Adapter Layer Added to teaagent
28 " 🟣 ChatAgentConfig and ModelDecisionEngine for Autonomous Agent Runs
29 " 🟣 Agent Prompt Assembly and JSON Decision Parsing in prompt.py
30 " 🟣 CLI Extended with agent run, model, doctor model, and workspace subcommands
31 " 🟣 ApprovalPolicy Gains allow_all_destructive Bypass Flag
S5 Generate commit message for staged changes adding LLM adapters, workspace tools, and chat agent to teaagent (May 8 at 8:05 AM)
**Investigated**: Full staged diff across 12 files in the teaagent project, covering new modules (llm.py, workspace_tools.py, chat_agent.py, prompt.py), updated modules (cli.py, tui.py, policy.py, __init__.py), updated docs (docs/cli.md), and new test files (test_llm.py, test_chat_agent.py, test_workspace_tools.py, test_tui.py).

**Learned**: - teaagent now has a zero-dependency multi-provider LLM adapter layer using Python stdlib urllib
    - Five providers supported: claude (Anthropic Messages API), gpt (OpenAI), gemini (generateContent), openrouter (OpenAI-compatible), opencodezen-go (OpenAI-compatible)
    - Workspace tool pack (7 tools) enforces root-escape protection via Path.relative_to() check
    - Agent prompt format requires strict JSON-only model responses; extract_json_object() handles bare JSON, fenced code blocks, and embedded JSON
    - ApprovalPolicy.allow_all_destructive bypasses per-call-id approval for automated agent runs
    - TUI prompt now shows active provider:model with "!" suffix when destructive mode is on
    - Project instructions loaded from AGENTS.md in workspace root if present

**Completed**: - New teaagent/llm.py: LLMAdapter protocol, ProviderConfig, ClaudeAdapter, GeminiAdapter, OpenAICompatibleAdapter, create_llm_adapter(), available_providers(), check_llm_configuration()
    - New teaagent/workspace_tools.py: WorkspaceToolConfig, build_workspace_tool_registry(), 7 workspace tools registered with ToolAnnotations (read-only vs destructive)
    - New teaagent/chat_agent.py: ChatAgentConfig, ModelDecisionEngine, run_chat_agent()
    - New teaagent/prompt.py: PromptBundle, assemble_agent_prompt(), parse_model_decision(), extract_json_object(), load_project_instructions()
    - Updated teaagent/policy.py: added allow_all_destructive flag with early-return in assert_allowed()
    - Updated teaagent/cli.py: added agent run, model providers, model smoke, doctor model, workspace tools subcommands
    - Updated teaagent/tui.py: added provider/model/root/destructive/ask commands; injected adapter_factory for testability; dynamic prompt string
    - Updated teaagent/__init__.py: exported all new public APIs
    - Updated docs/cli.md: documented all new CLI subcommands, env vars, base URL overrides, workspace tool list
    - New tests: test_llm.py, test_chat_agent.py, test_workspace_tools.py; updated test_tui.py
    - Commit message generated: "Add LLM adapters, workspace tools, and chat agent"

**Next Steps**: Session appears complete — the commit message was the final deliverable. No further work indicated.


Access 92k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>