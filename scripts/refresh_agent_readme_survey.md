# Mainstream Agent README Survey

Manual checklist for refreshing TeaAgent roadmap claims against upstream agent README conventions.

Last reviewed: **2026-05-21**

## Sources reviewed

| Project | URL | Notes |
|---------|-----|-------|
| Claude Code | https://github.com/anthropics/claude-code | Skills, hooks, permission modes |
| OpenAI Codex CLI | https://github.com/openai/codex | Agent harness + sandbox patterns |
| Cursor Agent | https://cursor.com/docs | IDE agent rules and tool routing |
| Gemini CLI | https://github.com/google-gemini/gemini-cli | Provider/env conventions |
| Continue | https://github.com/continuedev/continue | MCP + IDE integration surface |

## TeaAgent parity checklist

- [x] Tool registry with schema validation and destructive approval
- [x] Audit chain with redaction
- [x] MCP stdio + streamable HTTP
- [x] A2A discovery/delegation
- [x] ACP IDE adapter
- [x] ANP governed federation boundary (`ANPGovernedService`)
- [x] OAuth refresh-token rotation (ADR 0004, implemented 2026-05-22)
- [ ] Google managed runtime (`GoogleADKRuntime`, `VertexAgentRuntime`)

## Next review trigger

Re-run this survey before the next minor release or when adding a new federation/protocol ADR.
