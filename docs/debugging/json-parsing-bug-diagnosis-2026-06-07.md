# Diagnosis: "Model decision JSON parsing failed" at iteration 3 (deepseek-v4-flash, ~137K context)

Date: 2026-06-07

## Symptom recap

- Run fails at iteration 3 with `RuntimeError: Model decision JSON parsing failed after 2 attempts ...`
- Sequence: iter 2 tool call fails with `tool 'workspace_run_shell_inspect' failed: command is not inspect-safe; retry with workspace_run_shell_mutate` → model attempts a recovery decision in iter 3 → that decision fails JSON parsing.
- Affected: `deepseek-v4-flash`, large context (~137K tokens already accumulated by iter 3).

## Root cause ranking

1. **PRIMARY — hardcoded `max_tokens=1024` on every decision call truncates the model's JSON output.** [chat_agent.py:221-237](../../teaagent/chat_agent.py#L221-L237), [llm/_types.py:86](../../teaagent/llm/_types.py#L86)
   The recovery turn requires a *longer* completion than a normal turn (the model must explain why the previous tool failed, choose `workspace_run_shell_mutate`, and re-supply `command`/`arguments`). With `max_tokens` capped at 1024 and no override, the completion is cut off mid-object. `extract_json_object`/`_repair_json_text` cannot repair a response with unbalanced braces (truncated mid-string or mid-key), so it raises `ToolValidationError('model response did not contain a JSON object')`, which is what surfaces as "JSON parsing failed."
   This is **not detectable today** because `finish_reason` from the provider response is discarded — `LLMResponse` has no such field and `OpenAICompatibleAdapter.complete` never reads `choices[0]['finish_reason']`. [llm/_adapters.py:181-198](../../teaagent/llm/_adapters.py#L181-L198), [llm/_types.py:94-103](../../teaagent/llm/_types.py#L94-L103)

2. **SECONDARY / compounding — the runner's context-window assumption (200K) doesn't match deepseek's real limit (64K), so the warning/compaction machinery never engages before the model is overloaded.**
   `AgentRunner.__init__` defaults `max_context_tokens=200000` and `compaction_warning_threshold=0.6` ([runner/_core.py:103-104](../../teaagent/runner/_core.py#L103-L104)), and `_create_runner_and_engine` constructs `AgentRunner(...)` **without passing either** ([chat_agent.py:617-630](../../teaagent/chat_agent.py#L617-L630)). Meanwhile `teaagent/daily.py` already has the correct per-model number — `_model_context_limit` returns **64,000** for any `deepseek*` model ([daily.py:464-465](../../teaagent/daily.py#L464-L465)) — but that helper is wired only into the `daily` token-budget report, not into the chat-agent/runner path.
   Net effect: at 137K accumulated tokens the runner believes it is at `137000/200000 = 68.5%` (just past its 60% warning line), while the model is actually at **~214% of its real 64K window**. The provider is very likely silently truncating the oldest messages (including the system prompt that carries `DECISION_INSTRUCTIONS` + `DECISION_JSON_SCHEMA`), which materially increases the odds of a malformed/incoherent decision turn — exactly when the recovery turn in iter 3 needs the model to be most precise.

3. **Contributing — the `workspace_run_shell_inspect` vs `_mutate` tool descriptions don't tell the model the routing rule, so it guesses wrong and triggers the failure→recovery chain in the first place.** [workspace_tools/_files.py:341-368](../../teaagent/workspace_tools/_files.py#L341-L368)
   Descriptions are `'Run a bounded read-oriented shell command...'` / `'Run an approval-gated shell command...'`. They never state the actual allowlist enforced by `classify_shell_command_policy` (only `pwd, ls, rg, grep, wc, find, git {status,diff,log,show,branch,grep}`, no shell operators, no path escapes — see [workspace_tools/_shell.py:157-218](../../teaagent/workspace_tools/_shell.py#L157-L218)). The model has no way to predict whether a candidate command is "inspect-safe" before calling, so any command using a pipe, redirect, or an executable outside that allowlist (e.g. `cat`, `head`, `python -c`, `git log | head`) gets routed to `inspect`, fails, and forces a recovery turn — the exact turn that then gets truncated by issue #1.

4. **Working as intended (not a bug, but masks the real problem) — error recovery loop.**
   `_execute_tool_decision`'s `except ToolExecutionError` branch ([runner/_core.py:681-693](../../teaagent/runner/_core.py#L681-L693)) correctly appends `{call_id, tool_name, error, duration_ms}` as an observation, records `tool_call_failed`, and returns control to the loop so the model can self-correct. This is sound design — it is **not** "producing invalid JSON." The invalid JSON comes from the *next* `decide()` call (issue #1), which now has to produce a longer corrective response inside a more crowded context (issue #2).

5. **Working as intended — JSON validation.**
   `parse_model_decision`/`extract_json_object`/`_repair_json_text` ([prompt.py:321-415](../../teaagent/prompt.py#L321-L415)) correctly reject malformed JSON and attempt repair of *cosmetic* issues (bare keys, trailing commas). They cannot and should not try to repair structurally truncated JSON (unbalanced braces) — that would risk fabricating tool calls. The `ToolValidationError` it raises is correct; the bug is upstream (truncation), not in this validator.

**Verdict: Fix #1 (raise/parameterize `max_tokens` for decision calls and detect `finish_reason == 'length'`) is the primary fix. Fix #2 (wire model-aware `max_context_tokens` into the runner) is required to prevent the same failure from recurring at scale and to make the compaction warning meaningful for deepseek's smaller window. Fix #3 is a precision improvement that reduces how often the model lands in the failure→recovery path at all.**

## Fix locations

### Fix 1 — Decision-call output budget & truncation detection (PRIMARY)

- **File/line:** [teaagent/chat_agent.py:221-237](../../teaagent/chat_agent.py#L221-L237) (the `LLMRequest(...)` built inside `ModelDecisionEngine.decide`)
- **Current code:**
  ```python
  response = self.adapter.complete(
      LLMRequest(
          system=prompt.system,
          messages=messages,
          model=self.model,
          stream=self.stream and on_chunk is not None,
          on_chunk=on_chunk,
          response_format={...},
      )
  )
  ```
  No `max_tokens=` is passed, so `LLMRequest.max_tokens` defaults to **1024** ([llm/_types.py:86](../../teaagent/llm/_types.py#L86)).
- **Suggested fix:**
  - Add a `decision_max_output_tokens` (or reuse/raise the existing budget-preflight constant `1024` at [chat_agent.py:209](../../teaagent/chat_agent.py#L209) so both numbers agree) and pass it explicitly: `LLMRequest(..., max_tokens=self.decision_max_output_tokens)`. Default it higher (e.g. 4096) — large tool arguments (multi-line shell commands, file-edit payloads) routinely exceed 1024 tokens.
  - Add `finish_reason: str | None = None` to `LLMResponse` ([llm/_types.py:94-103](../../teaagent/llm/_types.py#L94-L103)) and populate it in `OpenAICompatibleAdapter.complete` from `response['choices'][0].get('finish_reason')` ([llm/_adapters.py:190-198](../../teaagent/llm/_adapters.py#L190-L198)).
  - In `decide()`, when `parse_model_decision` raises **and** `response.finish_reason == 'length'`, skip the generic "repair this JSON" retry message (it cannot help — the content is incomplete) and instead retry with a larger `max_tokens` budget or a prompt that asks for a more concise decision. This turns an opaque parsing failure into an actionable, self-correcting retry.

### Fix 2 — Model-aware context-window ceiling for the runner (SECONDARY/compounding)

- **File/line:** [teaagent/chat_agent.py:617-630](../../teaagent/chat_agent.py#L617-L630) (`AgentRunner(...)` construction inside `_create_runner_and_engine`) and [teaagent/runner/_core.py:103-104](../../teaagent/runner/_core.py#L103-L104) (defaults)
- **Current code (runner construction omits the two context-size knobs):**
  ```python
  runner = AgentRunner(
      registry=tool_registry,
      audit=audit_logger,
      budget=runner_budget,
      approval_policy=approval_policy,
      approval_handler=config.approval_handler,
      budget_prompt_handler=config.budget_prompt_handler,
      compactor=ContextCompactor(memory_keys=('task_spec', 'memories')),
      checkpoint_store=config.checkpoint_store,
      cancel_token=config.cancel_token,
      auto_mode_config=config.auto_mode_config,
      require_plan=config.require_plan,
      skip_plan_check=config.skip_plan_check,
  )
  ```
  `max_context_tokens` therefore stays at the class default of **200,000**, although `_model_context_limit` in [teaagent/daily.py:456-471](../../teaagent/daily.py#L456-L471) already knows `deepseek*` models cap at **64,000**.
- **Suggested fix:** import `_model_context_limit` (or hoist it to a shared module — it's currently private to `daily.py`) and pass the resolved value through:
  ```python
  resolved_limit = _model_context_limit(adapter.provider, config.model) or 200_000
  runner = AgentRunner(
      ...,
      max_context_tokens=resolved_limit,
  )
  ```
  This makes the existing 60%-usage compaction warning fire at ~38K tokens for deepseek instead of ~120K, giving the agent a real chance to `/compact` (or for the compactor at [runner/_core.py:735-751](../../teaagent/runner/_core.py#L735-L751) to run) well before the provider starts silently dropping messages.

### Fix 3 — Tool descriptions that state the inspect/mutate routing rule (reduces failure frequency)

- **File/line:** [teaagent/workspace_tools/_files.py:341-354](../../teaagent/workspace_tools/_files.py#L341-L354) (`workspace_run_shell_inspect` registration) and [:355-368](../../teaagent/workspace_tools/_files.py#L355-L368) (`workspace_run_shell_mutate`)
- **Current code:**
  ```python
  registry.register(
      name='workspace_run_shell_inspect',
      description='Run a bounded read-oriented shell command inside the workspace root.',
      ...
  )
  registry.register(
      name='workspace_run_shell_mutate',
      description='Run an approval-gated shell command inside the workspace root.',
      ...
  )
  ```
- **Suggested fix:** make the description state the allowlist that `classify_shell_command_policy` actually enforces ([workspace_tools/_shell.py:175-218](../../teaagent/workspace_tools/_shell.py#L175-L218)), e.g.:
  ```python
  description=(
      "Run a read-only shell command. ONLY these are accepted: "
      "pwd, ls, rg, grep, wc, find (no -delete/-exec), "
      "git status|diff|log|show|branch|grep. No pipes, redirects, "
      "or other shell operators. Anything else (cat, head, python -c, "
      "pipelines, etc.) MUST go through workspace_run_shell_mutate."
  ),
  ```
  This is a prompt-engineering change (no logic change), but it directly reduces how often the model picks `inspect` for a command that will be rejected — cutting off the failure→recovery→truncation chain at its source.

### Fix 4 — (Token management; folds into Fix 2, listed separately per the requested breakdown)

- **File/line:** [teaagent/runner/_core.py:299-315](../../teaagent/runner/_core.py#L299-L315) (`_check_compaction_warning`) is the only place that currently looks at accumulated tokens vs. a ceiling, and that ceiling is wrong for deepseek (see Fix 2).
- **Current code:** `usage_pct = (total / self._max_context_tokens) * 100.0` where `self._max_context_tokens` is 200,000 regardless of the active model.
- **Suggested fix:** same change as Fix 2 — once `max_context_tokens` is resolved per-model, this function "just works" correctly for deepseek (warns at ~38K instead of ~120K). No separate code change needed beyond passing the right ceiling at construction time. Optionally also lower `compact_after_observations` (currently a flat `20`, [runner/_core.py:102](../../teaagent/runner/_core.py#L102)) for small-context models so compaction triggers on observation count *or* token estimate, whichever comes first.

## Reproduction steps (local)

1. Configure a `ChatAgentConfig` with `model='deepseek-v4-flash'` (or any `deepseek*` model) and a `FakeAdapter`/recorded transport that:
   - Returns a normal tool decision for iteration 1.
   - On iteration 2, returns `{"type":"tool","tool_name":"workspace_run_shell_inspect","arguments":{"command":"cat largefile.txt | head -100"}}` (an inspect-unsafe command — pipe + `cat`, both rejected by `classify_shell_command_policy`).
   - On iteration 3 (the "recovery" turn, after the `tool_call_failed` observation has been appended), return content that is **valid JSON but artificially truncated to ~1024 tokens** — e.g. a `{"type":"tool","tool_name":"workspace_run_shell_mutate","arguments":{"command":"<long multi-line script>` with no closing braces — to simulate provider-side truncation at `max_tokens=1024`.
2. Run `run_chat_agent(config, task)` and assert it raises `RuntimeError('Model decision JSON parsing failed after 2 attempts...')`.
3. Separately, seed `context['observations']` with synthetic entries totalling ~140K estimated tokens (`_input_tokens`/`_output_tokens` in context) and confirm `_check_compaction_warning` does **not** fire until `total/200000 >= 0.6` (i.e., ~120K) — demonstrating the warning is miscalibrated for a 64K-context model.
4. Inspect `tests/test_chat_agent.py:104` and `:126` (`decision_fallback` assertions) as a starting template for a regression test asserting the new `finish_reason == 'length'` retry path is taken instead of the generic "repair JSON" retry.

## Fix priority order

1. **Fix 1** (raise `max_tokens` for decision calls + capture/act on `finish_reason`) — directly eliminates the truncated-JSON failure mode; smallest, most surgical change; unblocks users immediately regardless of model.
2. **Fix 2 / Fix 4** (wire `_model_context_limit` into `AgentRunner` construction) — prevents the same class of failure from recurring at scale for small-context models and makes existing compaction machinery actually protective for deepseek.
3. **Fix 3** (tool description rewrite) — cheapest change, reduces *how often* the model enters the failure→recovery path, compounding the benefit of Fixes 1 and 2.

## Test cases to verify each fix

**Fix 1**
- Unit test on `ModelDecisionEngine.decide`: feed a fake adapter response with `finish_reason='length'` and content that fails `parse_model_decision`; assert the engine retries with an increased `max_tokens` (or a "be more concise" instruction) rather than the generic "repair this JSON" message, and that `LLMRequest.max_tokens` passed to `adapter.complete` is `> 1024`.
- Adapter-level test: feed a raw OpenAI-style response containing `"finish_reason": "length"`; assert `LLMResponse.finish_reason == 'length'`.

**Fix 2 / Fix 4**
- Construct `_create_runner_and_engine` (or `AgentRunner` directly) with `model='deepseek-chat'` and assert `runner._max_context_tokens == 64_000` (not the 200,000 default).
- Feed `_check_compaction_warning` an accumulated `input_tokens + output_tokens` of ~40,000 with a deepseek runner and assert the warning observation is appended (it would *not* be appended at the old 200K ceiling).

**Fix 3**
- Snapshot/contains test on `registry.mcp_metadata()` (or the registered tool's `description`) asserting the `workspace_run_shell_inspect` description enumerates the allowlisted executables/subcommands, so future edits to `_INSPECT_EXECUTABLES`/`_INSPECT_GIT_SUBCOMMANDS` ([workspace_tools/_shell.py:175-178](../../teaagent/workspace_tools/_shell.py#L175-L178)) can be cross-checked against the description text (consider generating the description from the allowlist constants to keep them in sync).

**End-to-end regression**
- Reuse the reproduction harness above as an acceptance test: run the same failing 3-iteration sequence with all three fixes applied and assert the run **completes** (either by successfully retrying the tool with `workspace_run_shell_mutate`, or by surfacing a clean, actionable error rather than the opaque `RuntimeError: Model decision JSON parsing failed...`).
