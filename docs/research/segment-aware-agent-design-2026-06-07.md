# Segment-Aware Agent Architecture: Implementation Design

**Status:** Design proposal — not yet implemented
**Author:** Design session, 2026-06-07
**Scope:** How teaAgent would automatically detect, chunk, and process tasks whose
input/output exceeds a model's context window, with the user kept in the loop at
every irreversible decision point.

**Why this matters:** Today, `ContextPressureScore` (`teaagent/context_pressure.py`)
and `TokenBudgetReport` (`teaagent/daily.py`) can *measure* context pressure on the
*workspace* (memory catalog, pinned files, recent runs), and `compute_context_health`
(`teaagent/context_health.py`) can *score* the health of an active session. But
neither pipeline acts on a single oversized **task input** — e.g. "summarize this
50MB log file" — before the agent attempts it, fails mid-stream, or silently
truncates. This document designs the missing layer: a pre-flight analyzer that
estimates whether a task will overflow, proposes remediation options to the user
(mirroring the existing JIT-approval UX in `approval_backend.py`), and — if the
user opts in — chunks the input, processes segments with carried-over context, and
aggregates results back into a single coherent answer.

---

## Section 1: User Experience Flow

### 1.1 The golden path

The defining UX principle is: **never silently truncate, never silently fail, and
never block on a decision the user didn't ask to make.** Today, if a task's input
exceeds the model's context window, the failure mode is one of: (a) the provider
SDK throws an HTTP 400 mid-run, (b) `CompactionManager` aggressively drops history
the user cared about, or (c) the agent quietly hands the model a truncated blob and
produces a confidently wrong answer. None of these give the user a chance to make
an informed call before tokens (and money) are spent.

The proposed flow intercepts *before* the first model call:

```
User: "Analyze this 50MB log file and summarize the errors"

  [ContextAnalyzer runs synchronously, <200ms — no model call yet]
  [Result: 2.1M estimated input tokens; deepseek-chat context limit 64K]
  [ContextPressureScore.usage_level would read "critical"; overflow_risk = 97%]

System:
  ┌─────────────────────────────────────────────────────────────┐
  │  ⚠ This task is ~2.1M tokens — about 33× your model's       │
  │  64K context window (deepseek-chat).                        │
  │                                                              │
  │  I can:                                                      │
  │    1. Chunk it automatically (≈30 segments, semantic-aware) │
  │       and aggregate the results — recommended               │
  │    2. Sample representative sections instead of the whole   │
  │       file (faster, less complete)                          │
  │    3. Stop here so you can pick a smaller scope yourself    │
  │                                                              │
  │  Choose 1, 2, or 3 (or describe what you'd like instead):   │
  └─────────────────────────────────────────────────────────────┘

User: 1

System: "Chunking with semantic awareness (line-oriented log chunker,
         ~70K tokens/segment, 30 segments). Processing 1/30…"

  [progress bar / streaming status, one line per segment, in the TUI]

  "✓ 1/30  ✓ 2/30  ⚠ 5/30 (retried, smaller chunk)  ✓ 6/30 …"

System: "Done. Aggregated 30 segments into one report (≈4,200 tokens).
         2 segments were retried with smaller chunks; all completed.
         Estimated extra cost from chunking overhead: ~22% more tokens
         than a single-shot run would have used (had it fit)."

  [Full aggregated answer follows, with a collapsible "segment log" the
   user can expand to audit which chunk produced which finding.]
```

### 1.2 Why a *proposal*, not a silent decision

This mirrors a pattern teaAgent already has baked into its trust model: the
`ApprovalBackend` hierarchy (`teaagent/approval_backend.py`) never lets the agent
silently take a destructive or expensive action — `PromptBackend` routes
destructive tool calls to JIT approval (`reason_code='jit_required'`), and even
`allow_all_destructive` is *not* sufficient to bypass the gate outside of
`danger-full-access` mode (P0-TR-001). Chunking is the same class of decision: it
changes cost, latency, and — critically — **result fidelity** (a chunked summary is
not equivalent to a single-shot summary; it can miss cross-chunk patterns). The user
must consent to that trade-off the same way they consent to a destructive file write.

The trigger threshold (proposal appears when `overflow_risk > 60%`) is deliberately
conservative-but-not-paranoid: below 60%, normal compaction (`CompactionManager`,
already wired into `build_token_budget_report`) can usually absorb the overage
without changing the *meaning* of the task. Above 60%, compaction alone would have
to discard so much of the input that the task's semantics would silently change —
that's the point where the user needs to be told.

### 1.3 What the user sees if they decline

Selecting option 3 (or typing a free-form alternative) must degrade gracefully —
this is `test_user_rejection_falls_back_to_simple_error()` in the test plan below.
The agent does **not** then attempt the oversized task anyway; it returns a clear,
actionable message:

```
System: "Understood — I won't process the full file. To proceed without
         chunking, you could: point me at a specific time range, grep
         for the error patterns first and hand me just the matches, or
         split the file yourself and I can run on each part. Let me
         know how you'd like to scope it."
```

### 1.4 Mid-run cancellation

Because chunked processing can run for minutes, the existing cancel-token
infrastructure (`tests/integration/test_cancel_token.py`,
`teaagent/tool_call_context.py`) must be wired into `SegmentProcessor` so that a
user-initiated cancel stops *between* segments (never mid-segment, to avoid
partial/corrupt aggregation state) and returns whatever has been aggregated so far,
clearly marked as partial:

```
User: [Ctrl-C]
System: "Stopped after 14/30 segments. Here's the partial summary —
         it covers roughly the first 47% of the file by token volume."
```

---

## Section 2: Architecture Components

The design favors small, independently-testable modules over one monolithic
"chunking engine," following the existing pattern of composable scorecards
(`ContextPressureScore`, `ContextHealthScore`, `TokenBudgetReport`) that are each a
plain dataclass with a `to_dict()` and a pure compute function. Every new component
below follows that shape: a dataclass result type + a pure(-ish) function that
produces it, so each is unit-testable without spinning up a model or a TUI.

```
ContextAnalyzer                                   (teaagent/context_analyzer.py — new)
├─ estimate_tokens(task_input: str | Path) -> int
│     Reuses the tokenizer/heuristic already backing
│     build_token_budget_report's estimated_input_tokens — no new
│     tokenization logic; this is a thin reframe of an existing estimator
│     applied to a *task payload* rather than the *workspace*.
├─ estimate_response_tokens(task: TaskSpec) -> int
│     Heuristic from output_reserve_tokens (ContextProfile) scaled by
│     task type (summarize ≈ 5% of input; transform ≈ 80-120% of input;
│     extract ≈ 10-30%). Conservative (over-)estimate by design — false
│     positives (proposing chunking when it wasn't needed) are cheap;
│     false negatives (mid-run overflow) are expensive.
└─ detect_overflow(input_tokens, output_tokens, model_limit) -> OverflowRisk
      OverflowRisk { ratio: float, level: "none"|"watch"|"propose"|"critical",
                     headroom_tokens: int }
      Mirrors the level taxonomy already used by ContextPressureScore.usage_level
      and ContextHealthScore, so the TUI can render it with the same widget.

ChunkingProposal                                  (teaagent/chunking_proposal.py — new)
├─ build_options(risk: OverflowRisk, format: FormatType) -> list[ProposalOption]
│     Always offers "stop and let me rescope" as the last option — this
│     is the fallback path tested by test_user_rejection_falls_back_to_simple_error.
├─ present(options) -> UserChoice
│     NOT a new prompting mechanism — delegates to the same
│     ApprovalBackend / PromptBackend JIT-prompt channel that destructive
│     tool calls already use, so it shows up consistently in TUI, headless,
│     and scripted modes (and respects --permission-mode the same way).
└─ log_decision(choice: UserChoice) -> DecisionAuditRecord
      Persisted via RunStore (teaagent/run_store.py) alongside the run,
      same audit trail that approval decisions already get — no new
      storage layer.

FormatDetector                                    (teaagent/format_detector.py — new)
├─ detect_format(input) -> FormatType   # json | csv | code | text | xml | yaml | binary
│     Cheap, sniff-based (file extension + first-N-bytes heuristic +
│     fallback to a lightweight content classifier). Must be fast — this
│     runs before any proposal, so it can't itself become a context cost.
└─ select_chunker(format_type) -> Chunker
      Pure dispatch into ChunkerRegistry; "binary" and unknown formats
      route to a degraded TextChunker with a stated caveat, never to a
      crash.

ChunkerRegistry                                   (teaagent/chunkers/ — new package)
├─ JSONChunker     — split by top-level array elements, preserve sibling keys
├─ CSVChunker      — split by row ranges, repeat header in every chunk
├─ CodeChunker     — split on function/class boundaries, repeat imports
├─ TextChunker     — split on paragraph/section boundaries
└─ XMLChunker      — split by repeating sibling elements, preserve ancestor path
      All five implement one Protocol:
        chunk(content, target_tokens) -> list[Segment]
      Segment { content: str, index: int, total: int,
                structural_path: str, carryover_hint: str | None }
      New chunkers register themselves via entry points — same plugin
      shape as existing tool registration, so this list can grow without
      touching the dispatcher (addresses the Section 6 "complexity risk").

SegmentProcessor                                  (teaagent/segment_processor.py — new)
├─ process_segment(segment, task, prior_summary) -> SegmentResult
│     One model call per segment. prior_summary is the compressed
│     carryover (Section 3.3) — never the raw prior segments.
├─ track_progress(i, total) -> ProgressEvent
│     Emits the same event shape the TUI already consumes for streaming
│     tool-call progress (teaagent/context_bus.py) — no new UI plumbing.
└─ handle_segment_failure(error, segment) -> RetryDecision
      RetryDecision { action: "retry_smaller" | "skip" | "abort",
                      next_chunk_size: int | None }
      Implements the escalation ladder in Section 3.4. Wired to the
      existing cancel-token (tool_call_context.py) so a user cancel
      during retry doesn't spin forever.

ResultAggregator                                  (teaagent/result_aggregator.py — new)
├─ aggregate_results(results: list[SegmentResult]) -> AggregatedResult
│     Format-aware: JSON segment results get structurally merged (not
│     concatenated); text/summary results get a final reduce pass
│     through the model ("here are N partial summaries, produce one
│     coherent summary, noting any contradictions").
├─ validate_consistency(results) -> ConsistencyScore
│     Cheap heuristic checks first (e.g., do JSON segment outputs share
│     a schema? do numeric totals roughly add up?); flags — but does not
│     block on — apparent contradictions between segments, surfacing
│     them to the user rather than silently picking one.
└─ report_strategy(strategy) -> str
      Plain-language explanation appended to the final answer — this is
      the "Aggregated 30 segments… 2 retried…" line in Section 1.1,
      not a hidden implementation detail.
```

### 2.1 Where this plugs into the existing run loop

`ContextAnalyzer.detect_overflow` is invoked once, synchronously, immediately after
intent clarification and before the first tool/model call — the same point where
`compute_context_pressure` already runs to decide whether to warn about workspace
bloat. If overflow is detected above the propose threshold, `ChunkingProposal`
intercepts the run *before* `RunContext` (`teaagent/run_context.py`) is created for
the "normal" single-shot path; if the user opts into chunking, a
`ChunkedRunContext` (a thin wrapper that fans out to N child `RunContext`s, one per
segment, each independently auditable) takes over. This keeps the blast radius of
the new feature contained: a non-overflowing task never touches any of these new
modules, and `RunContext`'s existing contract is unchanged.

---

## Section 3: Key Design Decisions

### 3.1 Chunk size strategy

**Decision:** target chunk size = 50% of (model_context_limit − output_reserve −
carryover_estimate), recomputed per segment from the *live* `ContextProfile`
(`teaagent/daily.py`) rather than a static constant.

**Rationale:** A fixed chunk size (e.g., "always 8K tokens") either wastes headroom
on large-context models (Claude/GPT-4-class, 128K–1M) or overflows on small-context
local models (many Ollama/vLLM deployments sit at 4K–32K). Pegging to a *fraction*
of the actual configured limit means the same chunker produces sensible chunk counts
whether the user is running `deepseek-chat` at 64K or a local 8K model — no
per-model tuning tables to maintain. The 50% figure leaves room for: the model's own
reasoning/scratch-space, the `output_reserve_tokens` already defined per
`ContextProfile` (512/1024/2048 across lean/balanced/deep), and the carryover
summary (Section 3.3). Chunk size is *recomputed*, not fixed, because carryover
grows slightly each segment — segment 30 needs a smaller content budget than segment
1 to leave room for a longer accumulated summary.

**Alternative considered — fixed chunk size:** Rejected. It would require either a
lookup table keyed on model+provider (a maintenance burden that fights teaAgent's
existing provider-agnostic design in `teaagent/llm_adapters` — ✱ name approximate)
or a single conservative constant that wastes 90%+ of headroom on large-context
models, multiplying segment count (and therefore cost and latency) for no benefit.

### 3.2 Semantic awareness in chunking

**Decision:** every chunker in `ChunkerRegistry` must guarantee it never splits a
*structural unit* the format defines as atomic:

| Format | Atomic unit | Never split mid-… |
|---|---|---|
| JSON | array element / object | …an object's key-value pairs |
| CSV | row | …a row (but headers repeat per chunk) |
| Code | function / class | …a function body (imports repeat per chunk) |
| Text | paragraph (fallback: sentence) | …a sentence |
| XML | sibling element | …an element's open/close tag pair |

If a single atomic unit is *itself* larger than the target chunk size (a 200KB
minified JS function, a single 50K-token JSON object), the chunker falls back to a
documented degraded mode — split at the nearest safe boundary it can find (e.g.
top-level statements inside the function) — and tags that segment's
`carryover_hint` with a warning that gets surfaced in the final aggregation report.
This is a deliberate "never silently lie about what you did" choice: a degraded
split is allowed, but it must be visible.

**Trade-off — complexity vs. accuracy:** A naive byte-offset chunker is ~20 lines
and format-agnostic; the structural chunkers above are each 100–300 lines and
format-specific. The complexity is justified because naive chunking on structured
data doesn't just lose *some* accuracy — it can produce outright invalid
sub-documents (an unclosed JSON object, half a CSV row) that cause the *segment's*
model call to fail outright, which is strictly worse than not chunking. The cost is
paid once, in the chunker implementation; every task that flows through it benefits.

### 3.3 Context carryover

**Decision:** each segment's prompt includes (a) the original task description, (b)
a *compressed* running summary of prior segments' findings — not their raw
content — and (c) the current segment.

**Why compressed, not raw:** Carrying forward raw prior segments would make the
"chunking" pointless — by segment 10, the prompt would again exceed the context
window. The carryover must itself stay within a fixed token budget (suggested: 10%
of the per-segment content budget, so it never crowds out new content). This is
produced by `SegmentProcessor` asking the model, as part of each segment's response,
to also emit a short "what should the next segment know" note — a technique already
informally similar to how `CompactionManager` produces rolling summaries for context
auto-compaction (`tests/test_context_auto_compaction.py`).

**Cost:** ~10% extra tokens per segment for carryover generation +
transmission — the "+20-30% overhead" figure cited to the user in Section 1.1
combines this with the structural repetition cost (repeated headers/imports/schema
from Section 3.2). Both costs are disclosed up front in the proposal (Section 1,
option 1's description) and again in the final report — never hidden in a bill the
user sees only after the fact.

### 3.4 Failure handling — the retry/skip/abort ladder

**Decision:** a three-rung escalation, never a silent retry loop:

1. **Retry with a smaller chunk.** If segment N fails (timeout, provider 4xx/5xx,
   malformed structural split), `handle_segment_failure` halves the *content*
   portion of that segment's budget and re-chunks just that region — not the whole
   document — then retries once.
2. **Skip + warn.** If the retry also fails, the segment is skipped, and a
   structured warning (`"Segment 5/30 skipped (timeout). Results may be
   incomplete."`) is attached to that segment's slot in the aggregation — visible in
   both the live progress stream and the final report's "segment log."
3. **Abort the run.** If skip-rate crosses a threshold (suggested: >20% of segments,
   or any *consecutive* run of 3+ skips suggesting a systemic problem rather than
   transient noise), the processor stops and surfaces the pattern to the user rather
   than producing a report that's silently 60% holes: `"6 of the last 8 segments
   failed — this looks like a systemic issue (possibly provider rate-limiting).
   Stopping here; want me to retry from segment 23, or pause?"`

This ladder is deliberately visible at every rung — "skip" is not a quiet
`continue`, it's a recorded, user-facing event, satisfying
`test_failure_skip_adds_warning()`.

### 3.5 User proposal logic — trigger and timing

**Decision:** `overflow_risk > 60%` triggers the proposal; it is computed and shown
**before** any model call for the task itself (estimation is local/heuristic, no
network round-trip), and it accepts free-form replacement input, not just option
numbers — `present()` parses "1", "option 1", "chunk it", or an entirely different
instruction ("just look at the last 1000 lines") via the same intent-clarification
layer teaAgent already uses for ambiguous user requests.

**Why 60%, not 80% or 100%:** Headroom matters. At 60% estimated usage, normal
compaction can usually still absorb estimation error (the heuristic
`estimate_tokens` is necessarily approximate — actual tokenization varies by
provider and model). Waiting until 100% means the proposal sometimes arrives *after*
a failed attempt has already burned tokens and time. 60% is conservative enough to
catch the cases that matter while staying well clear of "annoyingly trigger-happy on
borderline tasks" — this exact number should be revisited once real usage data
exists (tracked as a tunable, not a hardcoded literal, exposed via
`ContextProfile`-style configuration).

---

## Section 4: Format-Specific Chunking

Each chunker below follows the shared `Chunker` protocol
(`chunk(content, target_tokens) -> list[Segment]`) and the atomicity guarantees from
Section 3.2. Pseudocode is illustrative, not final implementation.

### 4.1 JSON chunking

**Strategy:** Identify the dominant top-level array (heuristically, the largest by
serialized size — usually the "data" the user cares about); split that array into
element groups sized to fit the token budget; replicate every *sibling* key
(metadata, schema, config) into each chunk so every segment is independently valid
JSON the model can reason about without the others.

```
Input:  {"users": [u1, u2, u3, ... u10000], "metadata": {"version": "2.1", ...}}

Strategy: split `users` into groups; carry `metadata` into every chunk

Chunk 1: {"users": [u1, ..., u333], "metadata": {"version": "2.1", ...},
          "_segment": {"index": 1, "total": 30, "covers": "users[0:333]"}}
Chunk 2: {"users": [u334, ..., u666], "metadata": {"version": "2.1", ...},
          "_segment": {"index": 2, "total": 30, "covers": "users[334:666]"}}
...
```

```python
def chunk_json(content: dict, target_tokens: int) -> list[Segment]:
    array_key, array = _find_dominant_array(content)       # e.g. "users"
    sibling_keys = {k: v for k, v in content.items() if k != array_key}
    groups = _group_by_token_budget(array, target_tokens,
                                     reserve=_estimate_tokens(sibling_keys))
    return [
        Segment(
            content={array_key: group, **sibling_keys,
                     "_segment": {"index": i + 1, "total": len(groups),
                                  "covers": f"{array_key}[{start}:{end}]"}},
            index=i + 1, total=len(groups),
            structural_path=f"$.{array_key}[{start}:{end}]",
            carryover_hint=None,
        )
        for i, (group, start, end) in enumerate(groups)
    ]
```

The `_segment` envelope is injected, not inferred — it tells the model exactly what
slice of the whole it's looking at, which materially improves both per-segment
accuracy and `ResultAggregator`'s ability to structurally merge (sort/dedupe/concat
by known index ranges, rather than guess at overlap).

### 4.2 CSV chunking

**Strategy:** Parse the header once; split data rows into ranges; prepend the header
to every chunk so each segment is independently valid, parseable CSV.

```
Input:  header row + 1,000,000 data rows

Chunk 1: header + rows[0:10000]      (annotated: "rows 1–10,000 of 1,000,000")
Chunk 2: header + rows[10000:20000]  (annotated: "rows 10,001–20,000 of 1,000,000")
...
```

```python
def chunk_csv(content: str, target_tokens: int) -> list[Segment]:
    header, rows = _split_header(content)
    header_tokens = _estimate_tokens(header)
    rows_per_chunk = max(1, (target_tokens - header_tokens) // _avg_row_tokens(rows))
    groups = list(_batched(rows, rows_per_chunk))
    return [
        Segment(
            content=header + "\n" + "\n".join(group),
            index=i + 1, total=len(groups),
            structural_path=f"rows[{i*rows_per_chunk}:{i*rows_per_chunk+len(group)}]",
            carryover_hint=f"Rows {i*rows_per_chunk+1}-"
                           f"{i*rows_per_chunk+len(group)} of {len(rows)} total",
        )
        for i, group in enumerate(groups)
    ]
```

Row-count-per-chunk is derived from *measured* average row size
(`_avg_row_tokens`), not assumed uniform — log files and exports often have highly
variable row lengths (a stack-trace line vs. a one-word status line), and a
fixed-row-count chunker would wildly over- or under-fill the budget depending on
which rows happen to land in which chunk.

### 4.3 Code chunking

**Strategy:** Parse into a lightweight AST/symbol table (teaAgent likely already has
LSP-adjacent tooling — see `teaagent/context_pack.py` and the LSP integration
referenced in prior benchmarking notes — reuse that rather than writing a new
parser); group functions/classes by *call-graph adjacency* (functions that call each
other land in the same chunk wherever possible) so a single segment's model call has
the best chance of seeing a coherent unit of behavior; always repeat the file's
import/`using`/`require` block at the top of every chunk.

```
Input: module.py with 50 functions, where helpers() is called by
       process_a(), process_b(), and validate()

Strategy: cluster by call-graph adjacency, not file order

Chunk 1: imports + [helpers, process_a, process_b, validate]   (cohesive cluster)
Chunk 2: imports + [parse_config, load_settings, ...]          (separate cluster)
...
```

```python
def chunk_code(content: str, target_tokens: int) -> list[Segment]:
    symbols = _parse_symbols(content)          # via existing LSP/AST integration
    imports = _extract_imports(content)
    clusters = _cluster_by_call_graph(symbols, target_tokens,
                                        reserve=_estimate_tokens(imports))
    return [
        Segment(
            content=imports + "\n\n" + "\n\n".join(s.source for s in cluster),
            index=i + 1, total=len(clusters),
            structural_path=f"functions: {[s.name for s in cluster]}",
            carryover_hint=f"Cluster {i+1}: {', '.join(s.name for s in cluster)}",
        )
        for i, cluster in enumerate(clusters)
    ]
```

**Why call-graph clusters over file-order chunks:** A model analyzing
`process_a()` *needs* to see `helpers()` to reason correctly about it; splitting
them into different segments forces the model to either guess at `helpers()`'s
behavior or flag it as "defined elsewhere, cannot verify" — both worse outcomes than
spending slightly more effort on the clustering pass up front. This is the code
analogue of "never split a function mid-body": don't split *coupled* functions
either, when you can avoid it.

### 4.4 Text chunking

**Strategy:** Split on paragraph boundaries (blank-line-delimited); if a single
paragraph exceeds the chunk budget (rare — long-form prose, transcripts), fall back
to sentence-boundary splitting within that paragraph, flagged via `carryover_hint`.

```python
def chunk_text(content: str, target_tokens: int) -> list[Segment]:
    paragraphs = content.split("\n\n")
    groups, current, current_tokens = [], [], 0
    for p in paragraphs:
        p_tokens = _estimate_tokens(p)
        if p_tokens > target_tokens:                      # oversized paragraph
            if current:
                groups.append(current); current, current_tokens = [], 0
            groups.extend(_split_oversized_paragraph(p, target_tokens))
            continue
        if current_tokens + p_tokens > target_tokens:
            groups.append(current); current, current_tokens = [], 0
        current.append(p); current_tokens += p_tokens
    if current:
        groups.append(current)
    return [_to_segment(g, i, len(groups)) for i, g in enumerate(groups)]
```

### 4.5 XML chunking

**Strategy:** Identify the dominant repeating sibling element (analogous to JSON's
"dominant array"); split on element boundaries; carry the ancestor path (and any
non-repeating siblings, e.g. a `<header>` block) into every chunk so each segment
remains well-formed, parseable XML.

```
Input: <catalog><header>...</header>
         <item id="1">...</item> ... <item id="50000">...</item>
       </catalog>

Chunk 1: <catalog><header>...</header><item id="1">...</item>...
                  <item id="1666">...</item></catalog>
Chunk 2: <catalog><header>...</header><item id="1667">...</item>...
                  </catalog>
```

```python
def chunk_xml(content: str, target_tokens: int) -> list[Segment]:
    tree = _parse(content)
    repeating_tag, elements, ancestor_path = _find_dominant_repeating_element(tree)
    non_repeating = _siblings_excluding(tree, repeating_tag)
    groups = _group_by_token_budget(elements, target_tokens,
                                      reserve=_estimate_tokens(non_repeating))
    return [
        Segment(
            content=_wrap_in_ancestor_path(ancestor_path, non_repeating, group),
            index=i + 1, total=len(groups),
            structural_path=f"{ancestor_path}/{repeating_tag}[{start}:{end}]",
            carryover_hint=None,
        )
        for i, (group, start, end) in enumerate(groups)
    ]
```

---

## Section 5: Testing Strategy

Each test below is independently runnable without a live model — `SegmentProcessor`
and `ChunkingProposal` are designed around injectable fakes (mirroring the existing
`fake` provider pattern referenced in `teaagent/cost` and the ACP fake-registry
tests), so the chunking *logic* is fully testable in isolation from LLM calls.

| # | Test | What it proves | Notes on approach |
|---|---|---|---|
| 1 | `test_context_analyzer_detects_overflow()` | Token estimation + overflow classification is correct for known input/limit pairs | Table-driven: feed `(input_size, model_limit, expected_level)` tuples spanning none/watch/propose/critical boundaries, including off-by-one cases at the 60% threshold |
| 2 | `test_chunking_proposal_appears_at_60_percent()` | The proposal trigger fires exactly at the documented threshold, not earlier/later | Parametrize across 59%/60%/61% estimated usage; assert proposal absent/present/present |
| 3 | `test_json_chunker_preserves_structure()` | No chunk is invalid JSON; sibling keys appear in every chunk; array elements are never split mid-object | Round-trip: `json.loads()` every chunk; assert union of array elements across chunks == original array, no duplicates, no omissions |
| 4 | `test_code_chunker_preserves_imports()` | Every chunk's import block matches the source file's; no function body spans a chunk boundary | Parse each chunk back with the same symbol parser; assert each function appears whole in exactly one chunk |
| 5 | `test_segment_processor_maintains_context()` | The carryover summary from segment N appears in segment N+1's prompt, and stays within its token budget | Use a fake LLM adapter that echoes its prompt back; assert prior-segment markers are present and total carryover tokens ≤ budget across all N segments |
| 6 | `test_result_aggregator_merges_json()` | Structural merge produces valid, deduplicated, correctly-ordered output from segment results that carry `_segment` envelopes | Feed synthetic out-of-order segment results; assert final merge re-sorts by `covers` range and contains no duplicate elements |
| 7 | `test_failure_skip_adds_warning()` | A skipped segment produces a visible, structured warning attached to the final report — not a silent gap | Inject a fake adapter that fails segment 5 twice; assert the aggregated result's segment log contains an entry with `status="skipped"` and the exact user-facing warning string |
| 8 | `test_user_rejection_falls_back_to_simple_error()` | Declining the proposal produces a helpful rescoping message, and the agent does **not** then attempt the oversized task anyway | Simulate a "3" / "no" response; assert no segment-processing calls occur and the returned message offers concrete rescoping suggestions |

Additional tests worth adding once the above are green (not blocking initial
implementation, but flagged so they aren't forgotten):

- `test_abort_on_systemic_failure_pattern()` — the third rung of the retry ladder
  (Section 3.4) fires on the consecutive-skip pattern, not just the aggregate
  threshold.
- `test_cancel_mid_chunk_run_returns_partial()` — wiring the existing cancel-token
  (`tests/integration/test_cancel_token.py`) into `SegmentProcessor` actually stops
  *between* segments and returns a clearly-marked partial result.
- `test_oversized_atomic_unit_degrades_visibly()` — the Section 3.2 fallback path
  (a single function/object too large to fit a chunk) produces a *visible* warning,
  not a silent best-effort split.

---

## Section 6: Risk Analysis

### 6.1 Accuracy risk — does chunking lose semantic meaning?

**The risk:** Any chunking strategy is, definitionally, showing the model less than
the whole picture per call. Cross-chunk patterns (a bug whose cause is in chunk 3
and whose symptom is in chunk 27; a CSV column whose running total only makes sense
across all rows) can be missed entirely, and the final answer may *look* complete
while quietly omitting exactly the insight the user was looking for.

**Mitigation:**
- **Context carryover** (Section 3.3) directly targets this — each segment knows
  what came before, so patterns *can* be tracked forward, though not perfectly.
- **`validate_consistency`** runs lightweight cross-segment checks (schema
  agreement, rough numeric reconciliation) and surfaces — rather than hides —
  apparent contradictions.
- **Disclosure, not false confidence:** the final report explicitly states that the
  answer was produced by chunked analysis (Section 1.1's "Aggregated 30 segments…"
  line), so the user can calibrate their trust accordingly — this is a known
  limitation that must be *visible*, not a hidden caveat in documentation nobody
  reads.
- **Residual risk accepted:** No amount of carryover fully replaces single-shot
  analysis with a sufficiently large context window. This is disclosed as a
  trade-off in the *initial proposal* (Section 1.1, option 1's description should
  arguably be even more explicit: "may miss patterns that span widely-separated
  parts of the input") — the user consents to this trade-off, they aren't surprised
  by it after the fact.

### 6.2 Cost risk — does chunking increase total tokens spent?

**The risk:** Yes, unavoidably — repeated structural overhead (headers, imports,
schema, ancestor paths) plus carryover summaries multiply token spend relative to a
hypothetical single-shot run.

**Estimation:** ~20–30% overhead, combining:
- ~10% from carryover generation and transmission (Section 3.3)
- ~10–20% from format-specific structural repetition (Section 3.2's "always
  repeat headers/imports/schema" guarantee) — the exact figure depends heavily on
  format (CSV with a tiny header repeats cheaply; JSON with large sibling metadata
  repeats expensively, which is itself a signal that `_find_dominant_array` chose
  poorly and the chunker should reconsider what counts as "metadata" vs. "data")

**Mitigation:**
- **Compression strategies for carryover** — summarize, don't replay; cap carryover
  at a fixed fraction of the per-segment budget (Section 3.3) so it can never grow
  unboundedly across 30+ segments.
- **Cost transparency up front** — the proposal (Section 1.1) states the overhead
  estimate *before* the user commits, using teaAgent's existing cost-estimation
  machinery (the same family of code that produces `TokenBudgetReport` and
  presumably feeds the cost-rate work referenced in recent fixes around
  ollama/vllm/fake default cost rates) so the number shown is consistent with
  whatever cost dashboard the user already trusts.
- **Residual risk accepted:** for genuinely huge inputs (the 2.1M-token example),
  even a 30% overhead on a task that wouldn't otherwise be possible at all is a
  reasonable trade — the alternative isn't "cheaper," it's "impossible."

### 6.3 UX risk — does automatic proposal overwhelm users?

**The risk:** A system that pops up a multi-option dialog every time a task brushes
against a context limit could feel naggy, slow down simple workflows, or train users
to reflexively click through without reading (the same "approval fatigue" problem
that plagues poorly-tuned destructive-action confirmations).

**Mitigation:**
- **Threshold tuning** (the 60% trigger, Section 3.5) is explicitly framed as a
  *starting point to be revisited with real usage data* — if telemetry shows the
  proposal fires too often on tasks that would have succeeded fine, the threshold
  moves up.
- **Clear, short, three-option framing** with a stated recommendation (option 1
  marked "— recommended") respects the user's time — they can accept the default
  with a single keystroke, exactly like JIT approval prompts already do for
  low-stakes tool calls.
- **Free-form override** (Section 3.5) means power users who already know what they
  want never have to navigate a menu — they just say what they want and the system
  routes it through the same intent-clarification layer as any other instruction.
- **Residual risk accepted:** some friction is the *point* — this is a decision
  that changes result fidelity and cost, and teaAgent's whole trust model
  (governance-first positioning, per recent strategic-assessment notes) is built on
  *not* hiding consequential decisions behind silent defaults. A small amount of
  "naggy" is the cost of "the agent never surprises you with a bill or a degraded
  answer you didn't agree to."

### 6.4 Complexity risk — is this too complex to maintain?

**The risk:** Five format-specific chunkers, a multi-rung retry ladder, a
proposal/consent flow, and a structurally-aware aggregator is a *lot* of new
surface area — and every new format (Parquet? protobuf? log-specific formats with
their own grammars?) is another chunker to write and maintain.

**Mitigation:**
- **Plugin architecture** (Section 2, `ChunkerRegistry`) — chunkers register via
  entry points exactly the way teaAgent already registers tools; adding format #6
  never requires touching the dispatcher, the proposal flow, or the aggregator's
  core logic.
- **Shared protocol, isolated implementations** — every chunker implements one
  `chunk(content, target_tokens) -> list[Segment]` contract; bugs in the CSV
  chunker cannot leak into the JSON chunker's behavior, and each is independently
  unit-testable (Section 5, tests #3–#4 demonstrate the pattern that scales to new
  formats).
- **Graceful degradation as the universal fallback** — `FormatDetector` routes
  anything it doesn't recognize to `TextChunker` with a stated caveat (Section 2),
  so "we haven't written a chunker for format X yet" degrades to "works, with a
  disclosed accuracy trade-off" rather than "crashes" or "silently mishandles."
- **Residual risk accepted:** this is genuinely more code than a "just truncate and
  hope" approach. The complexity is the cost of the accuracy and trust guarantees
  in Sections 6.1 and 6.3 — and it is *contained* (Section 2.1: a non-overflowing
  task never touches any of it), so the maintenance burden scales with how often the
  feature is actually exercised, not with the size of the codebase as a whole.

---

## Appendix: Open questions for implementation review

1. **Token estimator reuse** — confirm `estimate_tokens` can cleanly wrap whatever
   estimator backs `build_token_budget_report`'s `estimated_input_tokens` today
   (tokenizer-exact vs. heuristic — the design assumes "good enough, fast,
   conservative," not provider-exact tokenization).
2. **Threshold configurability** — should the 60% propose-trigger and the 50%
   chunk-size-fraction live in `ContextProfile` (per-profile tuning) or be global
   constants with a single override point? Leaning toward the former, for
   consistency with how `output_reserve_tokens` already varies by profile.
3. **Aggregation reduce-pass cost** — `ResultAggregator`'s final reduce pass for
   text/summary results is itself a model call against N partial summaries; for
   very large N (100+ segments) this reduce input could itself approach overflow,
   suggesting a recursive/tree-reduce design may eventually be needed. Flagged as a
   v2 concern, not a v1 blocker — 30-segment runs are comfortably within a
   single reduce pass.
4. **LSP integration point for `CodeChunker`** — confirm whether
   `teaagent/context_pack.py`'s existing LSP hydration path exposes a symbol
   table/call-graph primitive that `_cluster_by_call_graph` can build on directly,
   or whether a narrower AST-only utility needs to be added.
