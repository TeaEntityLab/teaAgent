# Safer path for a foreign host hook — 2026-10-23

> **Claim class:** Dated design. Not current truth, not an installed integration, and not an enforce mode.
> **Owner:** docs
> **Last reviewed:** 2026-10-23
> **Review trigger:** The owner installs the observe snippet on the other computer, or asks to build the veto.
> **Authority:** Owner answers on 2026-10-23. They will install the recorder on another computer. They admitted the fail-open hook friction and asked for a safer path. They did not ask to build a deny-veto in this repo.

## 1. What is unsafe

A host command hook is not a boundary when the host keeps going after the hook crashes, times out, or returns output the host does not understand. Editing the host settings to remove the hook has the same result: no process runs, and the tool proceeds.

Checked against current host docs on 2026-10-23:

| Host | What actually blocks | What does not block |
| --- | --- | --- |
| Claude Code | Exit 2 on a synchronous hook. `onFailure: "block"` on a `command` or `http` hook also blocks when that hook crashes or times out. That field needs Claude Code v2.1.295 or later. Source: [Hooks reference](https://code.claude.com/docs/en/hooks). | Exit 0 or 1, a timeout without `onFailure: "block"`, and any `async: true` hook. Async hooks cannot apply `permissionDecision`. |
| Codex CLI | Exit 2 with a nonempty stderr reason, or JSON `permissionDecision: "deny"`, on a synchronous trusted `PreToolUse` hook. Source: [Hooks](https://learn.chatgpt.com/docs/hooks). | Timeout, spawn failure, crash, and malformed output. There is no documented fail-closed switch. The request for one is open as [openai/codex#41979](https://github.com/openai/codex/issues/41979) (2026-09-01). `permissionDecision: "allow"` is a one-shot approval and skips the host prompt. |

TeaAgent cannot change those host rules from inside a process that never starts.

## 2. Path to install on the other computer

This is observation, not a veto. A crash loses one log line. It cannot allow a tool, because the hook is not on the decision path.

On that computer, with the interpreter that has TeaAgent installed:

```bash
/path/to/that/venv/bin/python -m teaagent.foreign_hook --print-install
```

Paste the JSON into the **user** Claude Code settings (`~/.claude/settings.json`), not into this repository. Regenerate it there. A snippet copied from another machine points at the wrong interpreter. The command is that interpreter's absolute path, shell-quoted, then `-m teaagent.foreign_hook`. A bare `python` is wrong: a user-level hook runs in each project's directory and does not activate the checkout virtualenv, so observations would be dropped outside this repo. `--print-install` runs that command once from an unrelated temporary directory and prints the snippet only if the probe records an event. TeaAgent has to be installed in that interpreter. The snippet is `PostToolUse`, `async: true`. It does not pass `--enforce`. The default audit file is `.teaagent/foreign-hooks/observe.jsonl` under the project directory. The event stores the tool name, session id, permission mode, byte count, and a SHA-256. It does not store tool arguments or tool results.

Do not point that command at `PreToolUse`. On Claude Code a slow or crashed `PreToolUse` hook allows the tool unless `onFailure` is `block`. On Codex a crashed `PreToolUse` hook allows the tool, and this design does not give a Codex `PreToolUse` snippet. Codex's own sandbox and approval mode stay the boundary.

Nothing in this repository writes `~/.claude/settings.json`, Codex config, or an oh-my-pi extension. The command sequence, the JSON shape, and the check that one event landed are in [owner-experiment-samples-2026-10-23.md](../work-log/owner-experiment-samples-2026-10-23.md). That file is a sample, not a record that the hook was installed.

## 3. Veto path, not built

A later veto has to be a different process from the recorder.

1. The owner sets the host to fail closed before any TeaAgent code runs. On Claude Code that is a synchronous `PreToolUse` `command` hook with `onFailure: "block"` and a short `timeout`. On Codex that setting does not exist, so a Codex hook is the wrong place for a veto.
2. The command on that path exits 2 before it imports `teaagent`. The recorder's cold start is still tens of milliseconds, and a timeout without a host-side block allows the tool. The recorder stays on the async post-tool path in section 2.
3. The veto command never prints `permissionDecision: "allow"`. That skips the host's own prompt. An uncertain read, a missing file, or a bad payload exits 2 with a short stderr reason and no tool body.
4. Removing the hook from the host settings still fail-opens, on both hosts. No local process can notice a hook that is no longer configured. The safer path does not claim otherwise.

Building that veto still needs a dated owner request. This document is the design, not the build.

## 4. What stays archived

The owner policy recorded on 2026-10-23 is to archive code rather than delete it, except code that is wrong. The observe recorder stays. ADR-0043 surfaces stay quarantined until the 2026-12-09 review. No surface was deleted from this design.
