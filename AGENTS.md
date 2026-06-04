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

# [teaagent] recent context, 2026-06-04 1:00am GMT+8

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (13,372t read) | 726,159t work | 98% savings

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
S19 Reflective Dispatch Mechanism Implementation (May 31 at 4:46 PM)
1565 4:53p 🔵 Verified audit level and scope key usage
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
1664 5:40a 🟣 Module Documentation Generation Structure
1665 5:41a 🟣 Module Documentation Generation Initiated
1666 7:14a ✅ Continue primary Claude session
1667 7:15a ✅ Continue primary Claude session
1668 " 🔵 Sampled audit.py for code style
1669 9:57a 🔵 Initial review of MD status
1670 " 🔵 Rule definition for Risk Issue Roadmap
1671 " 🔵 Current working directory confirmed
### Jun 3, 2026
1818 1:02p 🔵 cx-cli skill execution for project analysis
1868 8:25p ✅ Review of all tasks in markdown files
1869 " ✅ Recent commits and root directory listing
1870 " 🔴 Incorrect grep pattern for markdown tasks
1871 " ✅ Checkbox task counts in markdown files
1872 " ✅ TASK identifier and status patterns in markdown files
1874 8:26p ✅ Inspection of ticket plans and Heddle concept fit document
1876 " ✅ Master index of ticket execution plans
1877 11:56p 🔵 Pi Agent (Pi.dev) Overview
1878 " 🔵 Reflective Research Skill Definition
### Jun 4, 2026
1879 12:30a 🔵 cx-cli skill execution for project review
1880 12:31a 🔵 Initial Project Scan for Risks and UX

Access 726k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>