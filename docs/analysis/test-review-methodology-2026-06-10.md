# Test Review Methodology - 2026-06-10

## Overview

This document describes the methodology used for conducting reflective reviews of test suites, based on the comprehensive review of the TeaAgent test suite. This methodology can be applied to future test reviews to ensure consistent, thorough, and actionable results.

## Methodology Framework

### Phase 1: Preparation

#### 1.1 Define Review Scope

**Decision**: Sampling vs. Comprehensive Review

**Sampling Review** (Initial approach):
- Review 10-20 representative files
- Identify patterns and issues
- Create initial task list
- **Risk**: May miss scope limitations

**Comprehensive Review** (Follow-up approach):
- Review all test files in the suite
- Verify that patterns apply broadly
- Identify systematic issues
- **Benefit**: Complete picture of test suite health
- **Cost**: More time-intensive

**Recommendation**: Start with sampling to identify patterns, then verify with comprehensive review before declaring completion.

#### 1.2 Establish Review Criteria

Define what constitutes "good" tests:

**Test Organization**:
- Consistent framework usage (pytest or unittest, not both)
- Clear separation of unit/integration/acceptance tests
- Logical file naming and structure

**Test Quality**:
- Clear documentation with acceptance criteria
- Assertions with explanatory context
- Appropriate use of mocks vs. real execution
- Coverage of happy paths and edge cases

**Maintainability**:
- Shared fixtures for common patterns
- Named constants instead of magic numbers
- Cleanup verification for temporary state
- Minimal test data duplication

**Reliability**:
- Configurable timing thresholds
- No flaky timing dependencies
- Proper isolation between tests
- Deterministic results

#### 1.3 Set Up Tracking

Create task tracking document before finding issues:

**Task ID Format**: TASK-{CATEGORY}-{NUMBER}
- CATEGORY: TEST for test improvements
- NUMBER: Sequential (001, 002, etc.)

**Task Fields**:
- Status: Pending / In Progress / Completed
- Priority: High / Medium / Low
- Estimated Effort: Low / Medium / High / Very High
- Risk: None / Low / Medium / High
- Description: Clear explanation of what needs to be done
- Files Affected: List of files requiring changes
- Acceptance Criteria: Specific, measurable completion criteria
- Dependencies: Other tasks that must complete first
- Implementation: Brief description of how to implement

### Phase 2: Execution

#### 2.1 File Discovery

Use systematic file discovery:

```bash
# Find all test files
find tests/ -name "test_*.py"
find tests/ -name "*_test.py"
find tests/acceptance/ -name "*.py"
find tests/integration/ -name "*.py"
```

Categorize files:
- Unit tests: tests/test_*.py
- Integration tests: tests/integration/*.py
- Acceptance tests: tests/acceptance/*.py

#### 2.2 File Reading Strategy

Read files in batches to manage cognitive load:

**Batch 1**: Core infrastructure (conftest.py, test support files)
**Batch 2**: Integration tests (start with most critical)
**Batch 3**: Acceptance tests (end-to-end flows)
**Batch 4**: Unit tests (fixes, coverage, specialized tests)

For each file, note:
- Test framework used (pytest vs unittest)
- Number of test functions/classes
- Presence of mocks
- Documentation quality
- Assertion quality
- Cleanup verification
- Test data duplication

#### 2.3 Pattern Identification

Look for patterns across files:

**Positive Patterns** (to preserve):
- Excellent docstrings with acceptance criteria
- Good use of shared fixtures
- Comprehensive negative test coverage
- Clear assertion messages with context

**Negative Patterns** (to address):
- Inconsistent test framework usage
- Mock overuse in integration tests
- Magic numbers without constants
- Weak assertions without context
- Missing cleanup verification
- Test data duplication

#### 2.4 Claims Ledger

Track claims against observable evidence:

| Claim | Checked How | Status |
|---|---|---|
| What the artifact asserts | The observable evidence examined | asserted / verified / refuted / unverifiable |

**Status Definitions**:
- `asserted`: Only the author's word supports it (unverified)
- `verified`: Examined the evidence yourself
- `refuted`: Evidence contradicts the claim
- `unverifiable`: Cannot verify with available evidence

**Critical Rule**: Never accept reasoning or explanations as evidence. Require observable proof (test output, diffs, file contents).

#### 2.5 Severity Classification

Classify findings by severity:

**Critical**:
- Security or data-loss risk
- Tests that could pass while code fails
- Resource leaks in production

**High**:
- Likely bug or acceptance failure
- Widespread inconsistency affecting many files
- Flaky tests that cause CI failures

**Medium**:
- Maintainability issues
- Edge case gaps
- Incomplete cleanup verification
- Inconsistent documentation

**Low**:
- Minor clarity or style issues
- Naming conventions
- File organization

#### 2.6 Traceability Table

Map acceptance criteria to evidence:

| Acceptance Criteria | Artifact Evidence | Test Evidence | Status |
|---|---|---|---|
| What should work | Where it's implemented | How it's tested | Verified / Partial / Refuted |

**Status Definitions**:
- `Verified`: Evidence shows criteria met
- `Partial`: Criteria partially met
- `Refuted`: Evidence shows criteria not met

### Phase 3: Documentation

#### 3.1 Review Document Structure

Create comprehensive review document:

```markdown
# Test Code Review - {DATE}

## Review Summary
- Review Mode: Code Review (Primary), Methodology Review (Secondary)
- Scope: Description of files reviewed
- Decision: Approve / Comment / Request Changes / Reject / Human Review Required

## Findings
### Critical Issues
### High Severity Issues
### Medium Severity Issues
### Low Severity Issues

## Claims Ledger
| Claim | Checked How | Status |

## Traceability
| Acceptance Criteria | Artifact Evidence | Test Evidence | Status |

## Required Fixes
### TASK-TEST-XXX: Task Name
- Status
- Priority
- Description
- Files Affected
- Acceptance Criteria
- Dependencies
- Risk
- Implementation

## Residual Risks
1. Risk description
2. Risk description

## Sampled Files
List of files reviewed

## Review Metadata
- Date
- Reviewer
- Method
- Sample Size
- Status
```

#### 3.2 Task Document Structure

Create task tracking document:

```markdown
# Test Improvement Tasks - {DATE}

## Review Summary
Brief description of what prompted the task list

## High Priority Tasks
### TASK-TEST-XXX: Task Name
[Task details]

## Medium Priority Tasks
### TASK-TEST-XXX: Task Name
[Task details]

## Low Priority Tasks
### TASK-TEST-XXX: Task Name
[Task details]

## Task Summary
| Task ID | Priority | Status | Effort | Risk |

## Tracking
- Created
- Last Updated
- Total Tasks
- Completed
- In Progress
- Pending

## Recommended Execution Order
1. Task (priority, risk) - description
2. Task (priority, risk) - description
```

#### 3.3 Lessons Learned Document

Capture insights for future reviews:

```markdown
# Test Review Lessons Learned - {DATE}

## Overview
Summary of the review exercise

## Key Insights
1. Lesson title
   - What happened
   - Takeaway
   - Best practice
   - Anti-pattern

## Methodology Lessons
- What worked well
- What could be improved

## Anti-Patterns Identified
- Test anti-patterns
- Process anti-patterns

## Best Practices for Test Reviews
- Before starting
- During review
- After review

## Recommendations for Future Work
- Immediate actions
- Medium-term improvements
- Long-term goals
```

### Phase 4: Verification

#### 4.1 Scope Verification

After initial improvements, verify scope:

**Check**:
- Percentage of files affected by each task
- Whether patterns apply broadly or are localized
- If improvements need to be scaled up

**Example**:
- TASK-TEST-004 converted 2 files to pytest
- Comprehensive review found 200+ files still using unittest
- Conclusion: Task scope was insufficient, needs expansion

#### 4.2 Evidence Verification

Verify that claims are supported by evidence:

**For each claim**:
- Read the actual code
- Check test output if available
- Verify implementation matches description
- Don't accept explanations as proof

#### 4.3 Completion Verification

Before marking tasks complete:

**Check**:
- All acceptance criteria met
- All affected files updated
- Tests pass after changes
- No regressions introduced
- Documentation updated

### Phase 5: Decision

#### 5.1 Decision Framework

Use one of these decisions:

**Approve**:
- All critical and high issues addressed
- Test suite meets quality criteria
- No significant residual risks

**Comment**:
- Some improvements made but additional work needed
- Valid progress but scope insufficient
- Recommendations for next steps

**Request Changes**:
- Critical issues identified
- Specific changes required before approval
- Clear path to resolution

**Reject**:
- Fundamental problems with approach
- Cannot proceed without major rework
- Requires complete reconsideration

**Human Review Required**:
- Safety, privacy, financial, legal, medical stakes
- Destructive or irreversible operations
- Security or authentication issues

#### 5.2 Decision Documentation

Include rationale for decision:

**Example Comment Decision**:
```
Previous 14 tasks successfully addressed issues in sampled files,
demonstrating good progress on timing thresholds, security audit trails,
assertion messages, shared fixtures, partial unittest conversion,
filesystem security edge cases, and cleanup verification. However,
comprehensive review of 200+ files reveals improvements were limited
in scope. Test suite still has significant inconsistencies in
organization, test data duplication, magic number usage, assertion
quality, cleanup verification, and documentation. Not yet production-ready
from maintainability perspective, though sampled improvements are valid
and should be retained.
```

## Anti-Patterns to Avoid

### Process Anti-Patterns

1. **Sampling Without Verification**
   - Fixing sampled files assuming they represent the whole
   - **Mitigation**: Always verify scope with comprehensive review

2. **Task Completion Without Adoption**
   - Marking tasks complete when only sampled files fixed
   - **Mitigation**: Verify percentage of files affected

3. **Documentation Without Enforcement**
   - Creating documentation but not following it
   - **Mitigation**: Include compliance checks in review

4. **Claims Without Evidence**
   - Accepting explanations as proof
   - **Mitigation**: Use claims ledger to track observable evidence

5. **Severity Inflation**
   - Classifying minor issues as critical
   - **Mitigation**: Use clear severity definitions

### Test Anti-Patterns

1. **Mock-Heavy Integration Tests**
   - Tests claiming to be integration but using extensive mocking
   - **Detection**: Check mock usage vs. real code execution

2. **Partial Framework Migration**
   - Converting some files but not all
   - **Detection**: Count files using each framework

3. **Fixtures Without Adoption**
   - Creating fixtures but not updating tests
   - **Detection**: Check fixture usage across files

4. **Conditional Cleanup**
   - Cleanup checks that only run conditionally
   - **Detection**: Look for `if exists()` patterns

5. **Magic Numbers**
   - Hardcoded values without constants
   - **Detection**: Search for numeric literals in tests

## Tools and Techniques

### File Discovery

```bash
# Find all Python test files
find tests/ -name "*.py" -type f

# Count test files by directory
find tests/ -name "*.py" -type f | xargs dirname | sort | uniq -c

# Search for specific patterns
grep -r "unittest.TestCase" tests/
grep -r "def test_" tests/
grep -r "class Test" tests/
```

### Pattern Analysis

```bash
# Count unittest vs pytest usage
grep -l "unittest.TestCase" tests/*.py | wc -l
grep -l "def test_" tests/*.py | wc -l

# Find files with magic numbers
grep -r "assert.*[0-9]\{3,\}" tests/

# Find files with weak assertions
grep -r "assert.*==" tests/ | grep -v "#"
```

### Automated Checks

Consider creating automated checks for:
- Test framework consistency
- Missing docstrings
- Magic number usage
- Assertion quality
- Cleanup verification

## Time Estimation

Based on this review:

**Sampling Review** (10-20 files):
- Discovery: 30 minutes
- Reading: 1-2 hours
- Analysis: 1 hour
- Documentation: 1 hour
- **Total**: 3-4 hours

**Comprehensive Review** (200+ files):
- Discovery: 30 minutes
- Reading: 8-12 hours (batched)
- Analysis: 4-6 hours
- Documentation: 2-3 hours
- **Total**: 15-21 hours

**Task Implementation** (varies by task):
- Low effort: 1-2 hours
- Medium effort: 4-8 hours
- High effort: 1-2 days
- Very high effort: 3-5 days

## Continuous Improvement

### After Each Review

1. **Update Methodology**: Document what worked and what didn't
2. **Refine Criteria**: Adjust review criteria based on findings
3. **Improve Tools**: Add automated checks for patterns found
4. **Share Insights**: Document lessons learned

### Metrics to Track

- Number of files reviewed
- Issues found by severity
- Tasks created and completed
- Time spent per phase
- Percentage of files affected by each task
- Test suite quality score (if defined)

## Conclusion

This methodology provides a structured approach to conducting comprehensive test reviews. The key lessons from the TeaAgent review are:

1. **Scope Verification**: Always verify that improvements apply broadly
2. **Evidence-Based**: Require observable evidence, not just explanations
3. **Systematic Approach**: Use consistent patterns for discovery, analysis, and documentation
4. **Task Tracking**: Maintain clear task list with priorities and dependencies
5. **Continuous Learning**: Document lessons learned to improve future reviews

By following this methodology, future test reviews can be more efficient, thorough, and actionable.

## References

- Reflective Review Skill Documentation
- TeaAgent Test Review: `docs/analysis/test-code-review-2026-06-10.md`
- TeaAgent Task List: `docs/analysis/test-improvement-tasks-2026-06-10.md`
- TeaAgent Lessons Learned: `docs/analysis/test-review-lessons-learned-2026-06-10.md`
