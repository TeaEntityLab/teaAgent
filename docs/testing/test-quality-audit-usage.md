# Test Quality Audit Usage

## Common Scenarios

### 1. Run audit and generate Markdown report

```bash
python3 scripts/audit_test_quality.py --format markdown --output docs/testing/test-intent-audit-2026-06-05.md
```

**Success:** Report generated at specified path with summary tables, high-risk findings, and per-file metrics.

**Error:** If pytest collection fails, tool exits with error message showing collection output.

### 2. Run audit and generate JSON report

```bash
python3 scripts/audit_test_quality.py --format json --output .teaagent/test-quality-audit.json
```

**Success:** JSON file created with structured per-file metrics for programmatic consumption.

**Error:** If file write fails, tool exits with permission/path error.

### 3. Run audit with severe failure mode

```bash
python3 scripts/audit_test_quality.py --format markdown --output docs/testing/test-intent-audit-2026-06-05.md --fail-on severe
```

**Success:** Report generated, tool exits with code 1 if severe issues found.

**Error:** If severe issues found, tool exits with code 1 and lists affected files.

### 4. Run audit on specific test directory

```bash
python3 scripts/audit_test_quality.py --tests-dir tests/acceptance --format markdown --output docs/testing/acceptance-audit.md
```

**Success:** Audit limited to specified directory only.

**Error:** If directory doesn't exist, tool exits with path error.

## CLI Examples

### Basic audit (default: markdown, stdout)

```bash
python3 scripts/audit_test_quality.py
```

Output goes to stdout, suitable for quick checks.

### Full audit with both formats

```bash
python3 scripts/audit_test_quality.py --format json --output .teaagent/test-quality-audit.json
python3 scripts/audit_test_quality.py --format markdown --output docs/testing/test-intent-audit-2026-06-05.md
```

Generate both formats for different consumers.

### CI integration (report-only phase)

```bash
python3 scripts/audit_test_quality.py --format json --output .teaagent/test-quality-audit.json
# Upload artifact for review, no gate
```

### CI integration (gate phase)

```bash
python3 scripts/audit_test_quality.py --format json --output .teaagent/test-quality-audit.json --fail-on severe
# Fail PR if new severe issues introduced
```

## Success Examples

### Example 1: Healthy acceptance test

```python
"""AC-NEW-13: Audit log integrity flow.

Acceptance criteria:
- Every event written by AuditLogger is valid JSON parseable individually.
- Event IDs are unique within a run.
"""

def test_each_audit_line_is_valid_json(tmp_path):
    log_path = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log_path)
    audit.record('run_started', 'run-001', task='test')

    lines = log_path.read_text(encoding='utf-8').strip().splitlines()
    assert len(lines) == 1
    obj = json.loads(line)
    assert 'event_type' in obj
```

**Audit result:** `purpose_status: documented`, `assertion_profile: strong`, `risk_flags: []`, `recommended_action: none`

### Example 2: Construction-only test (weak)

```python
def test_audit_logger_constructs():
    logger = AuditLogger(path='/tmp/test.jsonl')
    assert logger is not None
```

**Audit result:** `purpose_status: missing`, `assertion_profile: weak (1 assert, construction-only)`, `risk_flags: [construction_only]`, `recommended_action: add behavior assertions`

### Example 3: Placeholder test (severe)

```python
def test_feature_coming_soon():
    pass
```

**Audit result:** `purpose_status: missing`, `assertion_profile: none`, `risk_flags: [placeholder]`, `recommended_action: implement or remove`

## Error Examples

### Example 1: Pytest collection failure

```bash
$ python3 scripts/audit_test_quality.py
Error: pytest collection failed
Output: tests/test_broken.py:5: error: invalid syntax
```

**Action:** Fix syntax error in test file, re-run audit.

### Example 2: Permission denied on output

```bash
$ python3 scripts/audit_test_quality.py --output /root/audit.md
Error: cannot write to /root/audit.md: Permission denied
```

**Action:** Use writable output path or run with appropriate permissions.

### Example 3: Invalid test directory

```bash
$ python3 scripts/audit_test_quality.py --tests-dir /nonexistent/tests
Error: test directory not found: /nonexistent/tests
```

**Action:** Use valid test directory path.

## Confusing Parts

### Q: Why does the audit tool use AST instead of running tests?

**A:** Running tests would be slow (minutes to hours) and could have side effects. AST analysis is fast (< 30 seconds) and safe, focusing on test structure rather than execution behavior.

### Q: What counts as "construction-only"?

**A:** Tests that only assert object construction (e.g., `assert obj is not None`, `assert type(obj) == Foo`) without verifying behavior or state changes. These pass even if the implementation is broken.

### Q: Should I fix all weak tests immediately?

**A:** No. Prioritize high-risk weak spots (security, audit chain, daily-driver paths) first. Cosmetic issues can wait. The audit report provides a prioritized remediation queue.

### Q: Can I override audit findings?

**A:** Not yet. The current tool intentionally avoids inline ignore comments because they are easy to misuse as a second bypass system. Fix the test, remove the placeholder, or add an explicit pytest skip reason when the behavior cannot be simulated locally. A future ignore mechanism should require a ticket ID, expiry date, and reviewer.

### Q: How do I add skip reasons?

**A:** Document in test docstring:

```python
@pytest.mark.skipIf(not CRYPTO_AVAILABLE, reason="cryptography not available - cannot simulate locally")
def test_encryption():
    """Test L3 encryption.

    Skipped when cryptography unavailable because encryption behavior
    cannot be simulated without the library.
    """
    ...
```

## Design Issues Revealed by Usage

### Issue 1: Mock density threshold

**Problem:** What mock density constitutes "mock-heavy"?

**Resolution:** Start with > 3 mocks per test as "mock-heavy", tune based on audit results. Some integration tests legitimately need many mocks.

### Issue 2: Dynamic test generation

**Problem:** Pytest fixtures that generate tests dynamically may not have individual test bodies in AST.

**Resolution:** Count the generator function as one test, note in report that dynamic tests may need manual review.

### Issue 3: Parametrized tests

**Problem:** `@pytest.mark.parametrize` creates multiple test cases from one function body.

**Resolution:** Count as one test in AST analysis, but note parametrization in report. Assertion counts apply to the shared body.

### Issue 4: Test inheritance

**Problem:** Test classes with inheritance may have assertions in base classes.

**Resolution:** Not implemented yet. Current AST analysis preserves class-based pytest node IDs during collection, but assertion scanning is still local to each discovered test function body.
