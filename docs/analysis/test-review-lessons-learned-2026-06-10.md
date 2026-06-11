# Test Review Lessons Learned - 2026-06-10

## Overview

This document captures the concepts, lessons, and insights learned from conducting a comprehensive reflective review of the TeaAgent test suite. These lessons are applicable to future test reviews and test suite maintenance efforts.

## Key Insights

### 1. Sampling vs. Comprehensive Review

**Lesson**: Initial sampling can identify issues, but comprehensive review reveals scope limitations.

**What Happened**:
- Initial review of ~15 test files identified 8 improvement tasks
- Follow-up review of additional files identified 6 more tasks
- Comprehensive review of 200+ files revealed that improvements were limited to ~2% of the test suite

**Takeaway**: When conducting test reviews, start with sampling to identify patterns, but verify that improvements are applied broadly across the codebase. Don't assume that fixing sampled files represents the entire suite.

### 2. Test Organization Consistency Matters

**Lesson**: Mixed test frameworks (unittest vs pytest) create maintenance burden.

**Problem Identified**:
- 200+ files still use `unittest.TestCase` class structure
- Only 2 files were converted to pytest-style functions
- Inconsistent patterns make codebase harder to navigate and extend

**Best Practice**:
- Choose one test framework and apply it consistently
- If converting, plan for large-scale refactoring (not just 1-2 files)
- Use automated tools to identify all files needing conversion

**Anti-Pattern**: Converting only a few files to a new pattern while leaving the majority unchanged.

### 3. Mock Overuse Masks Real Issues

**Lesson**: Tests that rely heavily on mocks may pass while actual functionality fails.

**Problem Identified**:
- Files named "security fixes" or "coverage" tests use unittest with mocks
- Tests verify mock behavior rather than actual integration
- Security fixes tested with tempfile/config mocks without real execution

**Best Practice**:
- Use mocks sparingly and only for external dependencies
- Prefer integration tests that exercise real code paths
- For security fixes, test actual execution when possible
- Distinguish between unit tests (with mocks) and integration tests (without mocks)

**Anti-Pattern**: Naming a test "integration" or "acceptance" when it's actually a unit test with mocks.

### 4. Magic Numbers Reduce Test Clarity

**Lesson**: Hardcoded values without named constants make tests hard to understand and maintain.

**Problem Identified**:
- Token thresholds: 150000, 200000 without explanation
- Timing values: 0.1s, 0.15s, 0.05s without named constants
- Card data values hardcoded inline

**Best Practice**:
- Extract magic numbers to named constants at module level
- Document what constants represent and why values were chosen
- Make constants configurable via environment variables for CI differences
- Group related constants together

**Example**:
```python
# Bad
assert compactor.should_compact(150000, 200000) is True

# Good
TOKEN_USAGE_THRESHOLD = 0.75  # 75% of max tokens
MAX_CONTEXT_TOKENS = 200000
threshold = int(MAX_CONTEXT_TOKENS * TOKEN_USAGE_THRESHOLD)
assert compactor.should_compact(threshold, MAX_CONTEXT_TOKENS) is True
```

### 5. Test Data Duplication Creates Maintenance Debt

**Lesson**: Inline test data duplicated across files becomes a maintenance burden.

**Problem Identified**:
- conftest.py created with 5 shared fixtures
- Most test files still use inline test data
- Schema changes require updates in many files

**Best Practice**:
- Create shared fixtures for common test patterns
- Extract frequently-used test data to conftest.py
- Use factory functions for complex test objects
- Document fixtures with clear descriptions

**Anti-Pattern**: Creating fixtures but not updating existing tests to use them.

### 6. Assertion Context Improves Debuggability

**Lesson**: Assertions without explanatory context make failures hard to diagnose.

**Problem Identified**:
- `assert cleaned == 'test'` without explaining why 'test' is expected
- `assert 'stdout' in result` without validating the content
- Assertions that accept multiple values without explaining each case

**Best Practice**:
- Add explanatory comments to assertions
- Use assertion messages that explain expected behavior
- For multiple acceptable values, document why each is acceptable
- Include relevant context in assertion failure messages

**Example**:
```python
# Bad
assert result.status == 'failed:system'

# Good
# Cancel token set before run starts should cause immediate system failure
assert result.status == 'failed:system', (
    f'expected failed:system (cancel token pre-set), got {result.status!r}'
)
```

### 7. Documentation Quality Varies Widely

**Lesson**: Inconsistent test documentation makes onboarding difficult.

**Problem Identified**:
- Some files have excellent docstrings with acceptance criteria
- Many files have minimal or no documentation
- Technical concepts sometimes explained, sometimes not

**Best Practice**:
- Standardize docstring format across test files
- Include acceptance criteria for behavior tests
- Explain technical concepts or reference documentation
- Document test purpose and what it validates

**Template**:
```python
"""Test description.

Purpose: What this test validates and why it matters.

Acceptance criteria:
- Criterion 1
- Criterion 2

Technical notes: Explanation of concepts if needed.
"""
```

### 8. Cleanup Verification Prevents Resource Leaks

**Lesson**: Inconsistent cleanup verification can cause orphaned state in test runs.

**Problem Identified**:
- Some tests verify cleanup, many don't
- Cleanup checks are sometimes conditional
- Background process files may not be cleaned up

**Best Practice**:
- Always verify cleanup after tests that create temporary state
- Make cleanup checks unconditional
- Assert that resources are cleaned up or marked terminated
- Use fixtures with automatic cleanup when possible

**Example**:
```python
# Bad
if bg_json_file.exists():
    # optional cleanup check

# Good
assert not bg_json_file.exists(), (
    f'Background file should be cleaned up, but exists at {bg_json_file}'
)
```

### 9. Negative Test Coverage Should Be Systematic

**Lesson**: Uneven negative test coverage leaves edge cases untested.

**Problem Identified**:
- Some files have comprehensive negative tests (5+ cases)
- Many files have no negative test cases
- Edge case coverage is inconsistent

**Best Practice**:
- Add negative tests for every public API
- Test malformed inputs, boundary conditions, and error cases
- Use parameterized tests for multiple negative cases
- Document what edge cases are covered and why

**Anti-Pattern**: Only testing happy paths and assuming error handling works.

### 10. Test File Organization Affects Discoverability

**Lesson**: Mixed test types in same directories make finding specific tests difficult.

**Problem Identified**:
- `tests/test_*.py` files contain both unit and integration tests
- No clear separation between test types
- Harder to find specific test categories

**Best Practice**:
- Separate unit, integration, and acceptance tests into different directories
- Use naming conventions to indicate test type
- Consider test markers/tags for categorization
- Document the test directory structure

### 11. Test Naming Should Reflect Behavior

**Lesson**: Test names that reference implementation details reduce clarity.

**Problem Identified**:
- `test_h4_shadow_wiring.py` references internal phase
- `test_phase5_jit_approval_server.py` references implementation detail
- Hard to understand test purpose from name

**Best Practice**:
- Name tests after the behavior they validate
- Avoid implementation details in test names
- Use descriptive names that explain what is being tested
- Consider the user's perspective when naming

**Example**:
```python
# Bad
def test_phase5_jit_approval_server():
    pass

# Good
def test_approval_server_handles_concurrent_requests():
    pass
```

## Methodology Lessons

### Reflective Review Process

**What Worked Well**:
1. **Claims Ledger**: Tracking claims against observable evidence prevented accepting unsupported assertions
2. **Traceability Table**: Mapping acceptance criteria to test evidence showed gaps
3. **Severity Classification**: Prioritizing findings by impact helped focus effort
4. **Task IDs**: Unique identifiers made tracking progress easier

**What Could Be Improved**:
1. **Scope Verification**: Should have verified that improvements applied broadly earlier
2. **Automated Analysis**: Could use static analysis to identify patterns across all files
3. **Progressive Sampling**: Start small, then expand to verify scope

### Task Management

**What Worked Well**:
1. **Priority Levels**: High/Medium/Low classification helped sequence work
2. **Dependencies**: Documenting dependencies between tasks prevented conflicts
3. **Effort Estimates**: Helped plan work realistically
4. **Status Tracking**: Clear status (Completed/Pending/In Progress)

**What Could Be Improved**:
1. **Scope Validation**: Should have estimated percentage of files affected per task
2. **Completion Criteria**: More specific criteria for "done" would help
3. **Rollback Planning**: Should have considered rollback for high-risk changes

## Anti-Patterns Identified

### Test Anti-Patterns

1. **Mock-Heavy Integration Tests**
   - Tests that claim to be integration but use extensive mocking
   - Risk: Passes while real code fails

2. **Partial Framework Migration**
   - Converting some files to new framework but not all
   - Risk: Inconsistent patterns, maintenance burden

3. **Fixtures Without Adoption**
   - Creating shared fixtures but not updating existing tests
   - Risk: Duplication continues, fixtures unused

4. **Conditional Cleanup**
   - Cleanup checks that only run if files exist
   - Risk: Resource leaks go undetected

5. **Magic Numbers**
   - Hardcoded values without named constants
   - Risk: Unclear intent, hard to adjust

6. **Happy Path Only**
   - Testing only success cases, no negative tests
   - Risk: Edge cases untested

### Process Anti-Patterns

1. **Sampling Without Verification**
   - Fixing sampled files assuming they represent the whole
   - Risk: Improvements limited in scope

2. **Task Completion Without Adoption**
   - Marking tasks complete when only sampled files fixed
   - Risk: False sense of progress

3. **Documentation Without Enforcement**
   - Creating documentation but not following it
   - Risk: Inconsistent practices continue

## Best Practices for Test Reviews

### Before Starting

1. **Define Scope**: Decide whether review is sampling or comprehensive
2. **Set Criteria**: Establish what constitutes "good" tests
3. **Plan Tracking**: Set up task tracking before finding issues
4. **Identify Stakeholders**: Know who will implement fixes

### During Review

1. **Use Claims Ledger**: Track claims against observable evidence
2. **Classify Severity**: Prioritize findings by impact
3. **Document Examples**: Include file paths and line numbers
4. **Estimate Effort**: Provide realistic effort estimates
5. **Identify Dependencies**: Note which tasks depend on others

### After Review

1. **Verify Scope**: Check if improvements apply broadly
2. **Update Documentation**: Keep task list current
3. **Communicate Findings**: Share results with team
4. **Plan Next Steps**: Sequence work by priority and dependencies

## Recommendations for Future Work

### Immediate Actions

1. **Complete TASK-TEST-015**: Convert remaining unittest classes to pytest
   - This is the highest priority because it affects 200+ files
   - Should be done before other large-scale changes
   - Consider automated conversion tools

2. **Expand Fixture Adoption (TASK-TEST-016)**:
   - After framework conversion, adopt shared fixtures broadly
   - Focus on most common test patterns first
   - Document fixtures clearly

### Medium-Term Improvements

1. **Replace Magic Numbers (TASK-TEST-017)**:
   - Extract constants to module level
   - Make timing thresholds configurable
   - Document constant choices

2. **Improve Assertions (TASK-TEST-018)**:
   - Add explanatory comments to all assertions
   - Standardize assertion message format
   - Include context in failure messages

### Long-Term Goals

1. **Standardize Documentation (TASK-TEST-020)**:
   - Create docstring template
   - Apply template across all test files
   - Include acceptance criteria consistently

2. **Add Negative Tests (TASK-TEST-021)**:
   - Identify files without negative tests
   - Add edge case coverage systematically
   - Use parameterized tests for efficiency

## Conclusion

This comprehensive test review revealed that while the initial 14 improvement tasks were valid and successfully implemented, they addressed only ~2% of the test suite. The broader review identified systematic issues requiring large-scale effort to resolve.

The key lesson is that test quality improvements must be applied broadly across the codebase to be effective. Sampling is useful for identifying patterns, but comprehensive review is necessary to verify scope and ensure consistent quality.

The 7 new tasks identified (TASK-TEST-015 through TASK-TEST-021) represent significant work but are necessary to achieve production-ready test maintainability. Prioritizing the high-priority unittest conversion (TASK-TEST-015) will enable the other improvements to proceed more efficiently.

## References

- Original Review: `docs/analysis/test-code-review-2026-06-10.md`
- Task List: `docs/analysis/test-improvement-tasks-2026-06-10.md`
- Reflective Review Methodology: Reflective Review skill documentation
