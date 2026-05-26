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

# [teaagent] recent context, 2026-05-26 9:32pm GMT+8

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (12,171t read) | 933,910t work | 99% savings

### May 8, 2026
S4 Generate commit message for staged changes adding interactive TUI to teaagent CLI (May 8 at 1:01 AM)
S3 Generate commit message for staged CLI additions to teaagent project (May 8 at 1:01 AM)
S5 Generate commit message for staged changes adding LLM adapters, workspace tools, and chat agent to teaagent (May 8 at 1:05 AM)
S6 Generate commit message for staged changes adding permission modes and hash-anchored workspace edits to teaagent (May 8 at 8:05 AM)
S7 Generate commit message for staged changes — TeaAgent intent clarification layer (May 8 at 8:33 AM)
S8 Add workspace memory catalog to teaagent — new MemoryCatalog feature with CLI, TUI, and agent prompt injection (May 8 at 8:40 AM)
S14 User continues to explore project instructions and configuration context for teaagent. (May 8 at 8:46 AM)
### May 14, 2026
S13 User asked "What instructions are you following for this project?" to understand project-specific conventions and guidelines. (May 14 at 4:13 PM)
### May 22, 2026
S15 Benchmark TeaAgent against Hermes/OpenCode/ClaudeCode/Codex via DeepWiki analysis, identify gaps, and design LSP + sub-agent implementation plans (May 22 at 11:56 AM)
### May 25, 2026
841 7:55a 🔵 Live Verification: 187 Acceptance Tests Pass, Docs Consistency Clean
844 7:58a 🔵 Analysis Plan Completed: All Four Steps Finished
849 11:20a 🔵 Community Feedback Analysis and Code Gaps
850 " ⚖️ Skill Selection for Project Review
### May 26, 2026
1020 10:10a 🔴 Resolved history file access error in TeaAgent TUI
1021 " 🔴 Fixed GraphQLite runtime error due to missing SQLite extension
1022 " ✅ Configured TeaAgent to use opencodezen-go provider
1023 " 🔵 Identified recurring "tool 'browser_navigate' is already registered" error
1024 " 🔵 Extracted skill metadata for reflective-implement
1025 " 🔵 Identified modified files in TeaAgent repository
1026 10:11a 🔴 Resolved GraphQLite SQLite Extension Loading Error
1027 " ✅ Configured OpenZepplin-Go Provider and DeepSeek Model
1028 " 🔴 Resolved "tool 'browser_navigate' is already registered" Error
1029 11:15a 🔵 Staged Modifications Review
1030 11:16a 🔵 Review of Reflective Review Skill Documentation
1031 12:57p 🟣 Implement User Profile Editing
1032 12:58p ✅ Tracked Git Status
1033 " ✅ Recent Commit Details
1035 1:36p 🔵 Initial Project CLI Functionality Assessment
1037 2:59p 🔵 Agent run task and dry run functionality
1036 3:00p 🔵 CLI command structure and functionality overview
1038 3:18p 🟣 Implement User Authentication with JWT
1039 3:19p ✅ Modified AGENTS.md
1040 " 🔄 Extended Approval CLI Functionality
1042 " 🔄 Detailed Commit Information for Approval CLI Enhancements
1044 " ✅ Recent Commits Summary for Approval CLI
1047 " ✅ Executed Pytest for CLI and TUI Tests
1050 " ✅ Validated Documentation Consistency
1052 " 🔄 Code Analysis for Approval Workflow
1057 " 🔄 Code Snippet from Approval Handler
1063 " 🔄 Approval Store Logic for Grant Evaluation
1072 " ✅ Pytest Execution Results
1083 " ✅ Documentation Consistency Check Result
1087 " 🔄 Approval Store: Grant Checking Logic
1095 " 🔄 Test Suite: Ergonomics Handlers
1104 " 🔄 CLI Help Output for Approval Command
1118 " 🔄 CLI Help Output for Approval Preset Command
1132 " 🔄 CLI Approval Command Help Text
1143 " 🔄 CLI Help for 'approval preset' Command
1155 " 🔄 Test Suite: Approval Explain Command
1166 3:22p 🔄 TUI Command Handling Logic
1190 3:30p 🔵 CLI Functionality Overview and Usage Patterns
1191 7:34p 🟣 Implement User Feedback Mechanism
1192 " 🔵 Content of SKILL.md for reflective-review
1193 " ✅ Local branch is ahead of origin/main
1195 7:52p 🔵 Initial Project CLI Feature Exploration
1196 9:09p 🟣 Implement User Profile Page
1197 9:10p 🔵 Content of SKILL.md for reflective-review
1198 " ✅ Uncommitted changes in AGENTS.md
1199 " 🔴 Improved approval security and health checks

Access 934k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>