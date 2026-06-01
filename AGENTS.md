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

# [teaagent] recent context, 2026-06-02 1:51am GMT+8

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (13,067t read) | 826,618t work | 98% savings

### May 8, 2026
S4 Generate commit message for staged changes adding interactive TUI to teaagent CLI (May 8 at 1:01 AM)
S3 Generate commit message for staged CLI additions to teaagent project (May 8 at 1:01 AM)
S5 Generate commit message for staged changes adding LLM adapters, workspace tools, and chat agent to teaagent (May 8 at 1:05 AM)
S6 Generate commit message for staged changes adding permission modes and hash-anchored workspace edits to teaagent (May 8 at 8:05 AM)
S7 Generate commit message for staged changes — TeaAgent intent clarification layer (May 8 at 8:33 AM)
S8 Add workspace memory catalog to teaagent — new MemoryCatalog feature with CLI, TUI, and agent prompt injection (May 8 at 8:40 AM)
S14 User continues to explore project instructions and configuration context for teaagent. (May 8 at 8:46 AM)
### May 14, 2026
S15 Benchmark TeaAgent against Hermes/OpenCode/ClaudeCode/Codex via DeepWiki analysis, identify gaps, and design LSP + sub-agent implementation plans (May 14 at 4:13 PM)
S13 User asked "What instructions are you following for this project?" to understand project-specific conventions and guidelines. (May 14 at 4:13 PM)
### May 31, 2026
1454 1:51p 🔵 CX CLI database access denied
1455 " 🔵 CX CLI language support identified
1456 " 🔵 CX CLI executable path confirmed
1457 " ✅ Workspace tools registration updated
1458 " ✅ ToolRegistryBuilder updated for workspace and git tools
1459 " ✅ ApprovalManager and related components updated
1460 " ✅ Code analysis and knowledge backend adapters updated
1461 " ✅ Workspace tool helper functions updated
1462 " ✅ Workspace configuration and gitignore matching updated
1485 1:54p 🟣 Implemented reflective dispatch for issue identification
1486 4:45p 🟣 Implement Reflective Dispatch Mechanism
S19 Reflective Dispatch Mechanism Implementation (May 31 at 4:46 PM)
1487 4:47p 🔵 Locate cx-cli Executable
1488 " 🔵 Project File Count and Listing
1490 4:48p 🔵 cx-cli Capabilities Overview
1492 " 🔵 Teaagent Package Structure and Python Files
1494 4:49p 🔵 cx overview of governance module
1499 " 🔵 cx overview of approval_manager
1506 " 🔵 cx overview of runner module
1511 " 🔵 cx overview of security modules
1564 4:53p 🟣 Implemented reflective dispatch mechanism
1565 " 🔵 Verified audit level and scope key usage
1566 6:41p ✅ Git diff review and CLI smoke tests requested
1567 10:09p 🔴 Fix undefined names in agent CLI handlers
1568 " 🔴 Correct handling of audit events and run summaries
1569 " 🔴 Fix TUI budget wiring and JSON serialization
1570 " ✅ Discard uncommitted changes in AGENTS.md
### Jun 1, 2026
1571 10:30a ✅ Added research documents for agent usability
1572 2:13p 🔵 cx-cli skill identifies MD files for review
1573 2:52p 🔵 UX Audit of Tea-Agent User Workflows
1575 3:01p 🔵 Agent pool slot timeout
1574 " 🔵 cx-cli skill for project-wide analysis
1576 " ✅ Agent plan updated with research progress
1578 " 🔵 Code search for specific keywords
1580 " 🔵 Code search for sandbox and resume functionality
1584 " 🔵 Code search for chat session cost and execution
1588 " 🔵 Git status check
1619 3:02p 🔵 Agent command handler and Git sandbox logic
1627 " 🔵 TUI initialization parameters
1636 " 🔵 Agent run argument parsing variations
1643 " 🔵 Chat command handler error handling and REPL initialization
1651 " 🟣 Session suspension to background task
1594 " 🔵 Chat command handler logic
1601 3:03p 🔵 Chat command handler logic and TUI invocation
1657 7:47p 🟣 Code Improvement and New Discoveries
1658 7:48p 🔵 Reflective Review Skill Documentation
1659 11:14p ✅ Initiate Project Review for User & Agent Utility
### Jun 2, 2026
1660 12:12a 🔵 teaAgent Project Initial Assessment
1661 " ✅ Marked Project State Assessment Chapter
1662 " 🔵 teaAgent README Content
1663 12:37a ✅ Dependency Audit and Security Analysis Initiated

Access 827k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>