# ADR-0027: stdlib-only LLM Provider Adapter via urllib

**Status:** Accepted  
**Date:** 2026-06-02  
**Deciders:** Core team  
**Related ADRs:** ADR-0001 (P0 Framework — zero-dep posture), ADR-0017 (Backend Adapter Interfaces)

---

## Context

TeaAgent must communicate with LLM providers: Anthropic Claude (primary), OpenAI-compatible APIs (OpenAI, Ollama, local models), and Google Gemini. Each provider has a distinct HTTP API contract (different request shapes, SSE streaming formats, tool-call schemas, safety categories). The choice of how to talk to providers has significant consequences for dependency footprint, portability, and long-term maintenance.

## Decision

Implement LLM provider communication using Python's stdlib `urllib` exclusively, organized as:
- `llm/_adapters.py` — provider-specific HTTP request construction and response extraction (Claude, OpenAI, Gemini)
- `llm/_extract.py` — response normalization into `LLMResponse`/`LLMToolCall` common types
- `llm/_sse.py` — manual Server-Sent Events parser for streaming responses
- `llm/_retry.py` — configurable retry with exponential backoff
- `llm/_transport.py` — pluggable `HTTPTransport` interface with `UrllibHTTPTransport` default
- `llm/_types.py` — `LLMRequest`, `LLMResponse`, `ProviderConfig`, `LLMToolCall`, `SafetyCategory` shared types

Provider selection via `create_llm_adapter(provider_config)` factory.

## Consequences

**Positive:**
- Zero additional runtime dependencies; works in any Python 3.10+ environment
- Full control over retry strategy, timeout, and SSE parsing — no hidden behavior from SDK defaults
- `HTTPTransport` interface allows test injection of mock transports without patching `urllib`
- Provider enum is open: adding a new provider is adding one extractor function, not installing an SDK
- TLS certificate verification via `ssl.create_default_context()` — no custom CA trust issues

**Negative:**
- Manual SSE parsing is brittle against non-standard streaming framing; must track each provider's streaming contract manually
- No automatic schema update when providers change their API (e.g., new tool-call format) — requires manual adapter update
- No built-in connection pooling — each request opens a new TCP connection (acceptable at agent iteration frequency, not for batch workloads)
- Missing SDK-level features: automatic model fallback, usage tracking hooks, built-in prompt caching headers — must implement manually

## Alternatives Considered

### `anthropic` Python SDK
- **Rejected:** Pins `httpx`+`anyio` runtime dependencies (pulls in ~8 packages). Restricts to one provider. SDK updates trail API changes by days-weeks. P0 zero-dependency posture violated.

### `openai` Python SDK (used as multi-provider via base_url override)
- **Rejected:** Forces non-OpenAI providers into an OpenAI-shaped abstraction, losing provider-specific features (Gemini safety categories, Claude thinking blocks). SDK has the same httpx/anyio dependency problem.

### `litellm`
- **Rejected:** 50+ transitive dependencies, complex import graph, not stdlib-safe. Excellent for production polyglot setups but incompatible with TeaAgent's portability requirement.

### `httpx` directly (without SDK)
- **Rejected:** Adds one dependency (`httpx`) without providing meaningful benefit over `urllib` for our use case. `urllib` handles our SSE + retry needs adequately. Added if `httpx` proves necessary (e.g., HTTP/2 requirement from a provider).

## Rationale

LLM provider APIs are stable at the HTTP level and documented. The adapters are small (~100 lines per provider). The maintenance cost of tracking API changes manually is bounded and predictable. The zero-dependency benefit — ability to `pip install teaagent` without pulling in async runtimes — is material for CI, embedded, and restricted environments.

## Conditions to Reconsider

- If any provider requires HTTP/2 or WebSocket (current: all use HTTP/1.1 SSE) → add `httpx` as optional dep under `pip install teaagent[http2]`
- If provider API change frequency exceeds quarterly → evaluate official SDK as optional dep
- If connection-pool latency becomes measurable → add `urllib3` as optional dep for pooling
