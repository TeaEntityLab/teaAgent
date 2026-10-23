# Architecture Rethink — Survey, Lenses, and What Landed (2026-10-23)

> **Claim class:** Dated review and continuation record; not current truth or scheduling authority.
> **Status:** Recorded 2026-10-23. Recommendations stay proposed. No goal text, roadmap status, or enforcement mode was changed.
> **Owner:** docs
> **Last reviewed:** 2026-10-23
> **Review trigger:** Owner disposition of the attach-or-not question, a booked B1 session, or a decision to install the observe-only hook.
> **Recording authorization:** The owner asked, on 2026-10-23, for evidence-based Socratic review in several roles, a survey of current agent systems, doc and roadmap updates where that is legitimate, and code that serves the existing concepts. That authorizes this record, the audit-chain fix, and the observe-only recorder. A later same-day pass deferred the OpenTelemetry import and stopped a red lint job from skipping the governance CI jobs. It does not amend [Harness-First Direction](../strategy/harness-first-direction-2026-06-13.md) and it is not an owner-override paragraph for a product pivot.
> **Repository HEAD observed when recording:** `fa5199da7c876cd75f89012b871611f732953d68`.

## 1. Recommendation

**Keep the ratified concept: a personal, local-first governance harness. Do not restate TeaAgent as a foreign-harness kernel in current-truth docs.**

The session's evidence is enough to say the owner's coding on this repo is not happening in TeaAgent's runner, and that TeaAgent's approval, audit, receipts, undo, and effect authority therefore do not see that work. It is not enough to replace the harness-first identity. Three lenses wanted a pivot. Two lenses, including the one whose job was to attack the pivot, said the pivot is an unproven escape hatch and that a host hook is an advisory veto, not a boundary.

What this session did instead:

1. Recorded the survey and the lens disagreement here, as hypothesis intake.
2. Fixed a real hash-chain fork: `AuditLogger.record` trusted an in-memory tip, so a second process appending to the same file broke `prev_hash`.
3. Added an opt-in observe-only recorder, `python -m teaagent.foreign_hook`. It is not installed into any host, it does not store tool arguments, and `--enforce` exits 2 because enforcement is not implemented.
4. Stopped `teaagent/audit.py` from importing OpenTelemetry unless `enable_opentelemetry` is called.
5. Stopped `.github/workflows/ci.yml` from skipping `governance-gate` and `review-institution` when `lint` fails. `package` still needs both.

Authority stays, in order: harness-first direction, [DR-006](../strategy/dr-006-owner-decision-2026-06-22.md), [Roadmap Status](../roadmap-status.md), then dated reviews such as this file.

## 2. What was re-checked in this recording step

| Check | Result |
| --- | --- |
| `python3 scripts/prepare_g1_evidence.py` | 1,538 runs; 0 `origin=owner`; 1,216 synthetic; 322 unknown; `verdict: unexercised` |
| `scripts/check_root_module_count.py` | at or under the frozen cap of 184 after `teaagent/foreign_hook.py` |
| `pytest tests/test_audit.py tests/test_ws3_audit_chain_remaining.py tests/test_audit_chain_tip_resync.py tests/test_foreign_hook.py` | passed (this recording step) |

Not re-done here: re-cloning upstream repos, re-counting Codex/Claude/oh-my-pi session files, and the governance lens's commit-share percentage. Those figures below are the survey and lens reports from this same session, labeled as such.

Session census used by the lenses (local file counts and dates only; contents were not treated as evidence of what the owner asked): Codex CLI session files mentioning this repo were counted in the low hundreds across 2026-04 through 2026-10, Claude Code on the order of ten, oh-my-pi on the order of ten including this session, OpenCode one. TeaAgent's own runner: 0 owner-origin runs on the re-check above. The intent lens reported that the 322 unknown-origin runs are synthetic benchmarks and dogfood, not hidden owner use. This recording step did not re-classify those 322 rows; the instrument still reports them as unknown.

## 3. Lens verdicts on "pivot to an attachable kernel"

| Lens | Verdict on that pivot | What this record adopts |
| --- | --- | --- |
| Concepts / intents / goals | Agree, with a demand to pivot | The zero-owner-run observation. Not the sentence that the project must pivot. |
| Behavior tests | Agree, with a demand to cut the runner over to a foreign-attached kernel | G1 has no product behavior test; G6's "behavior" marker is a file stamp, not proof the owner can do the job. Not the cut-over. |
| Gates | Agree, with wording that the primary role must be an attaching kernel and that most commits are ritual | DR-006 still requires a dated owner-override before a novel foreign integration is scheduled as the product. The "~84% of commits" figure was counted from reflog transitions and was **not** re-derived here. Gate demotions were not done. |
| Security | Disagree with "governance never touches that work" as the end state, and disagree that a hook *is* governance | Adopted wording: a host hook can be a tamper-evident audit plus a deny-veto the host may ignore. It is defense in depth, not the sole gate. Host default on crash, timeout, and bad JSON is fail-open. The host can edit the hook's own config. |
| Devil's advocate | Disagree. A pivot skips the question of whether the owner wants governance in the daily tool. | Adopted: do not install a hook for the owner; do not build enforce mode; do not store raw tool bodies. The observe recorder is the instrument for a trial the owner still has to choose. |
| Architecture | No report from the lens. It was still reading the tree when its budget ended. | A later line count is in §8. It is a size map, not a cut list and not a pivot. |

Converged sentence, for this record only:

> The owner's agentic coding on this repo shows up in other harnesses, and TeaAgent's runner has no owner-origin runs, so the governance kernel does not currently see that work. Whether TeaAgent should attach to those harnesses is an open hypothesis. Until the owner says so, the ratified concept remains a personal governance harness, and the only attach code is an uninstalled observe-only recorder.

## 4. Survey pins and the seams that matter

Pins are the survey agents' pins from 2026-10-23. This recording step did not re-clone.

| System | Pin reported | Seam that decides an adapter |
| --- | --- | --- |
| pi `earendil-works/pi` | `906e1302`, tag v1.4.0 | In-process `tool_call` extension can block. RPC and session-file tailing cannot approve a call before it runs. No audit chain. |
| oh-my-pi | `0b5c27ab`, v18.12.6 | Same in-process gate, plus a 30s fail-closed handler timeout and an opt-in approval mode whose schema default is still yolo. Project trust was removed. No audit chain. |
| OpenCode | v2.1.3 (tree `bb25a2f4` in the plugin survey) | V2 `tool.execute.before` throw fails the call before the tool runs. `permission.evaluate` can set allow/ask/deny, but a configured deny never reaches the hook. No hook timeout. V1 docs in the same tree are stale. |
| oh-my-openagent | v5.1.44 | Still the V1 plugin API, with a v2 stub. The survey reported it leaving for its own fork. Not an adapter target. |
| LangGraph | main `9d68e5b3`, release 1.2.16 | `interrupt()` re-runs the node from the start. Finished tasks are restored; unfinished ones re-execute. That is at-least-once, not TeaAgent's EFX-001 refusal to redispatch an unmatched mutating start. |
| Google ADK | `7f3517e4`, package 2.12.0 | `before_tool_callback` / a plugin can skip the tool by returning a dict. Confirmation resume re-executes the tool body. Binding is name-and-args equality, not EFX-003's consume-once digest. |
| Claude Code | `65823ec0`, npm 2.1.309 | Command hook on stdin JSON. `PreToolUse` can return `permissionDecision` deny/ask/defer/allow. Exit 2 blocks. Other failures fail open unless the host entry sets `onFailure: "block"`. `PostToolUse` cannot veto. |
| Codex CLI | `rust-v0.164.0` | The vendor survey reported that hooks now exist (it counted 14 events) plus a Starlark exec policy. This recording step did not re-read that protocol. |
| Hermes Agent | v0.22.5 | The vendor survey reported smart approvals and several hook systems. Not re-read here. |

TeaAgent is ahead of pi, oh-my-pi, and OpenCode on hash-chained audit, undo, and consume-once effect authority. Those systems are ahead on the editor loop the owner actually runs. Copying their surfaces (yolo default, unsandboxed extensions, omp's million-line tree, LangGraph's blind node replay) would trade away the part that is actually distinct.

Hypothesis IDs from the surveys stay hypotheses. They are not scheduled. The decision-critical cluster is:

| ID | Hypothesis | Disposition |
| --- | --- | --- |
| SRV-PI-07 / the Claude `PreToolUse` command | A TeaAgent process can observe or veto foreign tool calls | Open. Observe-only instrument landed, uninstalled. Enforce not scheduled. |
| SRV-PI-01 | Leaf-pointer session tree | Open. No owner evidence that linear runs are the pain. |
| SRV-PI-04 | Wire the defined-but-unwired session hooks inside TeaAgent's own runner | Open, and a different question from foreign hooks. M5 still says they stay unwired on purpose. |
| LangGraph / ADK resume | Do not copy re-execution of a node that already performed a side effect | Rejected as a copy. EFX-001/003 stay the local rule. |
| OpenCode V2 `permission.evaluate` | Same shape as a policy hook, still in-process and fail-open on a hung hook because there is no timeout | Open. Not an adoption. |

Two of these are also in the [operator friction log](../work-log/operator-friction-log.md) as open hypotheses. That log is not roadmap demand.

## 5. Code that landed, and why it is allowed

### 5.1 Audit tip resync — `governance-gap`

`AuditLogger` loaded the last hash once, then `record` chained from that memory inside `file_lock` without reading the file again. The lock stopped interleaved writes. It did not stop this: logger A and logger B both start at genesis; A appends; B appends with `prev_hash=genesis`. `verify_audit_chain` then reports a prev-hash mismatch. A foreign hook is a new process per call, so this bug is on the path of any multi-process audit, including the observe recorder.

`record` now reads the last hashed event under the lock and chains from that. Timestamps move forward with the tip so a later writer does not insert an earlier `created_at`. Behavior coverage: `tests/test_audit_chain_tip_resync.py`. Risk note: [audit-chain-tip-resync-2026-10-23-risk.md](audit-chain-tip-resync-2026-10-23-risk.md).

### 5.2 Observe-only recorder — instrument, not a pivot

`python -m teaagent.foreign_hook` reads one JSON object from stdin and appends `foreign_hook_observed` with event name, tool name, session id, permission mode, byte count, and a SHA-256 of the retained stdin. It does not write `tool_input` or `tool_response`. Stdin is capped (default 1 MiB). `--enforce` exits 2 before it touches the audit log, which a Claude Code `PreToolUse` hook treats as a block. A best-effort `mode=enforce_refused` event is written only when the log can be created; if `AuditLogger` cannot be constructed, the process still exits 2 and writes nothing. Exit 0, the observe path, prints `{}` and no `permissionDecision`. If the observe audit log cannot be created, or `record` keeps the event in memory after a disk error, it still prints `{}` and exits 0, and stderr says the observation was not recorded.

Nothing writes `.claude/settings.json`, Codex config, or an oh-my-pi extension. Installing it is the owner's trial, which is the falsifier the devil's-advocate lens asked for: if the owner does not keep it installed, do not build the enforce path.

A cold process is too slow for a synchronous pre-tool hook. Five runs of `python -m teaagent.foreign_hook` against a private audit file, after one warmup, took 153, 168, 260, 216, and 235 ms (median 216 ms) on this machine on 2026-10-23. That is the process start plus audit append, not a hosted-hook timeout. Those runs still imported the OpenTelemetry SDK because `teaagent/audit.py` imported it at module load. That import now happens only inside `enable_opentelemetry`, which this recorder does not call. Five runs after that change, same method, took 66, 63, 68, 70, and 69 ms (median 68 ms). Do not install it on Claude Code `PreToolUse` until that cost is acceptable. `--print-install` prints a `PostToolUse` snippet with `async: true`, so the recorder is off the tool path. The command is this interpreter's shell-quoted absolute path, not bare `python`, and the snippet is printed only after that command records one event from an unrelated temporary directory. It does not write the host config.

DR-006 class for this file: the owner asked for code that serves the governance concept, and the slice does not change policy outcomes. It is an evidence instrument. It is not `owner-override` for a new product shape. Turning it into a deny-veto that emits `permissionDecision` still needs a dated owner-override in DR-006 or the friction log, plus the security tests in the security lens (hook-config tamper, veto-payload redaction, review-noise). Those tests were not written, because that mode was not built. The observe install command is shell-quoted and covered by `tests/test_foreign_hook.py`.

### 5.3 Governance jobs are not skipped by a red lint run

`governance-gate` and `review-institution` in `.github/workflows/ci.yml` no longer set `needs: lint`. On 2026-09-09 a config-access ratchet failed `lint`, and GitHub skipped the approval, plan-gate, permission-matrix, audit-schema, and DR-006 steps because those jobs needed it. A red lint run still blocks `package`, which needs both `lint` and `governance-gate`. `docker-smoke` still needs `lint` and is `continue-on-error`. Locked by `tests/test_ci_governance_flow.py`. No roadmap status moved.

## 6. Must not do next, unless the owner decides

- Do not edit harness-first goal text or the positioning paragraphs. That file says human review first.
- Do not move G1–G6, H4, EFX, ADR-0031, or ADR-0043 statuses from this review.
- Do not delete the ADR-0043 quarantine. On 2026-10-23 the owner said to archive code rather than delete it, except code that is wrong, and confirmed the quarantine stays until 2026-12-09.
- Do not demote the doc-bundle gates in the same change as a product idea. The gate ledger is a proposal. Safety gates (assertion regression, audit schema, plan gate, approval fuzz, high-risk paths) stay.
- Do not emit `permissionDecision: "allow"` from a future hook. That skips the host's own prompt.
- Do not copy foreign `tool_input` into any field the host will show the model.
- Do not treat LangGraph checkpoint resume or ADK confirmation resume as a replacement for EFX-001/003.

## 7. Owner answers, 2026-10-23

1. **B1 was not recognized, and no session was booked.** B1 is one real coding task run through TeaAgent while the owner watches: tool activity, an approval or rejection, a receipt, and an undo. It is not a mode, a milestone id the owner has to remember, or the shadow gate itself. The 2026-11-15 extension is unchanged. Nothing was reverted.
2. **The owner will install the observe recorder on another computer.** This machine was not configured. On that computer, run `--print-install` with the interpreter that has TeaAgent installed. The printed command is that interpreter's shell-quoted absolute path, not bare `python`, and the command is probed from an unrelated directory before it is printed.
3. **Do not remove the recorder.** The owner's policy is to archive code instead of deleting it, except code that is wrong.
4. **ADR-0043 stays archived** until the 2026-12-09 review. No surface was deleted.
5. **The "other harness" friction is admitted** (F9). It stays open until those sessions are actually visible to the audit.
6. **The fail-open hook friction is admitted** (F10). The safer path is designed in [foreign-hook-safer-path-2026-10-23.md](foreign-hook-safer-path-2026-10-23.md). The veto is not built.
7. **A live EFX provider mutation was not run.** The owner said to do the proof. The procedure requires six Definition of Ready values (throwaway target, credential scope, exact payload and budget, pre-state, reversal, and interruption authorization) before any live call. Those values were not given, so the live call stays blocked. Providerless tests passed. Record: [efx-live-proof-2026-10-23.md](../work-log/efx-live-proof-2026-10-23.md).

The steps for those four owner actions are written as samples, not results, in [owner-experiment-samples-2026-10-23.md](../work-log/owner-experiment-samples-2026-10-23.md).

## 8. Package size, measured after the architecture lens timed out

The lens in §3 did not finish. This recording step counted Python lines in the working tree on 2026-10-23 (`teaagent/**/*.py`, skipping `__pycache__`). It is not a deletion plan. The owner said to archive code rather than delete it, except code that is wrong. No directory below was judged wrong from its size.

`teaagent/` is 125,935 lines. The largest directories:

| Path | Lines |
| --- | ---: |
| `cli/` | 20,368 |
| `subagents/` | 11,645 |
| `governance/` | 5,909 |
| `ergonomics/` | 4,017 |
| `tui/` | 3,352 |
| `domain/` | 2,836 |
| `runner/` | 2,704 |
| `approval/` | 2,516 |
| `memory/` | 2,262 |
| `workspace_tools/` | 2,191 |
| `oauth21/` | 2,189 |
| `llm/` | 2,110 |

Counted together, the approval package, the audit and run-record modules (`audit.py`, `audit_chain.py`, `audit_export.py`, `run_evidence.py`, `run_receipt.py`, `run_undo.py`, `run_store.py`), the runner, `policy.py`, `hooks.py`, `foreign_hook.py`, `tool_permissions.py`, `file_policy.py`, and the governance package are 17,636 lines. That is 14% of `teaagent/`. It is an upper bound: `governance/` also holds H4 evidence helpers and a repo-map benchmark, not only plan and review gates. `cli/` alone is larger than that whole group. `tests/` is 138,948 lines.

The root-module cap still holds after `foreign_hook.py`: `scripts/check_root_module_count.py` reported 178 <= 184.

What this supports, and does not support: the ratified harness is a small part of the tree, and the command-line surface is the largest bucket. That is consistent with the north-star note that the runner became a gravity well, and with not restating the project as a foreign-harness kernel. It is not evidence that any bucket should be deleted, and it is not a status change for G1–G6. Session-lifecycle hooks stay unwired on purpose ([M5](../work-log/m5-hooks-observability-only-2026-06-13.md)).
