# Trade-offs Analysis

Per-component analysis of the primary design tensions in TeaAgent. Each section names the trade-off, states the current resolution, and identifies the break-even condition where the resolution should change.

---

## 1. Agent Harness Core

### Safety vs. Speed
**Tension:** Approval prompts, plan-before-write checks, audit logging, and budget checks all add latency to every agent iteration.  
**Resolution:** Safety wins. Every write-mode tool call goes through `ApprovalPolicy.check()`. A 50–200ms overhead per iteration is acceptable given that agent iterations are measured in seconds.  
**Break-even:** If latency budget per iteration drops below 500ms (e.g., real-time code co-pilot), approval checks must be parallelised or pre-cleared via session-approval.

### Flexibility vs. Simplicity
**Tension:** The 5-permission-mode system (READ_ONLY → DANGER_FULL_ACCESS) provides fine-grained control but requires users to understand five distinct modes.  
**Resolution:** Default to `workspace-write` (safe default for development). Power users configure stricter or looser modes explicitly.  
**Break-even:** User research shows >20% of users misconfigure the mode → simplify to 3 modes (safe / standard / unrestricted) with clear labels.

### Vendor independence vs. Features
**Tension:** Building on stdlib means rebuilding features (connection pooling, automatic retries, API version pinning) that SDKs provide.  
**Resolution:** Accept the rebuild cost for core primitives; expose optional-dep escape hatches (`[oauth]`, `[tui]`, `[wasm]`) for feature additions.  
**Break-even:** If maintaining the urllib adapter for a provider requires >1 dev-week/quarter of catch-up work → add that provider's SDK as an optional dep.

---

## 2. Storage & Persistence

### Human-readability vs. Query Performance
**Tension:** JSONL is grep-able but cannot be queried efficiently (no indices, no JOINs).  
**Resolution:** JSONL for all append-dominant stores. GraphQLite (SQLite-backed) for graph/knowledge queries where indexed access is needed.  
**Break-even:** If audit log replay for incident analysis routinely scans >1 GB files → add a run-level SQLite index alongside the JSONL.

### Crash Safety vs. Write Throughput
**Tension:** Atomic rename (`write-temp + os.rename`) serialises all writes through a single rename. `fcntl.LOCK_EX` further serialises concurrent writers.  
**Resolution:** Correctness over throughput. A single agent run generates at most a few hundred audit events; serialised writes are not measurable.  
**Break-even:** If swarm mode with 8+ parallel subagents produces >1000 events/second → switch to per-run append files merged at completion.

### Single-node vs. Distributed State
**Tension:** JSONL + fcntl is single-node. A multi-node swarm cannot share state this way.  
**Resolution:** Single-node is the current deployment target. Federated swarm uses per-node JSONL with signature relay for cross-node votes.  
**Break-even:** If any single swarm task requires coordination across >1 physical host → PostgreSQL shared state is required.

---

## 3. Security

### Defence Depth vs. Operational Overhead
**Tension:** Every added security control (DPoP, hash-chain, mTLS, code sandbox, memory invalidation) adds operational surface (keys to manage, processes to monitor).  
**Resolution:** Defaults are maximally safe with minimum configuration. Optional controls (mTLS, encryption, multi-sig) are opt-in.  
**Break-even:** If the operator checklist for a new project takes >30 minutes → consolidate controls into a `teaagent secure-defaults` wizard.

### AST Allowlist vs. Expressiveness (Code Mode)
**Tension:** The Code Mode AST allow-list blocks useful constructs (network access, filesystem writes) to prevent malicious code execution.  
**Resolution:** Block by default; allow explicit categories via `CodeModeConfig.allowed_imports`. Untrusted code should run in Docker.  
**Break-even:** If the allow-list produces >5 false positives per week for legitimate agent-generated code → widen the allowlist category or push all code execution to Docker.

### Audit Payload Redaction vs. Debuggability
**Tension:** Redacting credentials from audit payloads prevents secret leakage but makes debugging authentication failures harder (the token that caused a 401 is not logged).  
**Resolution:** Redact unconditionally. Debugging auth failures uses the provider's dashboard or `TEAAGENT_DEBUG_AUTH=1` env flag (logs un-redacted to stderr, not to audit file).  
**Break-even:** Not a sliding scale — redaction is non-negotiable. Add structured debug modes that do not persist to audit log.

---

## 4. Multi-Agent / Swarm

### Parallelism vs. Approval Fatigue
**Tension:** Running N subagents in parallel means N approval requests may arrive simultaneously. Approving each individually defeats the productivity gain.  
**Resolution:** `CentralizedApprovalQueue` aggregates all subagent requests under the parent run ID. Operator can `approve-all` or `deny-all` in a single command.  
**Break-even:** If the approval queue UI itself becomes a bottleneck (operator spends >2 min/run approving) → introduce risk-tier auto-approval (LOW risk: auto-approve, MEDIUM+: always prompt).

### Consensus Accuracy vs. Latency
**Tension:** Unanimous consensus for CRITICAL tasks provides maximum safety but may time out if a peer is unavailable.  
**Resolution:** Configurable voting thresholds (Simple Majority/Supermajority/Unanimous) per risk tier. Default timeout: configurable, no internal default override.  
**Break-even:** If CRITICAL tasks time out >10% of the time due to peer unavailability → introduce a quorum exception pathway (supermajority + timeout = proceed with log).

### Worktree Isolation vs. Shared Context
**Tension:** Each swarm subagent runs in its own git worktree (full isolation), but agents may need shared knowledge (code index, memory catalog).  
**Resolution:** Context bus (WAL-mode SQLite) provides read-shared, write-serialised cross-worktree knowledge propagation via Delta messages.  
**Break-even:** If context bus write conflicts exceed 1% of sync operations → switch to per-worktree context snapshots merged at reconciliation.

---

## 5. LLM Abstraction

### Provider Portability vs. Provider-Specific Features
**Tension:** A unified `LLMRequest`/`LLMResponse` abstraction hides provider-specific features (Claude's thinking blocks, Gemini's grounding, OpenAI's vision inputs).  
**Resolution:** Common path through `LLMRequest`. Provider-specific extensions via `extra_params: dict` that adapters pass through without normalisation.  
**Break-even:** If >30% of production runs use Claude-specific thinking blocks → promote `thinking` to a first-class field in `LLMRequest`.

### Retry Aggression vs. Cost Control
**Tension:** Aggressive retry on rate-limit (429) and transient errors (503) improves reliability but can amplify costs if a bad prompt causes repeated expensive calls.  
**Resolution:** `LLMRetryConfig` caps retries (default: 3) and uses exponential backoff with jitter. RunBudget hard-caps total spend regardless of retry count.  
**Break-even:** If retry storms are observed (budget exhausted by retries before useful work) → add per-request cost estimation and abort retry if estimated cost exceeds remaining budget.

---

## 6. TUI & User Experience

### Rich Interactivity vs. Headless Compatibility
**Tension:** `prompt-toolkit` features (completion, split-pane, async output) require a real TTY. CI, scripted pipelines, and log-capture environments have no TTY.  
**Resolution:** All non-interactive usage goes through `teaagent run` (CLI, no TUI). TUI is `teaagent chat` only. (The `--no-tui` flag was documented but never implemented and has been removed from documentation.)  
**Break-even:** Not applicable — the split is intentional and correct. Monitor if users route interactive work through `run` to avoid TUI friction (signals UX issue in chat).

### Streaming Output vs. Clean Transcript
**Tension:** Streaming tokens interleave with the input prompt line, creating visual noise. Suppressing streaming makes the agent feel slower.  
**Resolution:** `patch_stdout()` from `prompt-toolkit` re-renders the prompt below streamed output, keeping both readable.  
**Break-even:** If users report disorientation from streaming interleave → add `--stream=false` flag that buffers the full response before displaying.
