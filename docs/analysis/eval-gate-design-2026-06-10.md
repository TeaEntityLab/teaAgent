# Eval Gate Design — 2026-06-10

> **Claim class:** Current truth for release eval gating (WDD-002 precursor).
> **Requires:** WDA-004 wired at HEAD.

## Claim

Agent behavior changes that ship in a release must pass an offline eval gate
covering prompt regression, conversational-quality, and repo-map benchmark
corpora before the release workflow proceeds.

## Corpora

| Corpus | Module | Tests |
| --- | --- | --- |
| Prompt regression | `teaagent.prompt_regression` | 3 default cases |
| Conversational quality | `teaagent.eval_corpus` | 4 axes: clarification, interruption, correction, long-context recall |
| Repo-map benchmark | `teaagent.eval_corpus` + `teaagent.governance.repo_map_benchmark` | 1 deterministic fixture corpus case; critical-category coverage is required |

## Commands

```bash
# Green path (should exit 0)
python scripts/run_release_eval_gate.py --root .

# Verify gate blocks on seeded failure (should exit 1)
python scripts/run_release_eval_gate.py --root . --seed-failure

# Verify repo-map critical failure blocks the gate (should exit 1)
TEAAGENT_EVAL_SEED_REPO_MAP_FAILURE=1 python scripts/run_release_eval_gate.py --root .

# Unit tests
python -m pytest tests/test_release_eval_gate.py -q
```

## CI integration

- Tag releases: `.github/workflows/release.yml` runs the gate before packaging.
- Evidence bundle: `scripts/build_release_evidence_bundle.py` includes the gate in `release` profile.

## Artifacts

- Gate report JSON: `--report dist/evidence/release-eval-gate.json` (release workflow)
- Eval store: `.teaagent/eval/` under workspace root (gitignored)

## Limits

- The default CLI/release workflow path still uses offline replay for prompt and conversational tests unless a `model_runner` is injected; those runs are disclosed as simulated/advisory.
- `repo_map_benchmark` is now in the release corpus through a deterministic fixture benchmark, and release gating blocks if any configured critical category has zero enabled tests.
