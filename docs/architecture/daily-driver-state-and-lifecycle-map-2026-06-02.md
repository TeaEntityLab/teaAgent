# Daily-Driver State And Lifecycle Map
# 2026-06-02

This architecture note maps the state surfaces that matter for daily TUI, TUI chat, and
agent-mode usage.

## State objects

| State | Owner | User-visible through | Trust risk |
|-------|-------|----------------------|------------|
| Current root | CLI args, TUI state loader | TUI prompt/status, run paths | Wrong repository work. |
| Chat session messages | Chat session/controller path | REPL/TUI chat transcript | Surface divergence. |
| Session cost | Controller or TUI ledger | `/cost`, budget display | False zero. |
| Run record | RunStore | `agent runs`, `agent show`, resume/review | Lost continuity. |
| Audit events | Audit log writer | Evidence/audit inspection | Unproven claims. |
| Approval state | Approval manager | prompts, pending approvals | Overbroad authority. |
| Undo journal | Undo subsystem | `/undo`, review | Data loss if scope unclear. |
| Checkpoints/stash | Git recovery path | TUI checkpoint/undo | Confused with journal undo. |

## Lifecycle vocabulary

| Lifecycle word | Required backing state |
|----------------|------------------------|
| Running | Active process or task execution loop. |
| Suspended | Durable run id plus enough context to inspect. |
| Background | Active work continuing outside current UI. |
| Resume | Stored task, observations, approval state, and model/provider context. |
| Review | Changed files and run evidence are available for human inspection. |
| Undo | Recovery mechanism and file scope are known. |

## Desired flow

```text
User task
  -> command parser
  -> shared execution/controller path
  -> run record + audit events
  -> visible result + cost ledger
  -> review / undo / resume using same run id
```

## Current high-risk splits

| Split | Risk | Recommended repair |
|-------|------|--------------------|
| REPL chat vs TUI chat | Cost/undo/result semantics drift. | Finish TUI `ChatSessionController` migration. |
| Undo journal vs checkpoint restore | Same user word can imply different blast radius. | Rename or clearly label mechanisms. |
| Suspend printout vs resume store | User gets a command that cannot rehydrate context. | Persist task/observations before advertising resume. |
| Saved root vs explicit root | User intent can be overwritten by stale state. | Track explicit root and skip overwrite. |
| Helper tests vs command tests | CI can prove a helper while UI fails. | Add path-level tests and manual smoke gates. |

## Architecture recommendations

- Keep the harness thin: orchestration, state, audit, and validation here; model reasoning outside.
- Make trust-sensitive state single-source where possible.
- Prefer explicit adapters over exception-based test detection.
- Add a `TUIConfig` only when it reduces real parameter and persistence complexity.
- Treat docs as part of the UX contract, not as an afterthought.
