# context_pack — Behavior Specification

## Purpose

Context packs gather planning/preflight evidence for a task.

## Responsibilities

- Extract candidate files and symbols.
- Include relevant memory evidence.
- Include graph/RAG hints when enabled.
- Clearly label side-effect behavior.

## Contracts

- Evidence labels must be semantically accurate.
- `readonly` behavior must either be enforced or not claimed.
- Context gathering must avoid hidden writes when advertised as read-only.

## Open risks

- `ContextPack.read_only` defaults to true even when builder `readonly` is false.
- Memory catalog construction can initialize state depending on path.
- Evidence consumers can misread the label as no-write proof.
