# Test Quality Standards

This document defines what counts as a meaningful test across different test categories in the TeaAgent project.

## Purpose

Test quality standards ensure that tests provide actual verification of behavior rather than false confidence through weak assertions or placeholders.

## General Principles

1. **Tests must verify behavior, not construction**
   - Bad: `assert obj is not None`
   - Good: `assert obj.method() == expected_value`

2. **Tests must have clear intent**
   - Every test should have a docstring explaining what it verifies
   - Test names should describe the scenario being tested

3. **Tests should be independent**
   - Each test should be runnable in isolation
   - Tests should not depend on execution order

4. **Tests should be deterministic**
   - No random data without seeded fixtures
   - No time-dependent assertions without mocking

## Unit Test Standards

Unit tests verify individual functions, classes, or modules in isolation.

### Requirements

- **Scope**: Test a single unit of code (function, method, class)
- **Isolation**: Use mocks to external dependencies
- **Assertions**: Minimum 1 meaningful assertion per test
- **Docstring**: Required for non-trivial tests

### Meaningful Unit Test

```python
def test_audit_logger_records_event_with_unique_id():
    """Test that AuditLogger assigns unique event IDs to each record."""
    logger = AuditLogger(path=tmp_path / 'audit.jsonl')
    logger.record('test_event', 'run-1', key='value')

    event_ids = [e.event_id for e in logger.events]
    assert len(event_ids) == len(set(event_ids)), 'event IDs must be unique'
```

### Weak Unit Test (Anti-Pattern)

```python
def test_audit_logger_constructs():
    """Test that AuditLogger can be constructed."""
    logger = AuditLogger(path='/tmp/test.jsonl')
    assert logger is not None  # Only verifies construction, not behavior
```

## Integration Test Standards

Integration tests verify interactions between multiple components.

### Requirements

- **Scope**: Test cross-component interactions (e.g., CLI → handler → service)
- **Real dependencies**: Use real implementations where practical, mocks only for external services
- **Assertions**: Minimum 2 assertions (setup + behavior verification)
- **Docstring**: Required with clear interaction description

### Meaningful Integration Test

```python
def test_cli_init_creates_config_and_agents_md(tmp_path):
    """Test that CLI init creates both config.json and AGENTS.md."""
    exit_code = main(['init', '--root', str(tmp_path), '--provider', 'gpt', '--api-key', 'sk-test'])

    assert exit_code == 0
    assert (tmp_path / '.teaagent' / 'config.json').exists()
    assert (tmp_path / 'AGENTS.md').exists()
```

### Weak Integration Test (Anti-Pattern)

```python
def test_cli_init_runs():
    """Test that CLI init command runs without error."""
    exit_code = main(['init', '--root', str(tmp_path)])
    assert exit_code == 0  # No verification of side effects
```

## Acceptance Test Standards

Acceptance tests verify user-facing workflows and end-to-end scenarios.

### Requirements

- **Scope**: Test complete user workflows from CLI/TUI/API to outcome
- **Real environment**: Use real filesystem, real CLI, real TUI where possible
- **Assertions**: Minimum 3 assertions covering setup, execution, and outcome
- **Docstring**: Required with structured acceptance criteria
- **User-facing**: Must verify behavior visible to users, not internal state

### Meaningful Acceptance Test

```python
"""AC-NEW-13: Audit log integrity flow.

Acceptance criteria:
- Every event written by AuditLogger is valid JSON parseable individually.
- Event IDs are unique within a run.
- Events are ordered by creation (monotonic event stream).
"""

def test_each_audit_line_is_valid_json(tmp_path):
    log_path = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log_path)
    audit.record('run_started', 'run-001', task='test')

    lines = log_path.read_text(encoding='utf-8').strip().splitlines()
    assert len(lines) == 1
    obj = json.loads(line)
    assert 'event_type' in obj
    assert 'run_id' in obj
```

### Weak Acceptance Test (Anti-Pattern)

```python
def test_audit_flow():
    """Test audit flow works."""
    run_audit_flow()
    assert True  # Placeholder with no verification
```

## Security Test Standards

Security tests verify security boundaries, auth, permissions, and data protection.

### Requirements

- **Scope**: Test security-critical paths (auth, permissions, audit, encryption)
- **Threat modeling**: Tests should map to specific threat scenarios
- **Assertions**: Must verify both positive (allowed) and negative (blocked) cases
- **Docstring**: Required with threat scenario description
- **High priority**: Security tests are P0 tier

### Meaningful Security Test

```python
def test_policy_denies_write_to_protected_git_directory(tmp_path):
    """Test that policy.yaml deny rules block writes to .git directory."""
    policy = Policy(rules=[DenyRule(pattern='.git/*')])
    result = policy.check_permission(WriteAction(path='.git/config'))

    assert result.allowed is False
    assert result.reason == 'deny_rule_match'
```

### Weak Security Test (Anti-Pattern)

```python
def test_security_blocks_bad_paths():
    """Test that security blocks bad paths."""
    assert security_check('.git') == False  # No verification of which rule blocked it
```

## UX/TUI Test Standards

UX/TUI tests verify user interface behavior, rendering, and interaction flows.

### Requirements

- **Scope**: Test TUI rendering, command loops, user input handling
- **Headless where possible**: Use headless TUI mode for CI compatibility
- **Assertions**: Verify rendered output, state transitions, and user-visible changes
- **Docstring**: Required with user scenario description
- **Smoke tests acceptable**: Full coverage not required for UI rendering

### Meaningful TUI Test

```python
def test_tui_daily_command_shows_cockpit(tmp_path, mock_tui):
    """Test that TUI daily command renders cockpit with pending approvals."""
    mock_tui.run_command('daily')

    assert 'Cockpit' in mock_tui.rendered_output
    assert 'Pending Approvals' in mock_tui.rendered_output
```

### Weak TUI Test (Anti-Pattern)

```python
def test_tui_daily_runs():
    """Test that TUI daily command runs."""
    tui.run_command('daily')
    assert True  # No verification of rendered output
```

## Weak Test Anti-Patterns

### 1. Placeholder Tests

```python
def test_feature_coming_soon():
    pass  # No implementation
```

**Fix**: Implement the test or remove it.

### 2. Construction-Only Tests

```python
def test_object_creates():
    obj = MyClass()
    assert obj is not None
```

**Fix**: Add behavior verification:
```python
def test_object_creates_and_initializes():
    obj = MyClass()
    assert obj.state == 'initialized'
```

### 3. Assert True

```python
def test_something():
    do_something()
    assert True
```

**Fix**: Add meaningful assertion:
```python
def test_something():
    result = do_something()
    assert result == expected_value
```

### 4. Mock-Only Tests

```python
def test_with_mocks():
    mock_obj = Mock()
    mock_obj.method()
    assert mock_obj.method.called  # Only verifies mock interaction, not real behavior
```

**Fix**: Add real behavior assertion or integration test.

### 5. Undocumented Skips

```python
@pytest.mark.skipIf(not LIBRARY_AVAILABLE)
def test_feature():
    ...
```

**Fix**: Document reason in docstring:
```python
@pytest.mark.skipIf(not LIBRARY_AVAILABLE, reason='library not available - cannot simulate locally')
def test_feature():
    """Test feature behavior.

    Skipped when library unavailable because the feature cannot be
    simulated without the actual library implementation.
    """
    ...
```

## Test Tier Definitions

### P0 Tests (Critical)

- First-run experience
- Policy boundaries
- Core coding loop
- Security boundaries
- Audit chain integrity

### P1 Tests (High)

- Recovery and continuity
- IDE/runtime surface reliability
- Session resume
- Background attach

### P2 Tests (Medium)

- Ecosystem compatibility
- Extended operations
- Optional features

## Skip Guidelines

Tests may be skipped only when:

1. **Optional dependencies**: The test requires a library that is not installed (e.g., cryptography, sigstore)
2. **Environment constraints**: The test requires specific environment setup (e.g., live provider conformance)
3. **Platform limitations**: The test is platform-specific and cannot run on the current platform

All skips must include:
- `reason` parameter in skip decorator
- Docstring explaining why the test cannot be simulated locally

## Coverage Omit Guidelines

Code may be omitted from coverage only when:

1. **Owner surface**: A team owns the code and has a smoke-test candidate
2. **Reason documented**: The omit ledger has a clear reason
3. **Risk assessed**: Risk level (Low/Medium/High) is documented
4. **Return milestone**: A planned return to coverage is documented
5. **Smoke test exists**: A smoke-test candidate is documented in the ledger

See `docs/governance/coverage-omit-ledger.md` for the current omit ledger.

## Audit Tool Integration

The `scripts/audit_test_quality.py` tool enforces these standards by:

- Detecting placeholder tests (no assertions)
- Detecting construction-only tests
- Detecting mock-only tests
- Detecting undocumented skips
- Flagging tests without docstrings

Run the audit:
```bash
python3 scripts/audit_test_quality.py --format markdown --output docs/testing/test-intent-audit-2026-06-05.md
```

Use `docs/testing/test-completion-plan-2026-06-05.md` as the current remediation queue. Default validation should remain report-only until P0 security/audit findings are fixed.
