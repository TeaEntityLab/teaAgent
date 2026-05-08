# ADR 0002: P1 Primitives

## Status

Accepted for P1 implementation.

## Decision

Include trace recording, execution context compaction, eval framework, in-memory RAG,
skill review, and AI-BOM generation as P1 primitives on top of the P0 agent harness.

Each primitive follows the same no-external-dependency policy as P0 (stdlib only).

## Rationale

These primitives compose naturally with the agent harness without inventing new
interfaces:

- **TraceRecorder** records the agent's observation stream for replay and debugging.
- **ContextCompactor** compresses long observation lists into summaries, keeping
  prompts within model context windows.
- **Eval framework** lets teams measure agent performance on representative tasks
  before shipping model/prompt changes.
- **InMemoryRetriever** and **KnowledgeGraph** provide lightweight RAG so the
  agent can query project knowledge without a vector database.
- **SkillReview** audits skill content for security and correctness.
- **AIBOM** generates a bill-of-materials for the agent's dependencies.

## Consequences

- RAG components (`InMemoryRetriever`, `KnowledgeGraph`) are deliberately in-memory
  so that P2 can swap in GraphQLite-backed persistence without changing the agent
  contract.
- Eval framework is deterministic and does not call live LLMs; it uses pre-recorded
  decision sequences.
- These primitives add no mandatory dependencies beyond the Python standard library.

## Alternatives Considered

- **LangChain/LlamaIndex for RAG**: Rejected — adds 50+ transitive dependencies
  for what is essentially tf-idf similarity search.
- **pytest for evals**: Rejected — eval is harness-level, not test-level. The eval
  framework is embedded so the agent can self-assess.
