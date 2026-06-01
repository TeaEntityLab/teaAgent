# hooks — Behavior Specification

## Purpose

Implements an 8-event hook lifecycle compatible with Claude Code's hook system. Hooks intercept tool execution before and after, provide veto capability, and fire on session lifecycle events.

## Behavior Contract

1. **PreToolUse hooks** run before tool execution. Any hook may return modified arguments (dict) or raise `HookError` to veto the call. `None` means "allow, no changes."
2. **PostToolUse hooks** run after tool execution. Any hook may return modified result (dict). `None` means "keep original."
3. **Session lifecycle hooks** (SessionStart, SessionEnd, UserPromptSubmit, Stop, SubagentStop) receive `(session_id, context)` and return nothing. Exceptions propagate.
4. **PreCompact hooks** receive and may return a modified compaction context.
5. **Hook chain is ordered** — hooks run in registration order. First veto wins for PreToolUse.
6. **`config.enabled = False`** short-circuits all hooks; all run_* methods return `None` immediately.

## 8 Hook Events

| Event | Type | Can veto? | Can modify? |
|-------|------|-----------|-------------|
| `SessionStart` | `SessionHookFn` | No | context dict |
| `UserPromptSubmit` | `SessionHookFn` | No | context dict |
| `PreToolUse` | `PreToolUseHookFn` | Yes (HookError) | arguments |
| `PostToolUse` | `PostToolUseHookFn` | No | result dict |
| `PreCompact` | `PreCompactHookFn` | No | compaction context |
| `Stop` | `SessionHookFn` | No | — |
| `SubagentStop` | `SessionHookFn` | No | — |
| `SessionEnd` | `SessionHookFn` | No | — |

## Permission System

`HookPermissionMode` is **distinct** from `teaagent.policy.PermissionMode`:
- `HookPermissionMode.ALLOW` — no restriction
- `HookPermissionMode.DENY` — block all destructive tools
- `HookPermissionMode.ASK` — block destructive tools in `destructive_tools` set
- `HookPermissionMode.AUTO` — same as ASK (default)

This operates at the per-call level within `PreToolUse`, not the session permission policy.

## Invariants

- A `HookError` from a pre-hook must prevent tool execution — the runner is responsible for catching it.
- Hook registration is not thread-safe by default; register all hooks before the agent loop starts.
- `lint_check_hook` is an alias for `post_lint_check_hook` (same function, legacy name).
- `shell_command_hook` uses `shlex.split` + `shell=False` to prevent injection.
