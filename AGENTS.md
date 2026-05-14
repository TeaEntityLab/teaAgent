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

# [teaagent] recent context, 2026-05-14 4:12pm GMT+8

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 21 obs (8,973t read) | 185,455t work | 95% savings

### May 8, 2026
22 12:31a 🟣 TeaAgent P0 Agent Harness — Initial Implementation
23 12:35a 🟣 teaagent P1 primitives: trace, context, eval, RAG, skill review, AI-BOM
24 12:54a 🟣 GraphQLite Graph RAG persistence layer added to teaagent
25 1:00a 🟣 TeaAgent CLI with GraphQLite subcommands added
S4 Generate commit message for staged changes adding interactive TUI to teaagent CLI (May 8 at 1:01 AM)
S3 Generate commit message for staged CLI additions to teaagent project (May 8 at 1:01 AM)
26 1:04a 🟣 Interactive TUI added to teaagent CLI
S5 Generate commit message for staged changes adding LLM adapters, workspace tools, and chat agent to teaagent (May 8 at 1:05 AM)
27 8:04a 🟣 Multi-Provider LLM Adapter Layer Added to teaagent
28 " 🟣 ChatAgentConfig and ModelDecisionEngine for Autonomous Agent Runs
29 " 🟣 Agent Prompt Assembly and JSON Decision Parsing in prompt.py
30 " 🟣 CLI Extended with agent run, model, doctor model, and workspace subcommands
31 " 🟣 ApprovalPolicy Gains allow_all_destructive Bypass Flag
S6 Generate commit message for staged changes adding permission modes and hash-anchored workspace edits to teaagent (May 8 at 8:05 AM)
32 8:08a 🟣 Run Store, CLI, and TUI Support Added to teaagent
33 " 🟣 RunStore: Persistent JSONL-based Agent Run History
34 8:32a 🟣 PermissionMode Enum and Granular Tool Access Control
35 " 🟣 Hash-Anchored Line Editing Tools
36 " 🟣 Shell Tool Split: workspace_run_shell_inspect vs workspace_run_shell_mutate
37 " 🟣 --permission-mode CLI Flag and TUI permission Command
S7 Generate commit message for staged changes — TeaAgent intent clarification layer (May 8 at 8:33 AM)
38 8:39a 🟣 Deterministic task clarification system added to TeaAgent
39 8:46a 🟣 Memory Catalog added to teaagent
S8 Add workspace memory catalog to teaagent — new MemoryCatalog feature with CLI, TUI, and agent prompt injection (May 8 at 8:46 AM)
40 8:57a 🟣 Deterministic task-based model routing added to teaagent
41 2:07p 🟣 MCP HTTP Transport Layer Added to teaagent
42 2:08p 🟣 Streamable HTTP Transport for MCP Server Implemented

Access 185k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>