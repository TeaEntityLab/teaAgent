# Repo-Map Benchmark Corpus & Quality Gate
# 2026-06-01

**Fills:** Gap **F-ECO-005** — *"create a repo-map benchmark corpus and turn it into a
release gate or nightly quality gate."* The May-31 review notes teaagent has large-repo
SLO acceptance but lacks **external benchmark credibility**: representative repos,
target-file tasks, top-K hit rate, latency, and failure classification.

**Grounding (current state, verified).** teaagent's "repo map" is the composite of:
- **`teaagent/code_analysis/_client.py`** — LSP client: `document_symbols`,
  definition/references resolution (`CodeReference`).
- **`teaagent/code_analysis/_treesitter.py`** — `extract_tree_sitter_relations` → AST
  visitor producing `CodeRelation` for imports, functions, classes, calls.
- **`teaagent/code_analysis/_graph_rag.py`** — `ingest_code_to_graph`,
  `ingest_code_relations_to_graph`.
- **`teaagent/hybrid_search.py`** (293), **`teaagent/graph_rag.py`** (104),
  **`teaagent/rag.py`** (209) — retrieval over the ingested graph.

So retrieval exists; what's missing is a **labeled corpus + metrics + a gate** to prove
it works and to catch regressions. Without it, "repo-map quality" is an assertion.

---

## What the benchmark must measure

| Metric | Definition | Why |
|--------|-----------|-----|
| **top-K hit rate** | fraction of tasks where the ground-truth target file is in the top-K retrieved | core retrieval quality |
| **MRR** | mean reciprocal rank of the first correct file | rewards ranking, not just presence |
| **symbol-resolution accuracy** | def/ref lookups that return the correct location | LSP/treesitter correctness |
| **latency p50/p95** | time to build map + answer a query, by repo size | the SLO dimension |
| **failure class** | miss / wrong-rank / timeout / parse-error / unsupported-language | turns failures into actionable buckets |

---

## Corpus design

```
benchmarks/repo-map/
├── corpus.yaml                # repo list + provenance + license
├── repos/<name>/              # vendored or pinned-commit checkout
└── tasks/<name>.jsonl         # {query, ground_truth_files[], ground_truth_symbol?, kind}
```

- **Repo selection:** ≥3 size tiers — small (<5k LOC), medium (~50k), large (>200k);
  multiple languages (at least Python + one tree-sitter generic language) to exercise
  `_treesitter` paths; permissive licenses only (record in `corpus.yaml`).
- **Task kinds:** `locate-target` (where to edit for feature X), `find-definition`,
  `find-references`, `cross-file-impact`. Ground truth labeled by a human or derived
  from real commit diffs (the files a known fix actually touched).
- **Provenance:** pin commit SHAs so results are reproducible (mirrors the project's
  determinism push in recent commits).

---

## Harness & gate

- `benchmarks/repo_map_bench.py`: builds the map per repo, runs tasks, emits
  `repo-map-scorecard.json` (per-metric, per-tier, per-language) + a human summary.
- **Gate modes:** (a) **release gate** — fail if top-K hit rate or p95 latency regress
  beyond a threshold vs the committed baseline; (b) **nightly** — trend tracking without
  blocking. Recommendation: nightly first (establish a baseline), promote to release
  gate once stable.
- Baseline stored as `benchmarks/repo-map-baseline.json`; the gate compares against it.

---

## Acceptance

- `test_repo_map_bench_runs`: harness executes the full corpus and emits a scorecard
  with every metric populated.
- `test_repo_map_gate_detects_regression`: an injected retrieval regression
  (e.g. disable graph relations) drops the hit rate below baseline and the gate fails.
- `test_repo_map_failure_classification`: a task with no possible hit is bucketed as
  `miss`, a parse error as `parse-error` — not a crash.
- `test_repo_map_latency_recorded`: p50/p95 recorded per size tier.

## Open decisions

- **DQ-REPO-1:** Vendor repos into the tree (reproducible, heavy) or pin SHAs + fetch in
  CI (light, network-dependent)? Recommendation: pin SHAs + cache; vendor only the
  smallest tier for offline determinism.
- **DQ-REPO-2:** Ground truth from human labels or commit-diff derivation? Recommendation:
  commit-diff derivation for `locate-target` (scalable), human labels for a small gold set.
- **DQ-REPO-3:** Release gate thresholds — absolute floor or relative-to-baseline?
  Recommendation: relative-to-baseline to avoid flakiness across model/tooling updates.

## Non-goals

- Not a public leaderboard (that's marketing; this is a quality gate).
- Not a model-quality benchmark — it measures *retrieval/repo-map*, isolating the map
  from the LLM (use a fixed retrieval-only path so model variance doesn't pollute it).

## Cross-references

- SLO/observability: `operator-cockpit-contract-2026-06-01.md`.
- Determinism precedent: recent commits "Make docs/test verification deterministic".
- Building blocks: `teaagent/code_analysis/_treesitter.py`, `_graph_rag.py`,
  `teaagent/hybrid_search.py`.
</content>
