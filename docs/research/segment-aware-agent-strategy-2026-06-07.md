# Segment-Aware Agents: How Should TeaAgent Propose Chunking When It Hits Context Limits?

**Status:** Research document (literature review + competitor audit + design proposal)
**Date:** 2026-06-07
**Trigger:** The teaAgent JSON-truncation bug (see `docs/debugging/json-parsing-bug-diagnosis-2026-06-07.md`) exposed that the agent has no mechanism for *proactively* recognizing "this input/output is too large for one pass" and proposing a way through it. This document asks: what would a principled, segment-aware agent design look like, and what can we learn from the literature, the competition, and the developer community before building one?

**A note on evidentiary standard.** Every external claim below is backed by a URL that was actually fetched and read during this research pass (not guessed from memory, and not generated). Where a requested category of evidence — Discord servers, Twitter/X, Reddit — could not be retrieved with the tools available, that gap is stated explicitly rather than papered over with invented quotes. This matters more than hitting a page-count target: a research document that cites sources nobody can verify is worse than no document at all.

---

## Part 1 — Problem Statement

### 1.1 What actually happened

The JSON-truncation bug (documented separately in `docs/debugging/json-parsing-bug-diagnosis-2026-06-07.md`) is a specific instance of a general failure mode: the agent produced or consumed a JSON payload that exceeded the usable token budget, the payload was cut mid-structure, and the downstream parser broke. The *proximate* fix is a parsing/robustness fix. The *systemic* observation is the one worth dwelling on: nothing upstream of the parser ever asked "is this going to fit?"

### 1.2 The three postures an agent can take toward oversized work

1. **Naive.** Raise `max_tokens`, increase the context window, hope the response fits. This is not a strategy so much as a deferral — it pushes the failure further down the token axis without changing its shape. RULER (Hsieh et al., 2024, §2.2 below) is the sharpest evidence that this doesn't even buy what people think it buys: models that *advertise* 32K+ context often can't *use* it reliably.
2. **Reactive.** Let the provider or the runtime detect overflow, surface an error, and make the human retry with a smaller ask. This is what Aider does today by its own admission ("Aider never enforces token limits, it only reports token limit errors from the API provider" — `aider.chat/docs/troubleshooting/token-limits.html`). It is honest, but it puts the cognitive burden of decomposition entirely on the user, every single time.
3. **Proactive.** Estimate the size of the task *before* committing to it, recognize when it crosses a threshold, and offer the user a concrete plan for breaking it into pieces — "this is 137K tokens; want me to split it into 5 chunks, process each, and combine the results?" This is the posture this document is examining, because it is the one most agent frameworks (including teaAgent, today) do not take.

### 1.3 Why this is worth solving deliberately rather than patching reactively

Two independent bodies of evidence converge on the same point: bigger context windows are not a substitute for deliberate decomposition.

- **Positional degradation.** Liu et al.'s "Lost in the Middle" (TACL 2024; arXiv:2307.03172) found a U-shaped performance curve — models do best when relevant information sits at the very start or end of the context and measurably worse when it's buried in the middle, *even in models built for long contexts*. Stuffing more into the window doesn't just risk truncation; it actively degrades the quality of what the model does with the parts that *do* fit.
- **Advertised vs. usable context.** NVIDIA's RULER benchmark (Hsieh et al., 2024; arXiv:2404.06654) found that "only half" of models claiming 32K+ context "can maintain satisfactory performance at the length of 32K." A context-window number on a spec sheet is an upper bound on what *could* be sent, not a guarantee of what can be *used* well.
- **Context rot in practice.** A November 2025 *Understanding AI* analysis ("Context rot," understandingai.org/p/context-rot-the-emerging-challenge) cites a concrete data point — Claude 3.5 Sonnet's accuracy on inference questions over long documents fell from 88% to 30% as the context filled, with multi-hop reasoning degrading even faster than single-hop lookup.

Put together: an agent that waits until it physically cannot fit more tokens before acting has already, in all likelihood, been silently degrading for a while. The "graceful degradation" framing in the original brief is apt, but the real opportunity is *upstream* of degradation — recognizing the shape of the problem early enough to propose a better path.

---

## Part 2 — Literature Review (Annotated Bibliography)

This section organizes verified sources by theme. Every entry was fetched directly; summaries describe what the source actually says, not an inference from its title.

### 2.1 Chunking strategies in NLP / LLM / RAG systems

| # | Source | What it actually establishes |
|---|---|---|
| 1 | Schwaber-Cohen & Patel, "Chunking Strategies for LLM Applications," Pinecone, 2025-06-28 — [pinecone.io/learn/chunking-strategies](https://www.pinecone.io/learn/chunking-strategies/) | Surveys five families: fixed-size, content-aware (sentence/paragraph via NLTK/spaCy or recursive separators), document-structure-aware (PDF/HTML/Markdown-informed), semantic (embedding similarity breakpoints), and "contextual" (LLM-generated chunk descriptions). Its central thesis — there is **no universal best chunk strategy**; the right one depends on data type, embedding model, and query shape — should anchor any design that picks a single default chunking algorithm. |
| 2 | LangChain, "Splitting recursively" — [docs.langchain.com/oss/python/integrations/splitters/recursive_text_splitter](https://docs.langchain.com/oss/python/integrations/splitters/recursive_text_splitter) | Documents `RecursiveCharacterTextSplitter`: an ordered separator list (`["\n\n", "\n", " ", ""]`) tried in sequence until chunks fall under a size target, preserving paragraph → sentence → word boundaries as a fallback hierarchy. This separator-priority idea generalizes well beyond text — it's the same shape as "try splitting on logical boundaries first, fall back to brute force only when you must." |
| 3 | LangChain, `RecursiveJsonSplitter` reference — [reference.langchain.com/.../json/RecursiveJsonSplitter](https://reference.langchain.com/python/langchain-text-splitters/json/RecursiveJsonSplitter) | A real, shipped, format-aware JSON splitter that walks nested structures and preserves hierarchy rather than cutting by raw character count, configurable via `max_chunk_size` (default 2000 chars) and `min_chunk_size`. This is the closest existing prior art to "JSON-aware chunking" named in the original brief — it exists, it's documented, and it is the right reference point rather than something to invent from scratch. |
| 4 | Khalusova, "Chunking Strategies for RAG: Best Practices and Key Methods," Unstructured, 2024-07-17 — [unstructured.io/blog/chunking-for-rag-best-practices](https://unstructured.io/blog/chunking-for-rag-best-practices) | Recommends starting *small* (~250 tokens / ~1000 characters) because oversized chunks hurt retrieval precision — a useful counterweight to the intuition that "fewer, bigger chunks = less overhead." Also stresses building an evaluation set to measure how chunk-size choices affect downstream quality, rather than picking a number and hoping. |
| 5 | Unstructured, "Chunking" core docs — [docs.unstructured.io/open-source/core-functionality/chunking](https://docs.unstructured.io/open-source/core-functionality/chunking) | Describes a two-stage approach: first *partition* a document into format-aware "elements" using knowledge of its actual format (so a table stays a table, a heading stays attached to its section), and only fall back to text-splitting when a single element is still too big. This "partition first, split only as a last resort" ordering is a strong design principle — it should inform how a `FormatSpecificChunker` decides *whether* to chunk at all versus picking a smaller logical unit. |
| 6 | Superlinked VectorHub, "Semantic Chunking" — [superlinked.com/vectorhub/articles/semantic-chunking](https://superlinked.com/vectorhub/articles/semantic-chunking) | Concrete mechanics for embedding-based chunking: embed each sentence, compute cosine similarity between consecutive sentences, place a boundary wherever similarity drops below a percentile threshold. This is the most rigorous "meaning-aware" technique found — but it has a real cost (an embedding pass over the whole input before you even start the real task), which matters for any cost/latency analysis of "should the agent do this automatically." |
| 7 | Mehta, "Improving Code Chunking for LLM-Powered RAGs Using Abstract Syntax Trees," Medium — [medium.com/@rajatmehtta5/...-682b7a7cc38e](https://medium.com/@rajatmehtta5/improving-code-chunking-for-llm-powered-rags-using-abstract-syntax-trees-682b7a7cc38e) | Describes AST/`tree-sitter`-based code chunking that aligns chunk boundaries with whole functions/classes, contrasted against naive fixed-width chunking, which "frequently severs a function signature from its body." Directly actionable for a `CodeChunker`: parse first, chunk along the parse tree, never along raw byte offsets. |

**What's conspicuously absent from the literature** (stated rather than papered over): there is no peer-reviewed paper specifically on "format-aware JSON/CSV/YAML chunking" — the strongest real references are software documentation (`RecursiveJsonSplitter`) rather than research papers. The brief's request for papers titled "Hierarchical Agent Reasoning" or "Segment-based Processing in distributed systems" did not surface real matches; the closest legitimate analogues are the agent-orchestration sources in §2.3.

### 2.2 Long-context LLM research

| # | Source | What it actually establishes |
|---|---|---|
| 8 | Liu et al., "Lost in the Middle: How Language Models Use Long Contexts," TACL 2024 — [arxiv.org/abs/2307.03172](https://arxiv.org/abs/2307.03172) | The foundational empirical result: U-shaped retrieval performance across context position, present even in models purpose-built for long contexts. The practical implication for chunking design: **where** you place the most important content within a chunk (and within the prompt that wraps it) matters as much as whether the chunk fits at all. |
| 9 | Hsieh et al., "RULER: What's the Real Context Size of Your Long-Context Language Models?" NVIDIA, COLM 2024 — [arxiv.org/abs/2404.06654](https://arxiv.org/abs/2404.06654) | Benchmarked 13 tasks (retrieval, multi-hop tracing, aggregation, QA) at scale and found roughly half of models claiming ≥32K context fail to "maintain satisfactory performance" even at that length. This is the strongest available evidence that **advertised context size is not a reliable design constant** — any `ContextAnalyzer` that uses the model's nominal window as its threshold is likely being too generous. |
| 10 | Lee, "Context rot: the emerging challenge that could hold back LLM progress," *Understanding AI*, 2025-11-10 — [understandingai.org/p/context-rot-the-emerging-challenge](https://www.understandingai.org/p/context-rot-the-emerging-challenge) | A practitioner-facing synthesis (not peer-reviewed, but well-sourced) that names the phenomenon "context rot" and cites a striking data point: Claude 3.5 Sonnet's long-document inference accuracy fell from 88% to 30% as the context filled, with multi-hop reasoning degrading fastest. Useful as the bridge between the academic findings above and a plain-language argument a product surface could make to a user ("the longer this gets, the less reliable my answers become — let's split it up"). |

### 2.3 Agent framework decomposition / orchestration patterns

| # | Source | What it actually establishes |
|---|---|---|
| 11 | Microsoft Azure Architecture Center, "AI Agent Orchestration Patterns" (2026-02-12, updated 2026-05-12) — [learn.microsoft.com/.../ai-agent-design-patterns](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns) | Names the canonical multi-agent patterns: sequential/pipeline, concurrent fan-out/fan-in (= scatter-gather = map-reduce), group-chat, handoff, "magentic." Frames multi-agent decomposition as the right answer when "a single agent can't reliably handle certain tasks due to prompt complexity, tool overload, or security requirements" — i.e., an authoritative vendor source treating decomposition as a first-class architectural response to overload, not a workaround. |
| 12 | LangChain, "Subgraphs" (LangGraph docs) — [docs.langchain.com/oss/python/langgraph/use-subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs) | Shows a real, shipped mechanism (the `Send` API) for determining the *number* of parallel sub-tasks dynamically, at runtime, from the size/shape of the input state. This is the closest existing technical analogue to "decide how many chunks to create based on how big the input actually is." |
| 13 | CrewAI, "Hierarchical Process" — [docs.crewai.com/en/learn/hierarchical-process](https://docs.crewai.com/en/learn/hierarchical-process) | A real "manager agent evaluates the incoming task, delegates pieces to specialized workers, validates results" pattern — but notably **opt-in** (`Process.hierarchical`; sequential is the default). The opt-in default is itself a signal: even a framework built around multi-agent orchestration doesn't turn decomposition on by default, suggesting the maintainers judge it to add enough overhead/unpredictability that it shouldn't be silently assumed. |
| 14 | AutoGen 0.2 docs, "Task Decomposition" — [microsoft.github.io/autogen/0.2/docs/topics/task_decomposition](https://microsoft.github.io/autogen/0.2/docs/topics/task_decomposition/) | Documents four concrete decomposition mechanisms (planner-as-function, GroupChat sequencing, "AutoBuild" dynamic team generation, meta-prompted scheduling). Useful primarily as evidence that "propose a decomposition, then execute it piece by piece" is an established, named pattern with multiple real implementations — not a novel idea that needs inventing from scratch. |
| 15 | Weng, "LLM Powered Autonomous Agents," *Lil'Log*, 2023-06-23 — [lilianweng.github.io/posts/2023-06-23-agent](https://lilianweng.github.io/posts/2023-06-23-agent/) | A widely-cited synthesis covering Chain-of-Thought decomposition, Tree-of-Thoughts branching search, and LLM+P (delegating planning to a classical PDDL planner). Notably observes that decomposition can be driven by the LLM itself, by task-specific instructions, *or by human input* — a three-way framing that maps directly onto the "should the agent decide, ask, or be told?" question this document returns to in Part 6. |
| 16 | F22 Labs, "Map Reduce for Large Document Summarization with LLMs" — [f22labs.com/blogs/map-reduce-for-large-document-summarization-with-llms](https://www.f22labs.com/blogs/map-reduce-for-large-document-summarization-with-llms/) | Plainly states the map-reduce trade-off that any aggregation design must reckon with: splitting and summarizing in parallel is tractable, but "cross-chunk context can be lost and final quality depends on intermediate-summary quality." This is the conceptual ancestor of LangChain's `MapReduceDocumentsChain` and the most honest account found of *why* naive chunk-and-combine isn't automatically a win. |

---

## Part 3 — Competitor Audit

Six tools were investigated. For each, the question was narrow and falsifiable: *does it detect oversized input, and if so, does it (a) error, (b) silently truncate, (c) silently summarize/compact, or (d) proactively propose a segmented plan to the user?*

### 3.1 Feature matrix

| Tool | Detects large input? | What it actually does | Proposes segmenting to the user? | Sources |
|---|---|---|---|---|
| **Claude Code** | Yes — `/context` indicator, auto-compaction near the limit, a hardcoded Read-tool token cap | Auto-compacts the conversation as it nears ~200K tokens (1M for `[1m]` variants), replacing history with a structured summary; Read tool caps file ingestion (community reports cite ≈25K tokens / 2000 lines via `@`); docs recommend routing large reads through subagents to keep them out of the main context | **Indirectly.** No "split into N segments?" prompt exists; the documented mitigation is architectural (subagents, `offset`/`limit` params), placing the decomposition burden on the user/operator rather than the agent volunteering a plan | [code.claude.com/docs/en/context-window](https://code.claude.com/docs/en/context-window); [issue #12054](https://github.com/anthropics/claude-code/issues/12054); [#19988](https://github.com/anthropics/claude-code/issues/19988); [#20223](https://github.com/anthropics/claude-code/issues/20223); [#4002](https://github.com/anthropics/claude-code/issues/4002) |
| **Aider** | Only reactively — by its own documentation, "never enforces token limits, it only reports token limit errors from the API provider" | Surfaces the provider's raw error with token counts; tells the user to `/drop`, `/clear`, "break your code into smaller source files," or "ask for smaller changes." Separately, its **repo-map** feature *is* proactive: a tree-sitter + graph-ranking algorithm self-limits to a `--map-tokens` budget (default 1k) | **No**, for the chat/file-overflow case (purely reactive); **yes**, but silently and only for repo-map summaries (the chunking happens, but isn't "proposed" — it's just how the feature works) | [aider.chat/docs/troubleshooting/token-limits.html](https://aider.chat/docs/troubleshooting/token-limits.html); [aider.chat/docs/repomap.html](https://aider.chat/docs/repomap.html) |
| **Cline** | Inconsistently — a hardcoded 300KB block on file reads exists, but no pre-flight size check feeds the model call itself | Blocks reads over 300KB outright; for anything smaller, sends the **entire** file, which can trigger HTTP 413 "prompt too long" with — per the maintainers' own consolidated issue — "no recovery option" besides retrying or starting over | **No** (not shipped). Issue #4389 *proposes* chunked/streaming reads and smart truncation, explicitly comparing Cline unfavorably to Gemini CLI's truncation behavior — but this is a feature request, not a feature | [issue #4389](https://github.com/cline/cline/issues/4389); [#4576](https://github.com/cline/cline/issues/4576); [#5251](https://github.com/cline/cline/issues/5251) |
| **LangChain** | N/A — it's a library; the *developer* decides whether and how to chunk | Ships the actual primitives (`RecursiveCharacterTextSplitter`, `RecursiveJsonSplitter`, `MapReduceDocumentsChain`) that make principled chunking buildable | **Yes, by construction** — composing split → map → reduce pipelines is the entire point of the library; there's no "agent" to propose anything because the human is the orchestrator | [reference.langchain.com/.../RecursiveCharacterTextSplitter](https://reference.langchain.com/v0.3/python/text_splitters/character/langchain_text_splitters.character.RecursiveCharacterTextSplitter.html) |
| **CrewAI** | Yes, but reactively — a `respect_context_window` flag triggers detection "when an agent's conversation history grows too large" | If `True` (documented default/recommended): auto-summarizes history and continues silently; if `False`: stops with an error | **No** — it's a binary "summarize-or-die" switch with no user-facing proposal or visibility into what got summarized away | [docs.crewai.com/en/concepts/agents](https://docs.crewai.com/en/concepts/agents); [issue #1241](https://github.com/crewAIInc/crewAI/issues/1241) |
| **OpenCode** | **Could not verify.** The project is real (MIT-licensed terminal coding agent, github.com/opencode-ai/opencode, opencode.ai), but no documentation page, blog post, or issue describing its specific large-input handling was found | Could not verify | Could not verify | [opencode.ai](https://opencode.ai/); [github.com/opencode-ai/opencode](https://github.com/opencode-ai/opencode) |

### 3.2 The pattern across the matrix

Two things stand out, and both are uncomfortable for the premise of "let's just build the proactive-proposal feature":

1. **Nobody does it.** Not one of the five tools where evidence could be gathered offers a user-facing "this is big — want me to split it up?" proposal. The space between "error reactively" (Aider, Cline) and "summarize/compact silently" (Claude Code, CrewAI) is empty. That's either an opportunity (nobody's solved it, teaAgent could differentiate) or a warning sign (maybe it's harder to do well than it sounds, and the mature projects converged on "silent compaction" because *transparency about chunking is itself expensive to get right* — see Part 6 on the HN pushback against intermediary compression).
2. **The "decompose it for me" feature requests exist and are old.** Aider issue #74 — "chunk large files so it can access a single function in a large file instead of the entire file" — and Cline discussion #957 — "Do you really want to add this to the chat? It may break!" — are *exactly* the proposal pattern this document is investigating, requested by real users, against real projects, and neither has shipped. That's not proof it's a bad idea; it's evidence that wanting it and shipping it well are different distances.

---

## Part 4 — Community Sentiment (What Could and Could Not Be Verified)

**Methodology and an honest disclosure up front:** GitHub issues and Hacker News threads were directly fetched and read. **Reddit could not be retrieved through any available tool** — every `site:reddit.com` search returned no indexed results, and direct fetches of `reddit.com`/`old.reddit.com` were refused by the fetch tool. **Discord and Twitter/X were not attempted** — there is no tool in this environment that can authenticate into a Discord server or search X, and inventing quotes from either would be fabrication. Per the standing instruction not to guess URLs or generate unverifiable content, those three platforms are reported here as gaps, not filled with plausible-sounding placeholders.

### 4.1 GitHub Issues — verified, and the clearest signal in this whole document

Nine real issues were read in full. The pattern across them is more consistent than expected:

- **The exact feature being asked about already has a name in the wild, and users are asking for it by description if not by name.** Aider [#74](https://github.com/Aider-AI/aider/issues/74): "chunk large files so it can access a single function in a large file instead of the entire file." Cline [#957](https://github.com/cline/cline/discussions/957): a proactive pre-flight warning, "Do you really want to add this to the chat? It may break!" Claude Code [#28863](https://github.com/anthropics/claude-code/issues/28863): replace silently-truncated output with an explicit marker — *"Attempted to [...], but output was truncated at 32k tokens. The response was incomplete and discarded"* — to break what the reporter called a **"context death spiral"** (retrying into a context that's already too small to hold the retry).
- **The failure mode users describe is strikingly consistent across unrelated projects**: Aider [#4113](https://github.com/Aider-AI/aider/issues/4113) — "the LLM starts spewing back garbage (often in an entirely different programming language)"; Cline [#5251](https://github.com/cline/cline/issues/5251) — "Retries won't help since the context window isn't automatically shrinking, you'll just hit the same error again." Different codebases, same shape of complaint: degrade-then-fail, with no recovery path that doesn't start over.
- **There's also a counter-current: some users want *less* automatic context use, not more automation around it.** Aider [#4583](https://github.com/Aider-AI/aider/issues/4583) asked for a setting to deliberately *cap* context at ~20K tokens on a 262K-capable model — a reminder that "the agent should manage this for me automatically" is not a unanimous preference; some users want a dial, not an autopilot.
- **Maintainer engagement is often thin or negative.** [#14888](https://github.com/anthropics/claude-code/issues/14888) (a concrete proposal for dynamic per-model token limits) was closed "not planned." Cline [#957](https://github.com/cline/cline/discussions/957) drew two reactions and zero substantive replies. This is worth sitting with: *the feature this document is scoping has been requested, with specifics, against three different popular tools, and none of the maintainers have prioritized it.* That could mean it's underrated — or it could mean people closer to the problem than we are have judged the cost/benefit unfavorably and said so by inaction.

### 4.2 Hacker News — verified, two threads, contains the most important pushback in this document

- **["Context is the bottleneck for coding agents now"](https://news.ycombinator.com/item?id=45387374)**: *bgirard* names "context poisoning" — when an agent spends 10K tokens chasing a bad lead, it "has trouble ignoring" that exploration even after being redirected, polluting everything downstream. *tptacek* describes a pattern worth stealing directly: write a structured summary of everything established so far to a file as a checkpoint before a handoff. *vel0city* observes that some tools already keep a running plan file and "automatically compact their contexts" — independent confirmation that practitioners are converging on exactly this kind of behavior without anyone calling it "segment-aware processing."
- **["Show HN: Context Gateway"](https://news.ycombinator.com/item?id=47367526)** is the single most load-bearing source in this whole research pass, because it's the only place real practitioners directly debated *the actual proposal under consideration here* — automated context management — and the debate was not one-sided:
  - *ivzak* cited research that "steering away from the literal matching crushes performance already at 8k+ tokens" — i.e., context rot bites earlier than people assume, reinforcing the case *for* proactive intervention.
  - *sethcronin* pushed back hard: intermediary compression "can strip useful context that the agent actually needs to diagnose" — i.e., automated chunking/compression is not free; it can actively sabotage the very debugging it's meant to enable.
  - *guard402* raised a security angle rarely discussed in this space: compression "may interact with [untrusted content/instructions] in non-obvious ways" — meaning a chunking layer is itself a new attack surface (e.g., a malicious log file engineered so that the *summary* of chunk 3 instructs the agent to do something the original content never said).

This thread alone justifies treating "should the agent do this automatically" as a genuinely open question rather than an obviously-yes. The strongest voices *for* automated handling are arguing from quality data (context rot is real and starts early); the strongest voices *against* are arguing from a different kind of risk (silent information loss, new injection surfaces) that quality benchmarks don't capture.

### 4.3 Reddit, Discord, Twitter/X — explicitly not reported

No real content from these three platforms is included anywhere in this document. This is a genuine evidence gap, not a stylistic choice — if community sentiment on these platforms matters to a final design decision, it would need to be gathered by someone with authenticated access (a logged-in Reddit session, a member of the relevant Discord servers, X search access), none of which exist in this environment.

---

## Part 5 — Technical Design Space

### 5.1 Chunking strategies by format

The literature converges on one meta-principle worth stating before any per-format detail: **partition along the structure that already exists before falling back to brute-force splitting** (Unstructured's "partition into elements first," LangChain's "ordered separator fallback," the AST-chunking approach for code). Per format:

- **JSON.** `RecursiveJsonSplitter` (source #3) is real, shipped prior art: walk the structure, split arrays by element and objects by key-groups, never separate a value from the key that names it. The shape to copy: configurable `max_chunk_size` with hierarchy-preserving recursion, not byte-offset slicing.
- **Code.** Parse first (AST or `tree-sitter`), chunk along function/class/module boundaries, and *always* carry the surrounding imports/class signature with each chunk (source #7). A chunk that contains a method body but not its class context is close to useless to a model.
- **CSV.** Split by row, always re-attach the header to every chunk — this is closer to "trivial" than the other formats because the structure is flat and uniform, but the header-repetition requirement is easy to forget and breaks everything downstream if missed.
- **Plain text / Markdown / logs.** `RecursiveCharacterTextSplitter`'s separator-priority approach (source #2) generalizes well: try paragraph breaks, then sentence breaks, then hard character limits — but for *logs* specifically, the natural unit is a line or a timestamped entry, and grouping by time-window or by recurring pattern (e.g., stack traces) is likely to beat generic text splitting.
- **YAML / XML.** No dedicated tooling was found in the literature for either; the closest applicable principle is still "partition along the document's own structure" (top-level keys for YAML, element/subtree for XML) — these would likely need bespoke chunkers built on existing parsers (`PyYAML`, `lxml`) rather than adapted text splitters.

### 5.2 Preserving meaning across chunk boundaries

Three real techniques surfaced, each with a real cost:

1. **Structural alignment** (don't cut mid-unit) — cheap, mechanical, and the highest-leverage first step. This alone prevents the worst failure (a truncated JSON object, a function split across two chunks).
2. **Semantic boundary detection** (embedding similarity breakpoints, source #6) — more principled for prose, but requires an embedding pass over the *entire* input before the real work starts. For a CLI agent that's supposed to feel responsive, that's a real latency and cost tax to weigh against the quality gain.
3. **Overlap windows** (`chunk_overlap` in `RecursiveCharacterTextSplitter`) — cheap insurance against boundary information loss, at the cost of redundant tokens being processed (and paid for) twice.

None of these is "solved" in the sense of being free. Each is a deliberate trade a design has to make explicit, not a checkbox to tick.

### 5.3 Result aggregation

The map-reduce literature (source #16) is unusually candid about the central risk here: **the quality of the final answer is bounded by the quality of the worst intermediate summary**, and cross-chunk relationships ("the bug introduced in chunk 2 is the cause of the error in chunk 7") can vanish entirely if each chunk is processed in isolation. Three patterns exist for managing this, none of them free:

- **Sequential with running state** — each chunk's processing sees a summary of what came before. Preserves cross-chunk continuity; serializes the work (slower, and errors compound forward).
- **Parallel map, then reduce** — every chunk processed independently, then synthesized. Fast and resilient to a single chunk's failure; structurally blind to cross-chunk relationships unless the reduce step is given enough signal to reconstruct them.
- **Hierarchical reduce** — combine in a tree (chunks → groups → final), bounding how much any single synthesis step has to hold at once. Mitigates the "reduce step itself overflows" failure mode that a flat reduce over many chunks will eventually hit, at the cost of more orchestration complexity.

A failed segment is the sharpest open question none of the literature addresses cleanly: retry it alone (cheap, but risks the same failure twice), skip it and flag the gap (loses information silently unless surfaced loudly), or abort the whole job (safest, but throws away completed work). The Claude Code issue about "context death spirals" (#28863) is the clearest real-world articulation of *why* "just retry" is the wrong default — a retry into an already-degraded context tends to fail the same way again, just more expensively.

### 5.4 Implementation patterns from the original brief, evaluated against the evidence

- **Pattern 1 (Explicit, ask-before-each-chunk)** maps closest to what HN commenters were actually defending (visibility, control) — but "process segment 1/30? [yes][no]" thirty times is also the textbook definition of a UX nobody will tolerate. The honest version of "explicit" is *ask once, about the plan, not the execution* — closer to Pattern 3.
- **Pattern 2 (Implicit, just grind through it)** is what CrewAI's `respect_context_window=True` already does, silently — and it's exactly the behavior that drew the sharpest pushback on HN (*sethcronin*: silent compression "can strip useful context the agent actually needs"). Implicit segmentation trades user trust for smoothness; the GitHub evidence (issue #28863's "context death spiral," #5251's "retries won't help") suggests that trade has already burned real users on real tools.
- **Pattern 3 (Staged: sample → orient → propose → confirm → execute)** is the best-supported by the evidence gathered here. It mirrors *tptacek*'s checkpoint-summary pattern from HN, *vel0city*'s "plan file + compaction" observation, and the AutoGen "planner proposes, then dispatches" architecture (source #4) — three independent sources converging on "look first, propose a plan, then execute the plan," which is a meaningfully different (and more defensible) shape than "ask permission for every step" or "do it all silently."

---

## Part 6 — UX & Product Strategy

### 6.1 When should this even be proposed?

The RULER finding (source #9 — roughly half of models can't reliably use 32K even when they claim it) argues against using the model's *advertised* window as the trigger threshold; a usable-capacity estimate, calibrated lower than the spec sheet, is the more honest input to a "should I propose chunking?" decision. Beyond raw size, two softer signals matter and neither has good off-the-shelf tooling: *task shape* (a "summarize this log" is a better candidate for map-reduce than "find the one bug in this log," where losing cross-chunk context is fatal to the actual goal) and *user history* (if someone has said "no, just do it" to a chunking proposal before, repeating the question is friction, not help — though *building* that memory is itself new surface area).

### 6.2 How to explain it without either patronizing or confusing

The original brief's three example phrasings map onto a real spectrum, and the evidence favors the middle one more than either extreme:

- *"I'll split this into 3 chunks and process each"* — too terse to let the user object to anything specific; by the time they realize chunk boundaries matter to their task, the work is already split.
- *"Large task detected. Want me to process in segments?"* — too vague to be a real decision; "segments" of *what*, decided *how*? This invites a yes/no on a plan the user can't actually evaluate.
- ***A plan the user can actually inspect and redirect*** — e.g., "this log is ~140K tokens; I'd split it by timestamp into 5 windows of ~28K each, summarize each, then merge — does that grouping make sense for what you're looking for, or would splitting by service name fit your question better?" This is more words, but it's the only version that gives the user something to *correct*, which is exactly the lever the HN skeptics said was missing from automated approaches. It costs more to generate and more to read; it buys back the trust that silent or vague approaches were shown (in the GitHub evidence) to spend.

### 6.3 Failure modes worth designing for up front

Pulling directly from the verified evidence rather than brainstorming abstractly:

- **A chunk fails mid-run.** The Claude Code "context death spiral" report (#28863) is the concrete cautionary tale: don't retry blindly into a context that's already compromised. Whatever the retry policy is, it needs an explicit "this is now a different, smaller problem" reset, not a literal re-ask.
- **The user declines, and the task fails anyway.** This is the scenario the reactive tools (Aider, pre-#4389 Cline) live in permanently — and per Aider's own troubleshooting docs, the fallback is "tell the user to do it manually," which is just punting the same decision back to them with less help than before. If a user says no to a proposal, the agent should still be able to do *something* useful (partial results, a clearer explanation of exactly where and why it would break) rather than reverting to the same wall.
- **Chunking silently drops something the user needed.** This is *sethcronin*'s objection from the Context Gateway thread, and it's the hardest one to design against because the loss is invisible until it matters. The honest mitigation is not "chunk better" — it's "say what you dropped." An aggregation step that can name its own gaps ("chunks 3 and 4 both mentioned a `connection_reset` error close to their boundary — there may be more context just outside what I processed") turns an invisible failure into a visible, correctable one.

---

## Part 7 — Implementation Plan (Honest Version)

The architecture sketch in the brief (`ContextAnalyzer → ChunkingProposal → FormatDetector → FormatSpecificChunker → SegmentProcessor → ResultAggregator`) is sound as a *pipeline shape* — it mirrors the real map-reduce and orchestrator/worker patterns found in the literature (sources #11, #16). Two changes to the proposed sequencing fall directly out of the evidence:

1. **`ChunkingProposal` should come *after* a cheap structural look, not before.** The evidence on format-aware partitioning (Unstructured's "partition into elements first," `RecursiveJsonSplitter`'s hierarchy walk) suggests the agent can't propose a *good* plan without first knowing the input's shape — "I'll split this into 5 chunks" is a much weaker proposal than "I'll split this by top-level array entries, since that's how the JSON is structured." That argues for `ContextAnalyzer → FormatDetector → (cheap structural pass) → ChunkingProposal`, i.e., detect format and skim structure *before* proposing, even if the full chunking doesn't happen until after the user agrees.
2. **`ResultAggregator` needs a defined "what did we lose" output, not just a "here's the combined answer" output**, given §6.3's "silent loss" failure mode is the one the evidence says is hardest to detect after the fact.

Given those evidentiary checks, a defensible sequencing — *not a committed timeline, since real estimates require knowing teaAgent's current architecture and the team's velocity, neither of which this research pass examined* — would be:

- **Phase 1 — Make the problem visible before automating the response.** Build the `ContextAnalyzer` (size + format estimation) and surface it to the user *without* doing anything automatic yet — i.e., ship the equivalent of Cline discussion #957's "this is large, are you sure?" warning first. This is the smallest possible slice that delivers real value (it directly addresses the JSON-truncation bug's root cause: nobody asked "will this fit?"), and it's cheap to validate against real usage before investing in the harder parts.
- **Phase 2 — One format, done well, with a real proposal-and-confirm loop.** Pick the format most relevant to teaAgent's actual workloads (likely JSON or logs, given the triggering bug) and build the full pipeline for *just that format*, including the inspectable-plan UX from §6.2. Resist building `CSVChunker`/`CodeChunker`/etc. speculatively — source #1's central finding (no universal best chunking strategy) argues for depth on one real case over breadth across hypothetical ones.
- **Phase 3 — Generalize only from what Phase 2 actually teaches.** Whether to add more format-specific chunkers, build semantic chunking, or invest in aggregation sophistication should be driven by what real usage in Phase 2 reveals is actually the bottleneck — not by the format list in the original brief, which is a plausible-sounding inventory rather than a measured priority order.

### 7.1 What this plan deliberately does *not* commit to

It does not commit to a 12-week, three-phase calendar with named milestones, because no evidence gathered in this pass speaks to teaAgent's velocity, current architecture, or competing priorities — manufacturing a calendar would be exactly the kind of confident-sounding fabrication this document has tried to avoid elsewhere. It also does not commit to building semantic chunking, multi-format support, or streaming processing in any near-term phase, because the evidence (§5.2, §7 Phase 2 rationale) suggests those are the parts most likely to cost more than they're worth *until* a single real format is working end-to-end and tells you what actually breaks.

---

## Part 8 — Risk Analysis

| Risk | What the evidence actually says about it | Mitigation suggested by that evidence |
|---|---|---|
| **Accuracy: chunking loses context the model needed** | This is not hypothetical — it's *sethcronin*'s specific, first-hand objection on HN, and it's structurally what the map-reduce literature (source #16) calls out as the central trade-off of the entire pattern | Make losses *visible* (§6.3's "name what you dropped"), prefer structural-boundary chunking over arbitrary splits (source #5's "partition first"), and treat overlap windows as cheap insurance worth the redundant-token cost |
| **Cost: processing in segments costs more tokens** | Confirmed directly — Cline issue #6667 reports real per-call costs jumping from "$0.03–$0.20" to "$2–$4" under uncontrolled context growth; map-reduce inherently reprocesses shared context across chunks | Size chunks deliberately rather than defensively-large (Unstructured's "start smaller" finding, source #4); make the *cost* of the proposed plan part of what's shown to the user before they commit to it, not a surprise on the invoice |
| **UX: proactive proposals annoy users who just want it done** | Directly evidenced — Aider issue #4583 is a user asking to *cap* automatic context use, and source #15 (Lilian Weng's synthesis) frames "human input" as only one of three legitimate decomposition drivers, not the default one | A "stop asking, just handle it" preference, once expressed, should stick — this is squarely the kind of per-user state that's easy to describe and hard to build well, and should be scoped honestly as its own piece of work rather than assumed away |
| **Trust/adoption: will users believe the chunked answer is as good as a direct one?** | The thinnest evidence base in this document — no source directly measured user trust in chunked vs. unchunked agent output. What *is* well-evidenced is the precondition for trust: source #8 (Lost in the Middle) and the "context rot" piece (source #10) both show that the *unchunked* answer was already degrading; a chunked answer that's honest about its own boundaries may well be *more* trustworthy than a confident-sounding answer from an overloaded context, but that's an inference from adjacent evidence, not a measured finding | Treat this as the area most worth user-testing directly — build the smallest possible version (Phase 1's visibility-only step) and observe real reactions before investing further, rather than designing the full UX from first principles |

---

## Appendix — Source Index

All 24 sources cited in this document, with verification status:

**Fetched and read directly (chunking & long-context literature):**
1. [Pinecone — Chunking Strategies for LLM Applications](https://www.pinecone.io/learn/chunking-strategies/)
2. [LangChain — Recursive text splitter](https://docs.langchain.com/oss/python/integrations/splitters/recursive_text_splitter)
3. [LangChain — RecursiveJsonSplitter reference](https://reference.langchain.com/python/langchain-text-splitters/json/RecursiveJsonSplitter)
4. [Unstructured — Chunking Strategies for RAG](https://unstructured.io/blog/chunking-for-rag-best-practices)
5. [Unstructured — Chunking core docs](https://docs.unstructured.io/open-source/core-functionality/chunking)
6. [Superlinked VectorHub — Semantic Chunking](https://superlinked.com/vectorhub/articles/semantic-chunking)
7. [Medium — AST-based code chunking for RAG](https://medium.com/@rajatmehtta5/improving-code-chunking-for-llm-powered-rags-using-abstract-syntax-trees-682b7a7cc38e)
8. [arXiv 2307.03172 — Lost in the Middle](https://arxiv.org/abs/2307.03172)
9. [arXiv 2404.06654 — RULER](https://arxiv.org/abs/2404.06654)
10. [Understanding AI — Context rot](https://www.understandingai.org/p/context-rot-the-emerging-challenge)
11. [Microsoft Learn — AI Agent Orchestration Patterns](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns)
12. [LangChain — LangGraph Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)
13. [CrewAI — Hierarchical Process](https://docs.crewai.com/en/learn/hierarchical-process)
14. [AutoGen 0.2 — Task Decomposition](https://microsoft.github.io/autogen/0.2/docs/topics/task_decomposition/)
15. [Lil'Log — LLM Powered Autonomous Agents](https://lilianweng.github.io/posts/2023-06-23-agent/)
16. [F22 Labs — Map Reduce for Large Document Summarization](https://www.f22labs.com/blogs/map-reduce-for-large-document-summarization-with-llms/)

**Fetched and read directly (competitor docs & GitHub issues):**
17. [Claude Code — Context window docs](https://code.claude.com/docs/en/context-window) · [issue #12054](https://github.com/anthropics/claude-code/issues/12054) · [#19988](https://github.com/anthropics/claude-code/issues/19988) · [#20223](https://github.com/anthropics/claude-code/issues/20223) · [#4002](https://github.com/anthropics/claude-code/issues/4002) · [#14888](https://github.com/anthropics/claude-code/issues/14888) · [#28863](https://github.com/anthropics/claude-code/issues/28863)
18. [Aider — Token limits troubleshooting](https://aider.chat/docs/troubleshooting/token-limits.html) · [Repo map docs](https://aider.chat/docs/repomap.html) · [issue #74](https://github.com/Aider-AI/aider/issues/74) · [#4113](https://github.com/Aider-AI/aider/issues/4113) · [#4583](https://github.com/Aider-AI/aider/issues/4583)
19. [Cline — issue #4389](https://github.com/cline/cline/issues/4389) · [#4576](https://github.com/cline/cline/issues/4576) · [#5251](https://github.com/cline/cline/issues/5251) · [#6667](https://github.com/cline/cline/issues/6667) · [discussion #957](https://github.com/cline/cline/discussions/957)
20. [LangChain — RecursiveCharacterTextSplitter API reference](https://reference.langchain.com/v0.3/python/text_splitters/character/langchain_text_splitters.character.RecursiveCharacterTextSplitter.html)
21. [CrewAI — Agent concepts (respect_context_window)](https://docs.crewai.com/en/concepts/agents) · [issue #1241](https://github.com/crewAIInc/crewAI/issues/1241)
22. [OpenCode project (existence confirmed; large-input handling not documented anywhere found)](https://opencode.ai/) · [github.com/opencode-ai/opencode](https://github.com/opencode-ai/opencode)

**Fetched and read directly (community sentiment — Hacker News):**
23. [HN — "Context is the bottleneck for coding agents now"](https://news.ycombinator.com/item?id=45387374)
24. [HN — "Show HN: Context Gateway"](https://news.ycombinator.com/item?id=47367526)

**Explicitly not included — could not be verified with available tools:**
- **Reddit**: every `site:reddit.com` search returned no results; direct fetches of reddit.com/old.reddit.com were refused by the fetch tool. No real Reddit content is quoted or referenced anywhere above.
- **Discord**: no tool in this environment can authenticate into a Discord server. No Discord content is quoted or referenced anywhere above.
- **Twitter/X**: no tool in this environment can search X. No X/Twitter content is quoted or referenced anywhere above.
- **"Hierarchical Agent Reasoning" / "Segment-based Processing in distributed systems" papers**: searches for these specific titles (as named in the original research brief) returned no real matching publications. The closest legitimate analogues found are sources #11–16 above, which are cited in their place rather than inventing matches for the requested titles.
