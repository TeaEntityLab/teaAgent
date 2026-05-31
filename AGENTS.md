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

# [teaagent] recent context, 2026-05-31 8:38pm GMT+8

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (13,204t read) | 918,908t work | 99% savings

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
### May 28, 2026
1250 9:52a 🟣 Implement Git Diff and Review for Commit Range
1251 " 🔵 Code Review Skill Configuration Details
1252 " ✅ Modified AGENTS.md file detected
1254 " 🔵 Commit History for Code Review Range
1256 " ✅ Summary of Changes Between Commits
1260 9:53a ✅ Project Configuration in pyproject.toml
1266 " 🔵 TeaAgent CLI Command Structure and Handlers
1273 " ✅ List of Modified Files in Commit Range
1277 " ✅ Code Style Violations Detected
1285 " ✅ Git Sandbox Test Functions
1292 " ✅ Git Merge Conflict Markers Found
1302 " ✅ Code Snippets Containing Sensitive Keywords and Subprocess Calls
1307 " ✅ File Changes and Line Counts
1378 10:17a ✅ Loading Reflective Skills
1379 " 🔵 Listing Contents of .omx Directory
1380 " 🔵 Finding Directories within .omx
1382 10:18a ✅ Created Directory for Review Plan
1384 12:42p ✅ Applied Fixes
1385 " ✅ Updated Reflective Plan
### May 31, 2026
1389 1:48p 🟣 Implement Reflective Dispatch for MD File Analysis
1390 1:49p 🔵 Examine Reflective Dispatch Skill Definition
1391 " 🔵 Examine Reflective Spec Plan Skill Definition
1393 " 🔵 Examine Reflective Risk Skill Definition
1395 " ✅ Tracked Modification to AGENTS.md
1396 " 🔵 Examine Analyze Skill Definition
1400 " 🔵 Examine Reflective Review Skill Definition
1454 1:51p 🔵 CX CLI database access denied
1455 " 🔵 CX CLI language support identified
1456 " 🔵 CX CLI executable path confirmed
1457 " ✅ Workspace tools registration updated
1458 " ✅ ToolRegistryBuilder updated for workspace and git tools
1459 " ✅ ApprovalManager and related components updated
1460 " ✅ Code analysis and knowledge backend adapters updated
1461 " ✅ Workspace tool helper functions updated
1462 " ✅ Workspace configuration and gitignore matching updated
1463 " ✅ Schema validation functions updated
1464 " ✅ Code analysis tool registration updated
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

Access 919k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>