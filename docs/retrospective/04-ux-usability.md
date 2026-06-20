# 04 - UX and Usability Audit

> Dimension priority: **Fourth** | Method: cx overview + Read/Grep across CLI/TUI/chat/intent/observability/documentation modules and files

## User Journey (Install -> Configure -> Run -> Review), Including Friction Points

1. **Install** - `pip install -e .` (`README.md:74`) or `.[dev]` (`README.md:83`); optional `.[tui]` (`README.md:89`). Smooth; the optional-extra matrix is large but documented.
2. **First run** - `handle_first_run` prints a welcome banner containing the **placeholder GitHub URL** `https://github.com/yourusername/teaagent` (`teaagent/cli/_handlers/_misc.py:475`). **Friction (Critical)**: every new user's first interaction includes a broken link.
3. **Configure** - `teaagent setup --root . --provider gpt --permission-mode read-only --write-env` (`README.md:45`) or `teaagent tui --setup` (`README.md:67`). The wizard (`wizard.py`) redacts secrets (`wizard.py:59-70`). Doctor wizards are available. **Friction**: provider keys require manually copying/sourcing `scripts/providers_env.zsh` (`README.md:296-302`); there is no single `teaagent login` flow.
4. **Run** - `teaagent run "task"` / `teaagent agent run gpt "task"` / `teaagent chat`. **Friction (High)**: `--task` is common enough as an invalid flag to require a "Most Common Mistake" section in USAGE.md (`USAGE.md:604-621`). Positional order differs: `run` is provider-then-task, while `chat` is task-then-provider (`_agent_parsers.py:63-95`). `--clarify` exits with JSON and status 2 instead of asking interactively (`_agent/run.py:536-545`).
5. **Review** - `teaagent agent runs` / `show` / `audit tail` / `--human` run receipt (`run_receipt.py:185-332`). Strong: receipts include a completeness checklist (`run_receipt.py:76-96`). **Friction**: `agent run` task-resolution and plan-gate errors are raw JSON and bypass the hint formatter (`_agent/run.py:279-289,471-473`).
6. **Resume/Undo** - `teaagent agent resume`, `teaagent undo --last`. The documentation honestly lists operations users should "do not rely on" (`daily-driver-current-status.md:173-183`). **Friction**: `agent run --background <id>` may interpret the ID as a new task (`_agent/run.py:410-451`, `daily-driver-troubleshooting.md:12`).

## Evidence

### CLI Entry Point and Argument Parsing
- Entry point: `teaagent = "teaagent.cli:main"` (`pyproject.toml:141`).
- `main()` builds the parser, defaults to `chat` when no command is given (`teaagent/cli/__init__.py:291-293`), and dispatches through `args.func(args)` (`:304`).
- Exit codes are documented inline: `EXIT_SUCCESS=0`, `EXIT_ERROR=1`, `EXIT_BLOCKING=2` ("Blocking issue found - dirty workspace, missing config, needs clarification") (`teaagent/cli/__init__.py:20-26`).
- **Error rendering**: `format_error_block(title, message, hint, category)` includes ANSI color and `-> hint` (`teaagent/cli/_formatting.py:38-56`); it is used for `ProviderKeyError`, `LLMConfigurationError`, `ConfigError`, and `AgentHarnessError` (`teaagent/cli/__init__.py:305-353`).
- **Generic exception fallback**: prints `Unexpected error: {e}` plus an issue URL; traceback appears only with `--verbose` (`teaagent/cli/__init__.py:356-364`). Without `--verbose`, the result is opaque.
- **Inconsistent provider/task position**: `run` is provider then task; `chat` is task then provider (`teaagent/cli/_agent_parsers.py:63-95`).
- **`--parallel` is `type=int, metavar='N'`** (`teaagent/cli/_agent_parsers.py:155-163`), so argparse rejects its string form; the string-handling branch in `_agent/run.py:529-530` is unreachable through the CLI.
- **`--task` is not a flag**, and the mistake is common enough to require a documentation section (`docs/USAGE.md:604-621`).
- **`_normalize_optional_provider_args`** reinterprets a bare token as a task or run ID for `resume` (`teaagent/cli/__init__.py:765-783`). This is clever, but silently resolves the ambiguity between `teaagent run gpt` and `teaagent run "gpt"`.

### TUI
- `run_tui(...)` has 18 keyword arguments, including a default `max_estimated_cost_cents=500` (`teaagent/tui/rendering.py:114-138`).
- `TeaAgentTUI.__init__` has 22 parameters (`teaagent/tui/core.py:56-114`); `chat=False` is the default, with an `_chat_explicit` flag (`:91,99`).
- **The TUI is coverage-omitted**: `omit = ["teaagent/tui/*", ...]` (`pyproject.toml:253`).
- **Advertised but unimplemented TUI commands**: `conflict` prints `{"message": "Conflict resolution mode not yet implemented"}` (`teaagent/tui/_commands.py:365-373`); single-letter `o/t/n/p/a` commands print `"Conflict resolution shortcuts not yet implemented"` (`teaagent/tui/_commands.py:376-393`). Yet HELP_TEXT documents them (`teaagent/tui/rendering.py:67-72`) and the live state panel instructs users to invoke them (`teaagent/tui/core.py:226-238`).
- **`parallel`/`select`/`cancel` are handled syntactically but do not fulfill their advertised semantics**: `parallel` stores option strings and returns `status: options_stored` (`teaagent/tui/_commands.py:307-321`); `select` marks an option selected without executing a branch (`:323-353`); `cancel` clears stored options rather than canceling running experiments. They do not start branches, merge results, or cancel experiments as HELP_TEXT promises ("Start parallel experiment branches for comparison," `teaagent/tui/rendering.py:64-65`).
- **Chat mode silently forwards typos**: an unknown command in chat mode falls back to `ask {raw_command}` (`teaagent/tui/_commands.py:396-397`), silently converting a typo into an LLM task.
- **TUI approval `t` (always-for-tool) grants `path_globs=['*']`** with the comment `# Explicit current directory` (`teaagent/tui/core.py:1324-1335`). The security comment is misleading; `*` is a broad glob.
- **The TUI parser hardcodes `--provider gpt` as its default** (`teaagent/cli/_misc_parsers/tui_parser.py:25`) and exposes no budget/iteration flags, unlike `run`/`chat` (`teaagent/cli/_agent_parsers.py:124-133`).
- **Cost is always estimated, never actual**: `_determine_cost_state` returns `actual|estimated|unavailable|unlimited`, but the comment states that actual cost would require a provider billing API that is not implemented (`teaagent/tui/core.py:147-165`).
- **Duplicate `undo` help line**: `undo [run_id]` appears twice in HELP_TEXT (`teaagent/tui/rendering.py:50,81`).
- **The `--chat` flag exists**, but `_chat.py`'s docstring says `--chat-mode` (`teaagent/cli/_handlers/_chat.py:3,15`), indicating docstring drift.

### Chat Agent / REPL
- `chat_command` delegates to `run_tui(chat=True)` (`teaagent/cli/_handlers/_chat.py:40-62`) and forwards `initial_task` (TASK-DD2-001 fix, `_chat.py:37,61`).
- `run_chat_repl` is deprecated and emits a `DeprecationWarning` ("use run_tui(chat=True) via ChatSessionController") (`teaagent/cli/_handlers/chat_repl.py:202-225`). At **894 lines, it is dead in production** and imported only by tests (`tests/test_cli_chat.py:18-20`, `tests/test_e2e_cli_tui_parity.py:132`).
- **The `--no-tui` flag is documented in several places but does not exist**: multiple module documents describe `--no-tui -> run_chat_repl` (`docs/modules/cli/api.md:73,136`, `docs/modules/cli/inspection.md:32-33`, `docs/modules/tui/inspection.md:48,57,78`, `docs/modules/chat_session_controller/api.md:73`, `docs/decisions/trade-offs.md:101`); grep of `teaagent/cli` finds no `no_tui`/`--no-tui`, so users receive "unrecognized arguments."
- `ChatSessionController` unifies result display (CG-01), undo (CG-02), and cost (CG-03) (`teaagent/chat_session_controller.py:45-62,199-219`); failures print `result.error_message or f'[{result.status}]'` (`:204`).
- `SessionStore` prevents path traversal (`teaagent/session.py:215-223`).

### Intent Clarification
- `clarify_task` scores intent/outcome/scope/constraints/success and generates a `question` through `next_question` (`teaagent/intent.py:70-181`); the ambiguity threshold is `> 0.4` (`:27`).
- **Non-interactive**: `clarify_command` only calls `print_json(clarify_task(args.task).to_dict())` (`teaagent/cli/_handlers/_misc.py:22-24`). `agent run --clarify` prints `{'status': 'needs_clarification', 'clarification': ...}` as JSON and exits 2 (`teaagent/cli/_handlers/_agent/run.py:536-545`). The generated question is buried in JSON; the user is never prompted to answer it. The "intent clarification layer" presents ambiguity as a JSON blob rather than a conversation.

### Error Actionability
- Every `AgentHarnessError` has a `hint`; `__str__` appends `-> {hint}` (`teaagent/errors.py:52-60`).
- Default hints are reasonable: `ConfigError` -> "Run `teaagent doctor config-lint` or `teaagent setup --verify`" (`errors.py:68-73`); `BudgetExceededError` -> "Increase max_iterations / ..." (`:79-87`); `ToolPermissionError` -> "Use --permission-mode allow ..." (`:104-124`); `RunCancelledError` -> "Use `teaagent agent resume <run_id>`" (`:188-200`).
- `error-reference.md` documents the hierarchy, categories, and denial reason codes (`docs/error-reference.md:1-55`).
- **Documentation bug**: `error-reference.md:62` claims `EXIT_USAGE = 2 | CLI argument/parsing error`, but the actual constant is `EXIT_BLOCKING = 2` for blocking issues; `EXIT_USAGE` does not exist (`teaagent/cli/__init__.py:20-26`).
- **`agent run` bypasses the hint formatter**: task-resolution errors print `{'status':'error','message':str(exc)}` (`_agent/run.py:471-473`); plan-gate errors are JSON blobs (`_agent/run.py:279-289`); background-run errors are JSON-only (`_agent/run.py:427-451`). These bypass `format_error_block`.

### Session Management / Suspend / Resume
- `RunStore` persists JSONL under `.teaagent/runs/` with tenant partitioning (`teaagent/run_store.py:47-74`); `show_run` reconstructs `RunResult` from events, including `run_failed` and `error_message` (`:285-307`).
- `checkpoint.py` provides `InMemoryCheckpointStore` and `SQLiteCheckpointStore` (WAL) (`teaagent/checkpoint.py:19-90`).
- `suspend_to_background` in `chat_repl.py:37` writes a suspension checkpoint (legacy, deprecated path); TUI `background`/`handoff` only print guidance to use `interactive-review`/`resume` (`teaagent/tui/core.py:1081-1086`).
- **Undo divergence**: historically, TUI `/undo` used a broad git-stash checkpoint while CLI `/undo` used a targeted journal (`docs/daily-driver-known-issues-2026-06-01.md:30-35`). The TUI now uses journal-first with checkpoint fallback (`teaagent/tui/core.py:1063-1079`), but the fallback is still broader; the known-issues document is partially stale.
- The "Do not rely on yet" list is candid: `agent run --background <id>` for resume is explicitly discouraged (`docs/daily-driver-current-status.md:175`).

### Memory Catalog
- `MemoryCatalog` is defined in `teaagent/memory/catalog.py:135`; methods include `add`/`list`/`search`/`add_quarantined`/`list_quarantined` (`:151,224,228,175,439`); data persists to `.teaagent/memory.jsonl` (`:138`).
- **Three presentation paths**: CLI (`teaagent memory ...` via `_memory_parsers.py`), TUI (`/memory` via `teaagent/tui/core.py:651-687`), and prompt injection (`memory_entries_to_prompt` imported in `chat_agent.py:34` and called at `chat_agent.py:600`). README documents the failure-experience loop and live context anchors (`README.md:127-141`).

### Observability
- `--log-format=json` switches to NDJSON through `JsonLogFormatter` (`teaagent/cli/__init__.py:396-400,753-762`), documented in `docs/observability-logging.md`.
- Run receipts (`run_receipt.py:185-332`) include a completeness checklist (`:76-96`) and `check_receipt_completeness` (`:99-107`).
- `evidence_summary.py` produces `RunEvidenceSummary` with four canonical cost states (`evidence_summary.py:17-66`).
- `audit_tail.py` classifies events as lifecycle/tool/approval/audit/other (`audit_tail.py:33-42`) and provides human formatting (`:72-91`).
- `audit_viewer.py` serves an HTML runs/events dashboard (`audit_viewer.py:39-80`).
- `daily.py` builds a `DailyBrief` with a token-budget traffic light and recommendations (`daily.py:290-361,438-448`).
- Recovery guidance is displayed automatically for failed/partial runs (`_agent/run.py:995-997`).

### Documentation / Onboarding
- README has a golden path (`README.md:37-54`); USAGE.md is a 1,013-line walkthrough; INDEX.md is the curated front door; audience-specific onboarding exists for ML researchers and security engineers (`docs/onboarding-ml-researchers.md`, `docs/onboarding-security-engineers.md`).
- **Three conflicting GitHub URLs**: `https://github.com/yourusername/teaagent` (`teaagent/cli/_handlers/_misc.py:475`, a placeholder in the first-run welcome), `https://github.com/anomalyco/teaagent/discussions` (`SUPPORT.md:18`), `https://github.com/TeaEntityLab/teaagent/issues/new` (`teaagent/cli/__init__.py:359`), and `https://github.com/TeaEntityLab/teaagent` (`docs/ops/deployment-guide.md:68`).
- **Onboarding documentation shows a nonexistent command**: `teaagent skill install skill.tsb` (`docs/onboarding-security-engineers.md:84,88`). The actual commands are `skill candidate install` (`teaagent/cli/_skill_parsers.py:94`) and `skill install-from-marketplace` (`:145-146`).
- **Onboarding documentation shows invalid `--parallel` syntax**: `teaagent run --parallel "adam,sgd,rmsprop"` (`docs/onboarding-ml-researchers.md:23,77,86`; `docs/onboarding-security-engineers.md:74`). Argparse rejects a string for the integer argument (`teaagent/cli/_agent_parsers.py:155-163`).
- **Stale dated documentation contradicts current truth**: `tui-daily-driver-guide.md:67` lists "TUI cost not accumulated," and `:54` says "Prefer teaagent chat for accurate live chat cost until TICKET-12 lands," while `daily-driver-current-status.md:46-47` (2026-06-18) says CG-11/CG-12 are fixed. `tui-chat-reference.md:36-37` (2026-06-02) says "TUI path is not fully migrated to ChatSessionController," which is stale. `run-evidence-and-audit-guide.md:82` says "TUI cost display can contradict actual provider spend," which is stale.
- `SUPPORT.md` points to `github.com/anomalyco/teaagent/discussions` (`SUPPORT.md:18`), likely the wrong organization relative to the `TeaEntityLab` repository URL.

## Strengths

- **The error hierarchy enforces hints**: every `AgentHarnessError` subclass has a reasonable default remediation hint; the CLI renders it with color and category.
- **Run receipts are first-class**: comprehensive human-readable receipts include a machine-checkable completeness checklist.
- **Candid status documentation**: `daily-driver-current-status.md:141-183` explicitly lists "Known issues," "Do not rely on yet," and "Recently fixed"; this is unusual and valuable for trust.
- **Daily brief / token-budget traffic light**: `daily.py:290-361` produces readiness status, green/yellow/red pressure, and recommendations for the next safest command.
- **Unified controller**: `ChatSessionController` shares result/undo/cost semantics across CLI and TUI.
- **Permission playbook**: `docs/permission-and-approval-playbook.md` gives concrete scoped-approval scenarios and a security-review checklist.
- **Observability surfaces**: JSON logging, classified audit tail, HTML audit viewer, and a four-state cost model.
- **Memory catalog through three paths** (CLI/TUI/prompt injection), including quarantine and failure-card loops.
- **Recovery guidance appears automatically** for failed runs.
- **Secret redaction** in wizard and doctor output.

## Gaps

| ID | Severity | Summary | Evidence |
| --- | --- | --- | --- |
| G-C1 | **Critical** | The first-run welcome prints the placeholder GitHub URL `https://github.com/yourusername/teaagent` to every new user. **Impact**: the first impression is a broken link, and users cannot find documentation/help. Three other conflicting URLs compound the problem. | `teaagent/cli/_handlers/_misc.py:475`; `SUPPORT.md:18`; `teaagent/cli/__init__.py:359`; `docs/ops/deployment-guide.md:68` |
| G-C2 | **Critical** | TUI command semantics do not match what the UI advertises: `conflict` and `o/t/n/p/a` explicitly return "not yet implemented," although HELP_TEXT and the live state panel instruct users to invoke them. `parallel`/`select`/`cancel` are syntactically handled but only store, select, or clear option strings; they do not start branches, merge results, or cancel experiments as HELP promises. **Impact**: users who follow in-app instructions reach dead ends or receive behavior materially weaker than promised, undermining trust in the operator panel. | `teaagent/tui/_commands.py:365-393,307-361`; `teaagent/tui/rendering.py:64-72`; `teaagent/tui/core.py:226-238` |
| G-H1 | High | Onboarding documentation contains broken/invalid commands: `teaagent skill install` does not exist, and `teaagent run --parallel "string"` fails in argparse. **Impact**: the first command attempted by a new ML/security user fails, making the onboarding guides unreliable. | `docs/onboarding-security-engineers.md:84,88`; `docs/onboarding-ml-researchers.md:23,77,86`; `teaagent/cli/_agent_parsers.py:155-163` |
| G-H2 | High | The `--no-tui` flag is documented in multiple module documents but absent from the code. **Impact**: users following module documentation receive "unrecognized arguments." | `docs/modules/cli/api.md:73,136`; `docs/modules/cli/inspection.md:32-33`; `docs/modules/tui/inspection.md:48,57,78`; `docs/modules/chat_session_controller/api.md:73`; `docs/decisions/trade-offs.md:101` |
| G-H3 | High | Chat mode silently forwards typos to the LLM. **Impact**: typos cost money and produce unintended model responses without a confirmation gate. | `teaagent/tui/_commands.py:396-397` |
| G-H4 | High | Intent clarification is non-interactive: `--clarify` emits JSON and exits 2; the generated question is never presented as a prompt. **Impact**: the "intent clarification layer" does not actually clarify; it only blocks with JSON. | `teaagent/cli/_handlers/_agent/run.py:536-545`; `teaagent/cli/_handlers/_misc.py:22-24`; `teaagent/intent.py:170-181` |
| G-H5 | High | The exit-code table in `error-reference.md` is wrong: it claims `EXIT_USAGE = 2`, but the implementation has `EXIT_BLOCKING = 2` and no `EXIT_USAGE`. **Impact**: users misdiagnose exit status 2 while debugging. | `docs/error-reference.md:62`; `teaagent/cli/__init__.py:20-26` |
| G-H6 | High | Stale dated documentation contradicts current truth: `tui-daily-driver-guide.md:54,67`, `tui-chat-reference.md:36-37`, and `run-evidence-and-audit-guide.md:82` conflict with `daily-driver-current-status.md:46-47` (2026-06-18). **Impact**: users are steered away from working TUI cost behavior, and the guidance is internally inconsistent. | As listed |
| G-M1 | Medium | The TUI is coverage-omitted despite being the recommended daily surface and containing advertised-semantic mismatches. **Impact**: no test gate catches explicitly unimplemented conflict commands or experiment commands that do not fulfill their advertised behavior; regressions and dead UI can ship silently. | `pyproject.toml:253`; `docs/daily-driver-current-status.md:35` |
| G-M2 | Medium | `chat_repl.py` (894 lines) is dead in production but active in tests. **Impact**: tests verify a path users never reach, allowing production and tested behavior to diverge silently. | `teaagent/cli/_handlers/chat_repl.py:202-225`; `tests/test_cli_chat.py:18-20` |
| G-M3 | Medium | `agent run` error paths bypass the hint formatter: task-resolution, plan-gate, and background errors print raw JSON without hints. **Impact**: inconsistent error UX; `agent run` users receive less actionable errors. | `teaagent/cli/_handlers/_agent/run.py:279-289,471-473,427-451` |
| G-M4 | Medium | Undo scope still differs between TUI and CLI in the fallback path. **Impact**: when the journal is unavailable, undo may restore more than expected. | `teaagent/tui/core.py:1063-1079`; `docs/daily-driver-known-issues-2026-06-01.md:30-35` |
| G-M5 | Medium | TUI parser ergonomics are weaker than `run`/`chat`: hardcoded `--provider gpt`, no budget flags. **Impact**: users cannot set a budget when launching the TUI from the CLI, and the default provider can be surprising. | `teaagent/cli/_misc_parsers/tui_parser.py:25`; `teaagent/cli/_agent_parsers.py:124-133` |
| G-M6 | Medium | `--task` positional ergonomics are poor enough to require a documentation section; provider/task order flips between `run` and `chat`. **Impact**: first-run friction and failed commands. | `teaagent/cli/_agent_parsers.py:63-95`; `docs/USAGE.md:604-621` |
| G-L1 | Low | `clarify`/`guidance`/`doctor` discoverability: `clarify` dumps JSON without a next-step prompt. | `teaagent/cli/_handlers/_misc.py:22-24` |
| G-L2 | Low | Duplicate `undo` help line. | `teaagent/tui/rendering.py:50,81` |
| G-L3 | Low | `_chat.py`'s docstring says `--chat-mode`; the actual flag is `--chat`. | `teaagent/cli/_handlers/_chat.py:3,15` |
| G-L4 | Low | TUI approval `t` grants `path_globs=['*']` but labels it "Explicit current directory," a misleading comment. | `teaagent/tui/core.py:1324-1335` |
| G-L5 | Low | The discussions URL in `SUPPORT.md` uses the `anomalyco` organization, while the repository uses `TeaEntityLab`. | `SUPPORT.md:18` |

## Error UX Assessment

**Actionable**: core error paths are strong. `AgentHarnessError` guarantees a `hint`; category-specific defaults point to concrete commands; the CLI renders title + message + `-> hint` + `[CATEGORY]` with TTY-aware color; exit codes are documented inline; traceback is shown only with `--verbose`. `ConfigError` and `ToolPermissionError` hints name exact remediation commands.

**Opaque**: the generic `Exception` fallback prints `Unexpected error: {e}` plus an issue URL without a hint (unless `--verbose`). `agent run` error paths (task resolution, plan gate, background) print raw JSON `{'status':'error','message':...}` and bypass `format_error_block`. `error-reference.md:62` invents a nonexistent `EXIT_USAGE` constant. Denial reason codes are fully documented in `errors.py:9-26` and `docs/error-reference.md:37-54`, but TUI/CLI surfaces do not necessarily map denials inline to the corresponding reason-code guidance.

## Documentation / Onboarding Assessment

**Strong**: README golden path; deep USAGE walkthrough with recipes and common problems; curated INDEX.md front door with a three-tier reading model; audience-specific onboarding guides; scenario-based permission playbook; candid "Do not rely on yet" and known-issues sections; observability guide; error reference; run-evidence guide; recovery recipes; 14-provider key table.

**Weak**: onboarding guides contain nonexistent commands (`teaagent skill install`) or invalid syntax (`--parallel "string"`) - G-H1. Module documentation describes a nonexistent `--no-tui` flag - G-H2. Multiple stale dated documents contradict the current-truth `daily-driver-current-status.md` on TUI cost and controller migration - G-H6. The exit-code table in `error-reference.md` is factually wrong - G-H5. Multiple GitHub URLs conflict - G-C1. The documentation corpus is large (601 Markdown files under `docs/`), and INDEX.md tries to curate it through a "current truth / active work / historical evidence" split; however, stale current-truth candidates (`tui-daily-driver-guide`, `tui-chat-reference`, `run-evidence-and-audit-guide`) show that the curation gate is not fully enforced.

## Recommendations

### P0 - Fix Immediately (Trust/Blocking)
1. Replace the placeholder URL in `handle_first_run` and standardize one canonical GitHub URL across `_misc.py:475`, `SUPPORT.md:18`, `cli/__init__.py:359`, and `docs/ops/deployment-guide.md:68`. (G-C1, G-L5)
2. Implement TUI `conflict`/`o`/`t`/`n`/`p`/`a`, or remove them from HELP_TEXT (`rendering.py:64-72`) and the state panel (`core.py:226-238`). Separately, either implement the advertised branch-start/merge/cancel semantics for `parallel`/`select`/`cancel`, or narrow their help text to their actual option-store/select/clear behavior. Advertising unavailable semantics damages trust. (G-C2)
3. Fix onboarding commands: `teaagent skill install` -> `teaagent skill candidate install` / `teaagent skill install-from-marketplace`; `--parallel "string"` -> `--parallel N` (or change the parser to accept strings and connect the dead branch in `_agent/run.py:529-530`). (G-H1)
4. Correct `docs/error-reference.md:62` to `EXIT_BLOCKING = 2 | Blocking issue found (dirty workspace, missing config, needs clarification)`. (G-H5)

### P1 - Fix Soon (Usability/Correctness)
5. Make intent clarification interactive: when `--clarify` produces `needs_clarification`, present `clarification.question` as a prompt, accept the answer, and rerun rather than exiting 2 with JSON. (G-H4)
6. Route `agent run` task-resolution, plan-gate, and background errors through `format_error_block` with hints. (G-M3)
7. Add TUI command-path coverage (at least dispatch plus advertised commands) so explicitly unimplemented commands and advertised-semantic mismatches cannot ship; reconsider the `teaagent/tui/*` coverage omission. (G-M1)
8. Reconcile stale dated documentation: add supersession notes to `tui-daily-driver-guide.md:54,67`, `tui-chat-reference.md:36-37`, and `run-evidence-and-audit-guide.md:82` pointing to `daily-driver-current-status.md`, or update them. (G-H6)
9. Remove `--no-tui` from all module documentation or implement it. (G-H2)
10. Add a confirmation gate before forwarding chat-mode typos (`teaagent/tui/_commands.py:396-397`), for example: `unknown command "x"; send as task? [y/N]`. (G-H3)

### P2 - Cleanup (Polish/Debt)
11. Retire or connect `chat_repl.py`; choose one. It is currently dead in production but active in tests, risking divergence between tested and production behavior. (G-M2)
12. Align TUI parser flags with `run`/`chat` (add `--max-iterations`, `--max-estimated-cost-cents`, `--memory-limit`; default `--provider` from configuration rather than hardcoding `gpt`). (G-M5)
13. Fix undo-scope divergence and update `daily-driver-known-issues-2026-06-01.md:30-35` after the fallback paths are reconciled. (G-M4)
14. Improve `--task` ergonomics: consider accepting `--task` as an alias or add a CLI hint for its misuse; prominently document the provider/task order flip. (G-M6)
15. Minor: remove the duplicate `undo` help line; correct the `--chat-mode` docstring; fix the `['*']` "Explicit current directory" comment. (G-L2, G-L3, G-L4)
