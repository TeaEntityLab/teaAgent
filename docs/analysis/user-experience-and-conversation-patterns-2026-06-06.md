# User Experience and Conversation Patterns Analysis
# teaAgent — 2026-06-06

**Scope.** End-user perspective on teaAgent as a developer tool: first-time setup
through advanced workflows. Evidence is code-grounded (file:line citations) and
supplemented by existing internal audits (`daily-driver-code-grounded-ux-findings-2026-06-01.md`,
`ux-stability-contract.md`, `community-agent-pain-points-survey-2026-06-05.md`).

**Audience.** Developer and PM, not end-user documentation.

**Assumption.** "User" means a developer running teaAgent locally on their own machine.
Non-technical users are addressed in §8 (Critical Assessment).

---

## 1. User Journey Maps

### 1.1 First-time setup — Happy path

```
Install → setup wizard → dry-run → first real run
```

**Commands:**
```bash
pip install -e .
teaagent setup --root . --provider gpt --permission-mode read-only --write-env
teaagent daily "summarize this repo" --dry-run --root . --human
teaagent run "summarize the test suite" --permission-mode read-only --root .
```

**What works:** The README's "Golden path" is concise and correct. The wizard
(`wizard.py` → `run_first_session_setup`) produces a `WizardResult` with a
`safe_command` and `next_steps` list. The `--human` flag converts JSON to readable
output.

**Where it breaks (sad path):**

1. **Provider name is a prerequisite.** The user must already know to pass `--provider gpt`
   (or claude, gemini, openrouter, ollama, vllm, opencodezen-go, workers-ai, aigateway).
   There is no auto-detect. Wrong name produces: `error: unknown provider 'X'` — no
   suggestion of valid names.

2. **API key path is manual.** `--write-env` writes a `.env` file, but the user must
   already have the key. No keychain helper, no browser-auth flow. The README defers to
   `~/.teaagent/providers_env.zsh` as a "recovery recipe", but that is not clearly
   differentiated from the primary path.

3. **JSON is the default output mode.** Without `--human`, `setup`, `daily`, and most
   CLI commands produce raw JSON. A user who omits `--human` on first run sees a wall
   of JSON where they expected human-readable confirmation.

4. **PEP 668 trap.** macOS/Homebrew users hit the system-Python restriction. The README
   addresses this (venv), but the error message from pip is operating-system noise, not
   a teaAgent error. Users without Python experience hit a silent wall before they even
   install.

**Verdict:** Happy path is 3 explicit commands. Sad paths multiply fast due to provider
naming, API key management, and default JSON output.

---

### 1.2 Simple chat (conversational task)

**Entry point:** `teaagent chat` (REPL) or `teaagent tui` → `chat on` → type task.

**REPL path (`teaagent chat`):**

The canonical REPL loop is `chat_repl.py:run_chat_repl()`. As of HEAD:

- Prompt is `teaagent> ` (or `teaagent📌N> ` when N files are pinned).
- User types a task; it executes via `ChatSessionController.execute_task()`.
- Result is printed; cost accumulates in the controller's session state.
- `run_chat_repl` is marked `@deprecated` at `chat_repl.py:217` with a warning:
  *"use run_tui(chat=True) via ChatSessionController"* — but this deprecated path is
  what `teaagent chat` actually invokes.

**Happy path:** Works for simple conversational tasks. Tab completion exists for
`@file` references (`chat_completion.py`).

**Friction:**

- The REPL is deprecated but still the production entry point. Users will see a
  `DeprecationWarning` if they import from Python, but not in normal CLI use.
- Shell escape (`!<command>`) is disabled with an error. Users who expect an
  integrated shell (like Claude Code) get a hard stop.
- `/compact` and `/clear` affect local data structures but the behavior is documented
  as incomplete in earlier audits (CG-04).

**TUI chat path (`teaagent tui` → `chat on`):**

Requires knowing to type `chat on` after entering the TUI. There is no auto-chat-mode
flag at launch. The TUI's `chat` toggle creates a session ID (first 8 chars displayed).
The session persists across TUI commands. Cost accumulates through `ChatSessionController`.

---

### 1.3 Approval workflow

**Setup:** Run with `--permission-mode prompt` or set via TUI `permission prompt`.

**Flow when the agent wants to execute a destructive tool:**

1. Runner halts; writes a pending approval record to `RunStore`.
2. TUI: `approvals pending` shows queued calls as JSON.
3. User reads the JSON, finds the `call_id`.
4. User types `approve <call_id>` to allow.
5. Run continues.

**Happy path (code-grounded):**
```
_commands.py:567  _cmd_approve() → tui.approved_call_ids.add(args[0])
_commands.py:587  _cmd_approvals() → approvals pending → JSON list of blocked runs
```

**Friction:**

1. **Call ID as the UX primitive.** The user must extract a UUID-like `call_id` from
   a JSON blob and type it exactly. There is no "approve run 1" or "approve all
   pending" shortcut in the TUI. (`approval_subagents_approve_all_command` exists
   in the CLI at `cli/__init__.py:40` but is not surfaced in TUI help until `approvals
   subagents approve-all`.)

2. **Approvals are session-scoped in-memory.** `approved_call_ids` is a set on the TUI
   object (`tui/__init__.py`). It does not persist across restarts. If the user restarts
   the TUI, all in-session approvals are lost.

3. **No visual diff at approval time.** The approval prompt shows tool name and call ID
   but not a diff of what would be written. The user must read the plan separately.

4. **Subagent approval queue** (`tui/_approval_subagents.py`) is a separate surface
   from single-agent approvals — two different approval UIs with different commands.

5. **Path-scoped approval grants** (the `ergonomics/approval_store.py` system) are
   powerful but underdiscoverable. The `permissions` TUI command lists presets; creating
   them requires the CLI `teaagent approval grant ...` path.

---

### 1.4 Undo / recovery

**Two undo systems exist (CG-08), documented in the ux-stability-contract:**

| System | Trigger | Scope | Evidence |
|--------|---------|-------|----------|
| UndoJournal | TUI `/undo`, REPL `/undo` (journal path) | Files written by that agent run | `run_undo.py` |
| Git stash checkpoint | REPL `/undo` (checkpoint fallback) | Entire worktree stash | `chat_repl.py:393–468` |
| CLI `teaagent undo --last` | Non-interactive | Last run's journal | `_handlers/_misc.py` |

**Happy path (TUI):**
```
undo                       → journal undo completed   (file-level restore)
                           or checkpoint restore completed  (git-level)
                           or nothing to undo
```
The TUI now labels which method was used (`tui/__init__.py:164–169`).

**Sad path:**

- In the REPL, if no checkpoint exists and no journal exists, the fallback previously
  ran `git checkout -- .`, destroying all uncommitted work (CG-02, since fixed at HEAD).
  The fix removed the destructive fallback. But the checkpoint system is still
  disabled by default (`chat_repl.py:565–567`, comment: *"Automatic checkpoint creation
  disabled for data safety"*). This means `undo` silently does nothing on a session
  where no checkpoint was manually created.

- Users do not know which undo scope applies until they try it.

- `checkpoint` (manual git stash) and `undo` feel like the same operation to users,
  but they are not. No inline explanation at point of use.

---

### 1.5 Suspend / resume

**Suspend (`/background` or `/handoff`):** `chat_repl.py:36–159`

Creates a suspension JSON file at `.teaagent/suspension-<run_id>.json` and writes a
`run_started` audit event. Does **not** continue work in the background. The TUI
guide warns: *"Treat `/background` … as a suspension checkpoint, not proof that work
continues in the background."*

**Resume (`resume <run_id>` in TUI or `teaagent agent resume <run_id>`):**

Reads the original task and observations from `RunStore`, re-runs the task from the
beginning with injected observations. Pending approvals are **not** auto-granted;
the agent re-requests them.

**Key gap:** The user sees `[TeaAgent] Session suspended successfully!` followed by
a run ID and the instruction `teaagent agent interactive-review <run_id>`. If they
instead use `resume <run_id>` in the TUI, behavior is different (re-executes vs.
reviews). Two commands, similar names, different semantics.

---

### 1.6 Advanced: subagents, artifacts, skills

These are power-user paths. The TUI exposes them via `skills`, `skill-diagnostics`,
`skill-health`, `artifact read <run_id> <tool_call_id>`. All return JSON. No
human-readable summaries.

The parallel experiment system (`parallel <optA> <optB>`) requires: `parallel` →
`select <index>` → `cancel`. This is novel and not discoverable from `help` alone.
Conflict resolution shortcuts (`o`, `t`, `n`, `p`, `a`) are listed in help but
implemented as stubs returning JSON with `"message": "Conflict resolution not yet
implemented"` (`_commands.py:355–383`).

---

## 2. Cognitive Load Assessment

### 2.1 TUI command count

The TUI `_COMMAND_DISPATCH` table at `_commands.py:942–984` contains **34 registered
commands**. Adding inline commands handled outside the dispatch (lines 68–388):
`ask`, `run`, `clarify`, `preflight`, `route`, `complexity`, `estimate`,
`session`, `status`, `plan`, `permissions`, `mcp`, `context`, `daily`, `resume`,
`parallel`, `select`, `cancel`, `conflict`, `o`, `t`, `n`, `p`, `a` — **24 more**.

**Total: ~58 distinct command keywords in one prompt.**

This is a hard cognitive load. Even the help text requires scrolling. There is no
`help <command>` for per-command details.

### 2.2 Permission mode vocabulary

Five modes exist: `read-only`, `workspace-write`, `prompt`, `allow`,
`danger-full-access`. They are listed in the README and help text but not
explained at point of use. A user who selects `workspace-write` does not see:
"This allows file writes but blocks shell mutation." The mode is applied silently.

The modes exist on a trust gradient that is not obvious from the names:
- Is `allow` more permissive than `workspace-write`? Yes, but `allow` sounds neutral.
- Is `danger-full-access` truly dangerous? Yes, but users may treat it as "full power."
- `prompt` mode means the system will pause for approval — this is actually the
  **recommended** default, but it sounds passive.

### 2.3 Budget semantics

`RunBudget` (`budget.py:35–49`) has:
- `max_estimated_cost_cents: int | None = 500` — default $5.00 cap
- `0` = spend nothing
- `None` = unlimited

The CLI flag `--max-estimated-cost-cents` accepts both `0` and integers, but the
help text does not explain that `0 = no spend` and `None = unlimited`. A user who
wants to set no limit cannot easily discover to omit the flag (None default) vs.
passing 0.

The effort levels in the REPL (`low=$2, normal=$10, high=$50`) are disconnected
from the `RunBudget` semantics. These are different budget systems in different
surfaces.

### 2.4 JSON as the default

Most TUI commands print JSON: `runs`, `show`, `approvals`, `daily`, `preflight`,
`clarify`, `status`, `permissions`, `session list`, `memory list`, `skills`,
`skill-diagnostics`, `artifact list`.

This is intentional (machine-parseable output) but the TUI is presented as an
interactive operator cockpit. JSON output requires the user to mentally parse
structured data in a streaming terminal session. There is no `--human` flag inside
the TUI (unlike the CLI which has `--human` on `daily`).

---

## 3. Mode Consistency Analysis (REPL ↔ TUI ↔ CLI)

### 3.1 Surface map

| Feature | CLI (`agent run`) | TUI | REPL (`chat`) |
|---------|-------------------|-----|---------------|
| Multi-turn session | No | Yes (chat mode) | Yes |
| Cost tracking | Yes (post-run) | Partial (CG-03 risk) | Runs through controller |
| Undo | `teaagent undo --last` | Journal + checkpoint | Journal + checkpoint fallback |
| Approval | `teaagent approval approve` | `approve <id>` | Not exposed |
| `/compact` | N/A | Stub (not implemented) | Operational |
| `/background` | N/A | `background` (checkpoint) | `/background` (checkpoint) |
| Session persist | No | Yes (ChatSession) | Yes (in-memory) |
| Tab completion | Shell completion | No | `@`-file only |
| `--human` output | Yes | No | N/A |

### 3.2 Undo inconsistency

The UX stability contract states: *"Trust-sensitive facts must not depend on the surface."*
Undo scope is a trust-sensitive fact. The current state:

- TUI: labels `journal undo completed` or `checkpoint restore completed`.
- REPL: says `[TeaAgent] Undo completed successfully` or `Undo completed via
  checkpoint` — same labels, different code paths, same code risk.
- CLI: `teaagent undo --last` uses the journal only; no checkpoint fallback.

A user who switches from TUI to REPL mid-task faces different undo behavior without
any warning.

### 3.3 Chat mode: "three different chat UIs"

1. `teaagent chat` → `run_chat_repl()` (deprecated, still production).
2. `teaagent tui` → `chat on` → `ChatSessionController` via TUI.
3. `teaagent tui` → `ask <task>` → single-task execution, no session history.

All three feel like "chat with the agent" to users but differ on: session persistence,
cost attribution, undo scope, and help commands available. The TUI guide itself notes:
*"Prefer `teaagent chat` for accurate live chat cost until TICKET-12 lands"* —
meaning the recommended chat path is the deprecated one.

### 3.4 "Background" means different things in different contexts

- REPL `/background`: creates a suspension JSON file; does not run in background.
- TUI `background`: same — a checkpoint, not continuation.
- CLI `teaagent cloud submit`: actually submits to a cloud runner (different subsystem).
- `background_list_command` / `background_show_command` in CLI (`cli/__init__.py:70–71`):
  lists "background" runs — unclear relationship to the above.

The word "background" appears in the UX stability contract's reserved-word table with
the required meaning: *"Work continues outside the foreground UI."* The current
implementation violates this for REPL and TUI surfaces.

---

## 4. Feedback and Visibility Audit

### 4.1 Cost tracking

**Status as of HEAD:**

- REPL: cost flows through `ChatSessionController.session_state.session_cost_cents`.
  `/cost` should display real data if the controller is correctly wired. The CG-03
  finding (placeholder `+= 10 cents`) was in the deprecated code path. The
  `ChatSessionController` path calculates cost from run results.
- TUI: uses `self._session_cost_cents` accumulated from `ChatSessionController`.
- Known gap in TUI daily driver guide: *"TUI cost not accumulated — `/cost` can
  remain `$0.00`"* — this is still documented as a known gap.

**User impact:** The user cannot reliably know what a session cost. The dashboard
value may be stale or zero.

### 4.2 Approval decisions

When a tool call is blocked for approval, the user sees a run that stops. To know
why, they must:
1. Run `approvals pending` → JSON with `run_id`, `task`, `pending_approval` fields.
2. Find the `call_id` in the JSON.
3. Approve or deny by call ID.

There is no proactive notification ("⚠️ Run abc123 is waiting for your approval of
`write_file` to `src/main.py`"). The user must poll.

### 4.3 Error messages

Consistent pattern: `error: <reason>` in TUI; `[TeaAgent] Error: <reason>` in REPL.
Most error messages are actionable at the syntax level (`error: ask requires a task`).
At the semantic level, errors are less useful:
- `error: agent task failed — <exception text>` — wraps an OS/network exception
  without context about what the agent was doing.
- `error: run 'X' not found` — no suggestion of which run IDs are valid.
- Provider errors: `error: unknown provider 'X'` — no list of valid providers shown.

### 4.4 Run lifecycle visibility

`runs` in the TUI returns a JSON array of recent runs with `run_id`, `task`,
`status`, and timestamp. `show <run_id>` returns the full run record.

**Gap:** No live run progress in the TUI outside of `progress on` mode, which streams
audit event lines. Users cannot tell if a long-running agent task is still working
or hung without watching the terminal.

### 4.5 Routing decisions

There is no user-facing receipt of why a model/provider was chosen. The `route <task>`
TUI command previews routing before execution, but there is no post-run "here's the
route that was actually used" summary. Community survey identifies this as Pain Point 1.

---

## 5. Conversation Flow Patterns

### 5.1 Multi-turn session feel

Multi-turn sessions in TUI chat mode use `ChatSession` objects stored in `SessionStore`.
The session ID is displayed as the first 8 hex chars (`tui.session_id[:8]`). Messages
accumulate until `session clear` or `compact`.

**Positive:** Context is preserved across tasks in the same TUI session. Pinned files
(`/pin <path>`) are live-synced via `FileWatcher`.

**Friction:**

- `/compact` in the TUI calls `tui._handle_compact()` — the implementation is marked
  as a stub in CG-07. If compaction is not functional, long sessions will silently grow
  until context limits are hit.
- `session switch <id>` requires knowing the exact session ID (8-char hex). There is
  no `session list` output that makes the right ID obvious.
- Context is lost entirely when the TUI exits, unless the session was saved to the
  `SessionStore`. The user has no explicit "save session" command — sessions are
  auto-saved per-turn.

### 5.2 Latency and response streaming

`stream on` enables token-by-token output (`_commands.py:498`). Without it, the
user sees nothing until the full response is ready. For long tasks (multiple LLM
iterations, tool calls) this creates a dead terminal.

`progress on` streams brief audit event lines during runs — a lighter alternative
that shows tool calls but not token content.

Neither is the default. A first-time user who runs a task sits in silence.

### 5.3 Context preservation across surfaces

There is no way to carry a TUI session into a `teaagent agent run` or vice versa.
Each surface is a separate runtime. Suspension (`/background`) saves config and
the last 10 observations (`chat_repl.py:84`) but not the full message history.

---

## 6. Onboarding Friction Assessment

### 6.1 What must a new user know before first run

1. Python ≥ 3.12, pip or uv, venv on macOS.
2. A provider name from a specific list (not displayed until you get it wrong).
3. An API key for that provider.
4. `--root .` is needed (TUI can use a stale root from saved state if omitted).
5. `--human` is needed for human-readable output.
6. `--permission-mode read-only` is the safe starting point.

This is 6 prerequisites before seeing any agent output.

### 6.2 What the wizard does and doesn't do

`run_first_session_setup()` in `wizard.py` covers: provider selection, permission
mode, max iterations, heartbeat, daily cost cap. It writes a config file and
optionally writes env vars.

What it **does not** do:
- Detect or configure the API key automatically.
- Validate that the key works (the `check_llm` callback is injected but optional).
- Explain what each permission mode means before asking.
- Show a test run inside the wizard to confirm everything works.

### 6.3 Help discoverability

`help` in the TUI shows all 58+ commands in a flat, unstructured list. There is no
grouping by task type (chat, approval, session, diagnostics, advanced). A new user
cannot answer the question "how do I start chatting?" from the help text alone —
they must read the guide.

The README references `docs/USAGE.md` for the full walkthrough, but the TUI help
does not reference documentation. There is no `help setup`, `help approval`, or
`help undo` per-topic help.

### 6.4 `doctor` discoverability

`teaagent doctor` has 8 subcommands (`doctor_all`, `doctor_model`, `doctor_providers`,
`doctor_git_sandbox`, `doctor_graphqlite`, `doctor_mcp`, `doctor_env_order`,
`doctor_migration_command`). The TUI's `doctor` command only runs the GraphQLite
check (`_commands.py:421–425`). A user who suspects a provider misconfiguration
must switch to the CLI `teaagent doctor providers` — not obvious from the TUI.

---

## 7. Pain Point Matrix

Ranked by frequency × impact (frequency: estimated from code paths and existing audit
evidence; impact: P0–P2 per the project's own convention).

| Rank | Pain Point | Frequency | Impact | Source |
|------|-----------|-----------|--------|--------|
| 1 | **Cost display unreliable** — TUI can show $0.00 for real work; no real-time budget counter | High (every session) | High (trust) | CG-03, TUI guide known gap |
| 2 | **Three chat entry points with divergent behavior** — REPL (deprecated), TUI chat, TUI ask | High (daily decision) | High (confusion, wrong undo scope) | CG-05, §3.3 |
| 3 | **JSON default in an interactive TUI** — every informational command produces JSON; no `--human` in TUI | High (every info query) | Medium (UX friction) | §2.4 |
| 4 | **Approval flow requires call ID extraction** — no approve-by-run, no approve-latest, no visual diff | Medium (prompt-mode users) | High (security-UX tradeoff) | §1.3 |
| 5 | **"Background" does not mean background** — misleading lifecycle copy violates the UX contract | Medium (any suspend attempt) | High (trust violation) | §3.4, ux-stability-contract |
| 6 | **`compact` is a stub in TUI** — advertised in help, does nothing (CG-07) | Medium (long sessions) | Medium (context bloat → cost) | CG-07 |
| 7 | **Undo scope is invisible** — user doesn't know if journal or checkpoint undo will run | Medium (recovery attempt) | High (data loss risk) | CG-08, §1.4 |
| 8 | **No live progress indicator by default** — agent runs are a silent black box without `progress on` | High (every run) | Medium (dead terminal anxiety) | §5.2 |
| 9 | **Provider name required at setup** — no discovery, no auto-detect, wrong name gives no suggestions | High (first run) | Medium (blocks setup) | §6.1 |
| 10 | **Conflict resolution is a stub** — listed in help, returns JSON "not yet implemented" | Low (merge-conflict users) | Medium (false feature advertisement) | _commands.py:355–383 |
| 11 | **Routing decisions are not surfaced post-run** — no receipt of which model was used and why | Medium (multi-provider users) | Medium (opacity) | §4.5, community survey |
| 12 | **Session IDs as 8-char hex** — no human-readable labels, hard to reference across commands | Medium (multi-session) | Low (usability) | §5.1 |
| 13 | **Tab completion only for `@` mentions in REPL** — no TUI tab completion for commands | Medium (daily use) | Low (ergonomics) | §1.2 |
| 14 | **`teaagent chat` is deprecated but primary** — DeprecationWarning in code, still the CLI entry | Medium (clarity) | Low-Medium (technical debt signal) | chat_repl.py:217 |

---

## 8. Critical Assessment

### 8.1 Would a non-technical user understand this system?

**No.** The intended audience is explicitly a developer. Evidence:
- First-run requires knowing pip, venv, Python version, API key concepts, and a
  provider taxonomy that is unique to the agent ecosystem.
- Error messages use internal terminology (`permission_mode`, `call_id`,
  `GraphQLite runtime`, `cypher query`, `ACP compliance`).
- The TUI help text is a flat command reference, not a conversational guide.
- `doctor` diagnostics return JSON with `ok: bool` and `message: str` — useful
  to a developer, opaque to a non-technical user.

**Assumption we are making:** All users are developers comfortable with command-line
tools, JSON parsing, and API key management. This assumption is baked into every
surface. If teaAgent ever targets a broader audience, the entire I/O model must change.

### 8.2 What are we actually building vs. what we claim to be building?

The README positions teaAgent as having a "governance-first" design with "permission
gates", "audit trail", and "undo". These are accurate claims. But the UX layered over
these mechanisms does not match the governance intent:

- Approvals require the user to manually extract a UUID from JSON — this is governance
  that requires the user to operate as a compliance officer.
- The audit trail is hash-chained JSONL — impressive but not user-readable without
  `audit show` commands.
- Undo is powerful but the scope is invisible at the moment of action.

**The actual experience:** A developer who wants governance gets it, but only if they
invest in understanding the command surface. Casual users get the same tools but with
none of the safety benefits activated (default `prompt` mode requires knowing approval
commands; default `stream off` hides progress; default JSON output hides status).

### 8.3 What assumptions are we making about user sophistication?

1. Users will read `docs/USAGE.md` before hitting problems.
2. Users understand the difference between a "session" (ChatSession), a "run"
   (RunStore entry), and a "task" (string passed to the agent).
3. Users know that `background` means "suspension checkpoint" not "background process."
4. Users will set `progress on` or `stream on` to see what's happening.
5. Users will use `--permission-mode read-only` for exploratory work.

None of these assumptions are safe for a new user. All of them are documented in
guides that are not linked from the surfaces where users need them.

### 8.4 The intended vs. actual first-5-minutes experience

**Intended (from README):**
> One canonical flow for new users. Everything else is advanced.

**Actual:**
- User installs successfully.
- `teaagent setup` outputs JSON (forgot `--human`).
- `teaagent run "summarize this"` produces JSON (forgot `--human`).
- User types a task in the TUI; nothing happens for 10 seconds (forgot `stream on`).
- User types `cost`; sees `$0.00` (known gap).
- User wants to undo; types `undo`; gets `nothing to undo` (no checkpoint created).
- User exits and re-enters; session is gone (didn't use `session` management).

Each of these is a "5-minute abandonment trigger." The happy path exists, but the
surface area for veering off it is enormous.

---

## 9. UX Improvement Roadmap

Organized by effort and impact. "Effort" is implementation complexity; "Impact" is
user-facing trust improvement.

### P0 — Fix before any new feature work

| # | Problem | Fix | Effort |
|---|---------|-----|--------|
| P0-1 | `compact` in TUI is a stub but advertised (CG-07) | Either implement or remove from help text | XS |
| P0-2 | `conflict` commands are stubs returning JSON "not implemented" | Remove from help or add `[not yet available]` marker | XS |
| P0-3 | "Background" means checkpoint, not background | Rename to `suspend`/`checkpoint` in TUI; update help text; add clear "(note: work does not continue)" | S |
| P0-4 | No progress indicator by default | Default `progress on` when running in a TTY; let users opt out | S |

### P1 — High impact, addressable in one sprint

| # | Problem | Fix | Effort |
|---|---------|-----|--------|
| P1-1 | Cost display is unreliable (CG-03 risk in TUI) | Wire `cost` TUI command to `ChatSessionController.get_session_cost()` unconditionally; add `[estimated]` label when using estimate | M |
| P1-2 | Approval requires manual call ID extraction | Add `approve next` (approve the oldest pending call in the queue) and `approve all` shortcut for non-destructive calls | M |
| P1-3 | Undo scope is invisible | Before executing undo, print exactly what will be restored: "Will restore 3 files from run abc123 journal" | S |
| P1-4 | Error messages don't list valid options | On `unknown provider 'X'`, append "Valid providers: claude, gpt, gemini, ..." | XS |
| P1-5 | Provider name must be known before setup | Add `teaagent setup --list-providers` or show valid names in the wizard's first prompt | XS |

### P2 — Medium-term improvements

| # | Problem | Fix | Effort |
|---|---------|-----|--------|
| P2-1 | JSON as TUI default | Add a `format text\|json` TUI command; default to `text` in TTY, `json` when piped | M |
| P2-2 | Help is a flat list | Group help into sections: Setup, Chat, Approval, Session, Diagnostics, Advanced | XS |
| P2-3 | No live run progress without `progress on` | Show a spinner or dot-progress line by default for tasks > 3s | M |
| P2-4 | Session IDs are cryptic | Allow `session label <name>` to attach a human label; display both in `session list` | S |
| P2-5 | Routing decisions are invisible post-run | Add a `route-used` field to run summary: `show <run_id>` should include `resolved_provider`, `resolved_model`, `route_reason` | M |
| P2-6 | `teaagent chat` is deprecated but primary | Promote `teaagent tui` with `chat on` as the canonical chat surface; add deprecation notice to CLI output | S |
| P2-7 | Permission mode names don't explain themselves | Add `permission explain <mode>` to TUI; show one-line explanation before applying | S |

### P3 — Strategic, longer-term

| # | Problem | Fix | Effort |
|---|---------|-----|--------|
| P3-1 | Three chat surfaces with divergent behavior | Unify all chat through `ChatSessionController`; deprecate and remove `run_chat_repl` entirely | L |
| P3-2 | Onboarding wizard doesn't verify the full chain | Wizard should: validate API key, run a test task, show cost estimate, confirm undo is available | L |
| P3-3 | Approval UX requires operator-level knowledge | Design an approval widget: show tool name, path, diff preview, approve/deny buttons in TUI | XL |
| P3-4 | Tab completion in TUI | Implement readline/prompt_toolkit tab completion for TUI commands | M |
| P3-5 | Context not portable across surfaces | Define a session export/import format that works across TUI and CLI | L |

---

## Appendix: Key File Locations for UX Work

| Component | File |
|-----------|------|
| TUI command dispatch | `teaagent/tui/_commands.py:942` |
| TUI help text | `teaagent/tui/__init__.py:78` |
| REPL loop (deprecated) | `teaagent/cli/_handlers/chat_repl.py:198` |
| Approval manager | `teaagent/approval_manager.py` |
| Budget definitions | `teaagent/budget.py:35` |
| Suspension logic | `teaagent/cli/_handlers/chat_repl.py:36` |
| Undo journal | `teaagent/run_undo.py` |
| Permission modes | `teaagent/policy.py` |
| Session controller | `teaagent/chat_session_controller.py` |
| Setup wizard | `teaagent/wizard.py` |
| UX stability contract | `docs/ux-stability-contract.md` |
| Prior UX findings | `docs/analysis/daily-driver-code-grounded-ux-findings-2026-06-01.md` |
| Known gaps (TUI guide) | `docs/tui-daily-driver-guide.md#known-gaps` |
