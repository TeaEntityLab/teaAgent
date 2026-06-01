# Debugging & Troubleshooting
# teaagent — 2026-06-02

Index of debugging documentation. Start with the symptom you are seeing.

---

## Documents

| Document | Use when |
|----------|---------|
| [debug-mode.md](debug-mode.md) | Enabling debug logging, verbose output, pdb, audit stream |
| [logging-architecture.md](logging-architecture.md) | Understanding what gets logged where; Python logging vs audit events; correlation IDs |
| [trace-analysis.md](trace-analysis.md) | Following one run/tool-call/session end-to-end through audit.jsonl |
| [profiling-guide.md](profiling-guide.md) | CPU, memory, I/O profiling; identifying slow tool calls |
| [crash-analysis.md](crash-analysis.md) | Post-mortem: reading tracebacks, finding missing runs, recovering from /undo damage |
| [bug-catalog.md](bug-catalog.md) | All 13 known defeat scenarios with reproduce steps, log signatures, workarounds |
| [debugger-setup.md](debugger-setup.md) | VS Code / PyCharm launch configs, remote attach, pdb in tests |

---

## Existing checklists (from earlier sessions)

| Document | Use when |
|----------|---------|
| [agent-resume-debug-checklist-2026-06-02.md](agent-resume-debug-checklist-2026-06-02.md) | Diagnosing suspend/resume failures |
| [daily-driver-debug-playbook-2026-06-02.md](daily-driver-debug-playbook-2026-06-02.md) | Daily-driver quick triage |
| [tui-chat-debug-checklist-2026-06-02.md](tui-chat-debug-checklist-2026-06-02.md) | TUI-specific issues |

---

## "My app has symptom X" — master decision tree

```
Symptom → Document → Section
│
├─ Cost shows $0.00 in TUI ──────────────→ bug-catalog.md § DS-01
├─ /undo reverted wrong files ───────────→ bug-catalog.md § DS-05
│                                           crash-analysis.md § 6
├─ resume errors "no run_started task" ──→ bug-catalog.md § DS-08
├─ chat "task" opened but task not run ──→ bug-catalog.md § DS-11
├─ Approval granted too broadly ─────────→ bug-catalog.md § DS-12
├─ --max-cost 0 didn't stop spending ────→ bug-catalog.md § DS-13
├─ Run disappeared / not in audit.jsonl ─→ crash-analysis.md § 5
├─ Process hung, no output ──────────────→ crash-analysis.md § 4
├─ I need more debug output ─────────────→ debug-mode.md
├─ I need to follow one run through logs → trace-analysis.md
├─ teaagent is slow ─────────────────────→ profiling-guide.md § 7
└─ I want to set up IDE debugging ───────→ debugger-setup.md
```
