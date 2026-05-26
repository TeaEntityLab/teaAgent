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

# [teaagent] recent context, 2026-05-26 10:09am GMT+8

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (18,205t read) | 432,550t work | 96% savings

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
797 2:01a 🔵 Full Expanded Test Suite: 26 Tests Pass Including Limits, Promote Flow, and Run Ticket
798 " 🟣 P0 Implementation Complete: 9 Files Modified, Ready to Commit on main
799 2:02a 🔵 Broader Automation Test Suite Passes: No Regressions in Permissions, Webhook, Observability Tests
800 " 🔵 P0 Changeset Final Stats: 364 Insertions, 49 Deletions Across 9 Files, No Whitespace Errors
801 " 🔵 git add Blocked: `.git/index.lock` Cannot Be Created — Operation Not Permitted
802 " 🔵 git add Requires `require_escalated` Sandbox Permission in teaagent Project
803 " 🔵 8 P0 Files Staged for Commit; AGENTS.md Intentionally Left Unstaged
804 " 🔵 git commit Also Requires `require_escalated` Sandbox Permissions
805 2:03a 🟣 Automation Collector P0: Secret Redaction, Timeout/Truncation Handling, Structured Results
806 " 🟣 Provenance Digest Now Covers All Authority/Execution Fields in AutomationSpec
807 " ✅ P0 Git Stage Blocked by .git/index.lock Permission Error
808 " 🔵 Pre-commit Hooks Run on Commit: ruff-format, ruff, mypy, pytest All Triggered
809 2:04a 🔵 Pre-commit pytest Hook Blocked Commit: docs/acceptance.md Out of Date (Pre-existing Failure)
810 2:05a 🔴 docs/acceptance.md Refreshed: Competitive Docs Regenerated with 184 Acceptance Tests
811 " 🔵 docs/acceptance.md Updated with Minimal 2-Line Change After Refresh
812 " 🔵 Targeted Test Re-run: 21 Tests Pass Including test_refresh_competitive_docs
813 " 🔵 Final Staged Index: 9 Files Ready for Commit Including docs/acceptance.md
814 2:06a 🔐 Hardened Automation Provenance: Full Authority Field Digest-Binding
815 2:07a 🟣 P0 Implementation Committed to main: Hash 85e4f2a
816 " 🟣 P0 Commit Pushed to GitHub: TeaEntityLab/teaAgent main 62121f6..85e4f2a
817 2:08a 🔵 Post-P0 Survey: Remaining P1/P2 Backlog in docs/backlog-priority.md and docs/use-cases.md
818 " 🔵 Skill Candidate Pipeline: SkillCandidateStore and Static SkillReviewResult Architecture
819 " 🔵 Skill Candidate Artifact Bundle: 6 Required Files with Trust=Quarantine Default
820 2:09a 🔵 Skill Offline Eval Gate: 6 Deterministic Checks Before Human Review
821 " 🔵 Automation Run State Machine: 6 Terminal States and Reconcile Loop with Auto-Propose
822 " 🔵 provenance_gate.py: Canonical Trust Decision Engine for All Persistent Substrate Writes
823 2:10a 🔵 Skill Candidate provenance.json content_digest Not Re-Validated Against Actual Content at Eval/Install
824 2:14a 🔴 Fixed install gate ordering in skill_candidates.py: artifact validation before digest check
825 " 🟣 Added P1/P2 tests: collector_command network policy and SKILL.md tamper detection
826 " 🔵 P1 acceptance suite fails in sandbox due to loopback socket bind restriction
827 2:18a 🔐 Collector Command Validation with Blocked Executables Blocklist
828 " 🟣 New teaagent/collectors Package with repo_watch Module
829 " 🔴 Test Artifact Write Order Fixed in skill_eval and skill_eval_dataset Tests
830 " 🔵 git add Blocked by Sandbox: .git/index.lock Cannot Be Created
831 " ✅ Full Test Suite Passes: 184 Acceptance + 32 Unit Tests Green
832 7:51a 🔵 Analyze Skill Contract in teaagent Project
833 " 🔵 Reflective Research and Review Skills in teaPrompt Library
834 7:52a 🔵 TeaAgent Project Full Repository Structure
835 " ⚖️ Analysis Plan: Agent Ecosystem Review of TeaAgent
836 7:53a 🔵 TeaAgent Architecture and Feature Set from README
837 " 🔵 TeaAgent Acceptance Test Coverage: 187 Passing, P0/P1/P2 Tiered
838 " 🔵 TeaAgent Competitive Parity: All 28 Market-Standard Use Cases Implemented
839 " 🔵 TeaAgent Competitive Landscape Survey: 8 Agents Reviewed via DeepWiki
840 " 🔵 TeaAgent Architecture: 9-Layer Component Design with State Boundaries
841 7:55a 🔵 Live Verification: 187 Acceptance Tests Pass, Docs Consistency Clean
842 " 🔵 TeaAgent vs Claude Code/Codex/OpenCode Feature Matrix (22 Capabilities)
843 " 🔵 TeaAgent Daily Workflow: Context Profiles, Surface Table, Mode-Safety Matrix
844 7:58a 🔵 Analysis Plan Completed: All Four Steps Finished
849 11:20a 🔵 Community Feedback Analysis and Code Gaps
850 " ⚖️ Skill Selection for Project Review

Access 433k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>