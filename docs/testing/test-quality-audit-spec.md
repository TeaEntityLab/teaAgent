# Test Quality Audit System Spec

## Problem

The TeaAgent test suite has 3,486 tests across 376 files, but lacks systematic quality auditing. Weak tests (placeholders, construction-only, mock-heavy without assertions) can pass while providing no meaningful verification. This creates false confidence and risks undetected regressions.

## Goals

1. Create a repeatable automated audit tool that inventories and scores test quality
2. Establish governance standards for what counts as a meaningful test
3. Generate actionable audit reports (JSON + Markdown) to guide remediation
4. Target high-risk weak spots first (security, audit chain, daily-driver paths)

## Non-goals

- Rewrite the entire test suite
- Require every test to have long docstrings
- Gate on subjective quality scores in first implementation
- Make CI-hard failures before report-only phase

## Actors

- Quality engineers running audits
- Developers fixing weak tests
- CI systems running periodic audits
- Reviewers checking test quality before merge

## Inputs

- All test files under `tests/**/*.py`
- Pytest node IDs from `pytest --collect-only -q`
- Existing governance docs (acceptance.md, coverage-omit-ledger.md)

## Outputs

- JSON audit report: `.teaagent/test-quality-audit.json`
- Markdown audit report: `docs/testing/test-intent-audit-2026-06-05.md`
- Per-file metrics: purpose, assertions, skips, mocks, domain tags, risk flags
- Weak test classifications with recommended actions

## Functional Requirements

### Audit Tool (scripts/audit_test_quality.py)

1. **Collection Phase**
   - Run `pytest --collect-only -q` to collect all test node IDs
   - AST-scan all `tests/**/*.py` files
   - Extract: test functions, docstrings, assertions, mock usage, skip decorators

2. **Analysis Phase**
   - Classify test purpose from docstring (unit/integration/acceptance/regression/security/ux)
   - Count assertions per test
   - Detect weak patterns:
     - `assert True` or empty `pass` bodies
     - Construction-only tests (no behavior assertions)
     - Mock-only tests with no state/output assertions
     - Skip without documented reason
   - Calculate mock density (mocks per test)
   - Identify domain tags (audit, security, budget, workspace, etc.)

3. **Reporting Phase**
   - Emit JSON with per-file metrics
   - Emit Markdown with summary tables and high-risk findings
   - Flag severe issues: placeholder tests, acceptance files missing user-facing behavior proof
   - Provide recommended actions per file

4. **CLI Interface**
   ```bash
   python3 scripts/audit_test_quality.py --format markdown --output docs/testing/test-intent-audit-2026-06-05.md
   python3 scripts/audit_test_quality.py --format json --output .teaagent/test-quality-audit.json
   python3 scripts/audit_test_quality.py --fail-on severe  # available for strict trials
   ```

### Governance Docs

1. **test-quality-standards.md**
   - Define meaningful unit test criteria
   - Define meaningful integration test criteria
   - Define meaningful acceptance test criteria
   - Define security test requirements
   - Define UX/TUI test requirements
   - Define weak test anti-patterns

2. **test-intent-audit-2026-06-05.md**
   - First audit snapshot
   - High-risk findings
   - Remediation queue prioritized by risk/ROI
   - Baseline metrics for future comparison

### Validation

1. **Audit tool self-test**
   - Create temp test files with known weak patterns
   - Verify audit tool correctly identifies them
   - Verify false positive rate is acceptable

2. **Docs consistency check**
   - Add check to `scripts/validate_docs_consistency.py`
   - Fail on severe regressions: new placeholder tests, undocumented coverage omit entries
   - Warn on acceptance count drift

## Non-functional Requirements

- Performance: Audit should complete in < 30 seconds for 3,486 tests
- Maintainability: Audit tool should be simple AST analysis, not full execution
- Extensibility: Schema should support adding new metrics without breaking
- Actionability: Reports should prioritize high-risk fixes over cosmetic issues

## Edge Cases

- Tests with dynamic generation (pytest fixtures that create tests)
- Tests with complex inheritance or mixins
- Tests with parametrization that obscure individual test bodies
- Tests in optional dependency paths that legitimately skip

## Failure Modes

- AST parsing fails on malformed Python files → skip file with warning
- Pytest collection fails → report error and exit
- JSON/Markdown write fails → report error and exit
- False positives on weak test detection → allow manual override in audit report

## Open Questions

- Should audit tool run in CI by default? (Decision: report mode may run by default; strict gate waits for P0 remediation)
- What mock density threshold constitutes "mock-heavy"? (Decision: count mocks first; do not gate on mock density until false-positive rate is reviewed)
- Should skip reasons be required in code comments or docstrings? (Decision: docstring preferred, comments acceptable)

## Current Implementation Notes

- Class-based pytest node IDs are preserved during collection.
- Single-file `--tests-dir` targets are supported for AST scanning.
- The current AST scanner does not walk inherited base-class test bodies.
- Inline `# audit: ignore` comments are not supported; any future ignore mechanism should require a ticket ID, expiry date, and reviewer.
- Strict mode exists, but default validation remains report-only to avoid failing on known historical baseline debt before remediation.

## Schema

### JSON Report Schema

```json
{
  "audit_date": "2026-06-05",
  "total_tests": 3486,
  "total_files": 376,
  "files": [
    {
      "path": "tests/acceptance/test_audit_chain_integrity_flow.py",
      "collected_tests": 5,
      "domain": "security",
      "tier": "P0",
      "purpose_status": "documented",
      "assertion_profile": {
        "total_assertions": 15,
        "avg_assertions_per_test": 3.0,
        "tests_with_zero_assertions": 0
      },
      "skip_profile": {
        "total_skips": 0,
        "documented_skip_reasons": 0
      },
      "mock_profile": {
        "total_mocks": 0,
        "avg_mocks_per_test": 0.0,
        "mock_only_tests": 0
      },
      "risk_flags": [],
      "recommended_action": "none"
    }
  ],
  "summary": {
    "high_risk_files": 0,
    "medium_risk_files": 5,
    "placeholder_files": 0,
    "construction_only_files": 2
  }
}
```

### Markdown Report Structure

```markdown
# Test Intent Audit 2026-06-05

## Executive Summary
- Total tests: 3,486
- High-risk files: N
- Placeholder tests: N
- Construction-only tests: N

## High-Risk Findings
[Table of files with severe issues]

## Per-File Audit
[Detailed table with all metrics]

## Remediation Queue
[Prioritized list of fixes]

## Methodology
[Explanation of audit process and criteria]
```
