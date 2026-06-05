# Test Quality Audit Task Plan

## TASK-001: Create audit tool skeleton with pytest collection

- **Goal:** Create `scripts/audit_test_quality.py` that can collect pytest node IDs
- **Scope:** Basic CLI interface, pytest collection, file discovery
- **Inputs:** Test directory path (default: `tests/`)
- **Outputs:** List of collected test node IDs
- **Dependencies:** None
- **Acceptance Criteria:**
  - Script runs `pytest --collect-only -q` and parses output
  - Script discovers all `tests/**/*.py` files
  - CLI accepts `--tests-dir` argument
  - CLI accepts `--format` argument (json/markdown)
  - CLI accepts `--output` argument
- **Tests:**
  - Test script runs on actual test directory
  - Test script handles collection errors gracefully
- **Files likely touched:** `scripts/audit_test_quality.py`
- **Risk:** Low - simple subprocess wrapper
- **Parallelizable:** No
- **Human Review Required:** No

## TASK-002: Add AST scanning and basic metrics

- **Goal:** Scan test files with AST to extract test functions, docstrings, assertions
- **Scope:** AST parsing, metric extraction per file
- **Inputs:** List of test file paths
- **Outputs:** Per-file metrics (test count, docstring presence, assertion count)
- **Dependencies:** TASK-001
- **Acceptance Criteria:**
  - Parse each test file with Python AST
  - Extract all `def test_*` functions
  - Extract docstrings for test functions
  - Count `assert` statements in test bodies
  - Handle syntax errors gracefully (skip with warning)
- **Tests:**
  - Test with valid test file
  - Test with syntax error file
  - Test with no tests
- **Files likely touched:** `scripts/audit_test_quality.py`
- **Risk:** Low - standard AST parsing
- **Parallelizable:** No
- **Human Review Required:** No

## TASK-003: Add weak pattern detection

- **Goal:** Detect weak test patterns (assert True, pass, construction-only, mock-only)
- **Scope:** Pattern detection logic, risk flag assignment
- **Inputs:** AST nodes and metrics from TASK-002
- **Outputs:** Risk flags per test, weak pattern classifications
- **Dependencies:** TASK-002
- **Acceptance Criteria:**
  - Detect `assert True` or empty `pass` bodies
  - Detect construction-only tests (only assert existence/type)
  - Detect mock-only tests (mocks but no state/output assertions)
  - Detect skip decorators without documented reasons
  - Calculate mock density (mocks per test)
  - Assign risk flags: placeholder, construction_only, mock_only, undocumented_skip
- **Tests:**
  - Test with placeholder test
  - Test with construction-only test
  - Test with mock-only test
  - Test with documented skip
  - Test with undocumented skip
- **Files likely touched:** `scripts/audit_test_quality.py`
- **Risk:** Medium - pattern detection may have false positives
- **Parallelizable:** No
- **Human Review Required:** Yes - review pattern detection rules

## TASK-004: Add JSON output

- **Goal:** Emit structured JSON report with per-file metrics
- **Scope:** JSON schema implementation, file writing
- **Inputs:** Metrics from TASK-002 and TASK-003
- **Outputs:** JSON file at specified path
- **Dependencies:** TASK-002, TASK-003
- **Acceptance Criteria:**
  - JSON matches schema defined in spec
  - Includes all per-file metrics
  - Includes summary statistics
  - Handles write errors gracefully
- **Tests:**
  - Test JSON output matches schema
  - Test JSON is valid and parseable
  - Test write error handling
- **Files likely touched:** `scripts/audit_test_quality.py`
- **Risk:** Low - standard JSON serialization
- **Parallelizable:** No
- **Human Review Required:** No

## TASK-005: Add Markdown output

- **Goal:** Emit human-readable Markdown report with tables and summaries
- **Scope:** Markdown generation, table formatting
- **Inputs:** Metrics from TASK-002 and TASK-003
- **Outputs:** Markdown file at specified path
- **Dependencies:** TASK-002, TASK-003
- **Acceptance Criteria:**
  - Markdown includes executive summary
  - Markdown includes high-risk findings table
  - Markdown includes per-file audit table
  - Markdown includes remediation queue
  - Markdown includes methodology section
- **Tests:**
  - Test Markdown generation
  - Test table formatting
- **Files likely touched:** `scripts/audit_test_quality.py`
- **Risk:** Low - standard string formatting
- **Parallelizable:** No
- **Human Review Required:** No

## TASK-006: Create test-quality-standards.md

- **Goal:** Define what counts as a meaningful test
- **Scope:** Governance documentation
- **Inputs:** Spec requirements, existing test patterns
- **Outputs:** `docs/testing/test-quality-standards.md`
- **Dependencies:** None
- **Acceptance Criteria:**
  - Define meaningful unit test criteria
  - Define meaningful integration test criteria
  - Define meaningful acceptance test criteria
  - Define security test requirements
  - Define UX/TUI test requirements
  - Define weak test anti-patterns
- **Tests:**
  - Review against existing test suite
  - Review against spec requirements
- **Files likely touched:** `docs/testing/test-quality-standards.md`
- **Risk:** Low - documentation only
- **Parallelizable:** Yes (with TASK-007)
- **Human Review Required:** Yes - review standards completeness

## TASK-007: Create first audit snapshot

- **Goal:** Run audit tool and generate initial report
- **Scope:** Full audit execution, report generation
- **Inputs:** Completed audit tool from TASK-001 through TASK-005
- **Outputs:** `docs/testing/test-intent-audit-2026-06-05.md`, `.teaagent/test-quality-audit.json`
- **Dependencies:** TASK-001, TASK-002, TASK-003, TASK-004, TASK-005
- **Acceptance Criteria:**
  - Run audit tool on full test suite
  - Generate both JSON and Markdown reports
  - Document high-risk findings
  - Create prioritized remediation queue
  - Record baseline metrics
- **Tests:**
  - Verify reports are generated
  - Verify reports are parseable
- **Files likely touched:** `docs/testing/test-intent-audit-2026-06-05.md`, `.teaagent/test-quality-audit.json`
- **Risk:** Low - running existing tool
- **Parallelizable:** Yes (with TASK-006)
- **Human Review Required:** Yes - review audit findings

## TASK-008: Add audit tool self-tests

- **Goal:** Validate audit tool correctly identifies weak patterns
- **Scope:** Test suite for audit tool
- **Inputs:** Audit tool implementation
- **Outputs:** Test file for audit tool
- **Dependencies:** TASK-001, TASK-002, TASK-003
- **Acceptance Criteria:**
  - Create temp test files with known weak patterns
  - Verify audit tool detects placeholders
  - Verify audit tool detects construction-only tests
  - Verify audit tool detects mock-only tests
  - Verify audit tool detects undocumented skips
  - Verify false positive rate is acceptable
- **Tests:**
  - Run audit tool self-tests
- **Files likely touched:** `tests/test_audit_test_quality.py`
- **Risk:** Low - standard unit tests
- **Parallelizable:** No
- **Human Review Required:** No

## TASK-009: Targeted remediation of high-risk weak spots

- **Goal:** Fix high-risk weak tests identified in audit
- **Scope:** Test file modifications based on audit findings
- **Inputs:** Audit report from TASK-007
- **Outputs:** Modified test files with behavior assertions
- **Dependencies:** TASK-007
- **Acceptance Criteria:**
  - Fix placeholder tests in security/audit paths
  - Add behavior assertions to construction-only tests in P0 acceptance
  - Document skip reasons for optional dependencies
  - Verify smoke-test candidates exercise user-visible behavior
  - Run relevant tests to ensure fixes don't break
- **Tests:**
  - Run tests for modified files
  - Run P0 acceptance tier
- **Files likely touched:** Specific test files identified in audit
- **Risk:** Medium - modifying tests may expose real bugs
- **Parallelizable:** Yes (can fix multiple files in parallel)
- **Human Review Required:** Yes - review each test fix

## TASK-010: Add docs consistency check integration

- **Goal:** Integrate audit check into existing docs consistency validation
- **Scope:** Extend `scripts/validate_docs_consistency.py`
- **Inputs:** Audit tool, existing validation script
- **Outputs:** Extended validation script with audit checks
- **Dependencies:** TASK-001, TASK-002, TASK-003, TASK-004
- **Acceptance Criteria:**
  - Add check for new placeholder tests
  - Add check for undocumented coverage omit entries
  - Add warning for acceptance count drift
  - Fail on severe regressions (configurable)
  - Maintain backward compatibility with existing checks
- **Tests:**
  - Run extended validation script
  - Test failure on new placeholder
  - Test warning on count drift
- **Files likely touched:** `scripts/validate_docs_consistency.py`
- **Risk:** Low - extending existing script
- **Parallelizable:** No
- **Human Review Required:** Yes - review integration approach

## Execution Order

1. TASK-001 (skeleton)
2. TASK-002 (AST scanning)
3. TASK-003 (pattern detection)
4. TASK-004 (JSON output)
5. TASK-005 (Markdown output)
6. TASK-006 (standards doc) - parallel with TASK-007
7. TASK-007 (first audit) - parallel with TASK-006
8. TASK-008 (self-tests)
9. TASK-009 (remediation)
10. TASK-010 (docs integration)

## Current Status

As of 2026-06-05, TASK-001 through TASK-008 and TASK-010 are implemented for the report-only audit phase. TASK-009 remains open and is now expanded in `docs/testing/test-completion-plan-2026-06-05.md`.

Completed:

- Audit tool runs successfully on the full test suite.
- JSON and Markdown reports can be generated.
- Test quality standards are documented.
- First audit snapshot exists at `docs/testing/test-intent-audit-2026-06-05.md`.
- Docs consistency check includes test-quality audit integration.
- Audit tool self-tests cover placeholder, class-based collection, async tests, construction-only tests, mock-only tests, undocumented skips, syntax errors, and collection failures.

Open:

- High-risk weak tests are identified but not fully remediated.
- Strict-mode CI gate is available but should not become the default until P0 findings are fixed.
- Baseline/ratcher policy still needs a decision if the project wants to fail only on new weak tests.

## Definition of Done For Full Test Completion

- P0 security/audit no-assertion findings are zero.
- P1 daily-driver TUI, TUI chat, and agent-mode weak tests have behavior assertions or documented false-positive rationale.
- Integration no-assertion tests in the P2 queue have schema, replay, rate-limit, or notification assertions.
- `python3 scripts/validate_docs_consistency.py` passes.
- `python3 scripts/validate_docs_consistency.py --test-quality-mode strict` passes or fails only on documented non-P0 baseline debt during the rollout period.
- All edited test files pass under targeted pytest.
- Human review completed for strict-mode gate activation.
