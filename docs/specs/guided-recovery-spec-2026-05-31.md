# Guided Recovery Technical Specification

**Status:** Draft
**Priority:** P0
**Size:** Medium (1-2 weeks)
**Acceptance Test:** `test_guided_recovery_flow.py`

---

## Problem Statement

When a TeaAgent run fails or completes partially, the operator must manually decide what to do next:
- Should they undo the changes?
- Should they resume from a checkpoint?
- Should they inspect the audit log?
- Should they retry with a safer permission mode?

Currently, there is no guidance on which recovery action is appropriate for the specific failure scenario. This leads to:
- Operator confusion
- Suboptimal recovery choices
- Potential data loss or wasted time

---

## Requirements

### Functional Requirements

1. **Failure Classification**
   - Analyze run status and audit events to classify the failure type
   - Categories: tool failure, approval denied, budget exceeded, timeout, permission error, partial success

2. **Recovery Strategy Selection**
   - Recommend the most appropriate recovery action based on failure type
   - Strategies: undo, resume, inspect audit, retry with safer mode, manual intervention

3. **Guidance Display**
   - Display recovery suggestions to the operator after failed/partial runs
   - Include reasoning for the recommendation
   - Provide the exact command to execute the recommended action

4. **Integration with Existing Recovery**
   - Integrate with existing `UndoJournal` for undo recommendations
   - Integrate with existing `agent resume` for resume recommendations
   - Integrate with existing audit log for inspection recommendations

### Non-Functional Requirements

1. **Performance**: Failure analysis should complete within 1 second for typical runs
2. **Accuracy**: Recovery recommendations should be correct 90%+ of the time
3. **Safety**: Recommendations should never suggest destructive actions without warning
4. **Clarity**: Recommendations should be understandable by non-expert operators

---

## Architecture Design

### Components

```
┌─────────────────┐
│  RunResult      │
│  (status,       │
│   error, audit) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ FailureAnalyzer │
│ - classify()    │
│ - analyze()     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│RecoverySelector │
│ - select()      │
│ - rank()        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ RecoveryAdvice  │
│ - strategy      │
│ - reasoning     │
│ - command       │
└─────────────────┘
```

### Data Structures

```python
@dataclass
class FailureType:
    """Classification of a run failure."""
    category: FailureCategory  # enum
    severity: FailureSeverity  # enum
    recoverable: bool
    tool_name: Optional[str] = None
    error_message: Optional[str] = None

@dataclass
class RecoveryStrategy:
    """A recovery action that can be taken."""
    name: str  # "undo", "resume", "inspect", "retry", "manual"
    command_template: str  # e.g., "teaagent undo --run {run_id}"
    requires_confirmation: bool
    destructive: bool

@dataclass
class RecoveryAdvice:
    """Recommended recovery action with reasoning."""
    strategy: RecoveryStrategy
    reasoning: str
    confidence: float  # 0.0 to 1.0
    alternatives: list[RecoveryStrategy]
```

### Enums

```python
class FailureCategory(Enum):
    TOOL_FAILURE = "tool_failure"
    APPROVAL_DENIED = "approval_denied"
    BUDGET_EXCEEDED = "budget_exceeded"
    TIMEOUT = "timeout"
    PERMISSION_ERROR = "permission_error"
    PARTIAL_SUCCESS = "partial_success"
    UNKNOWN = "unknown"

class FailureSeverity(Enum):
    LOW = "low"  # recoverable without data loss
    MEDIUM = "medium"  # recoverable with potential minor data loss
    HIGH = "high"  # requires manual intervention
    CRITICAL = "critical"  # data loss likely
```

---

## API Design

### FailureAnalyzer

```python
class FailureAnalyzer:
    """Analyzes run results to classify failures."""

    def __init__(self, audit_logger: AuditLogger):
        self._audit = audit_logger

    def classify(self, result: RunResult) -> FailureType:
        """Classify the failure type from run result and audit events."""
        # Implementation logic
        pass

    def analyze(self, result: RunResult) -> dict:
        """Return detailed analysis including tool failures, errors, etc."""
        # Implementation logic
        pass
```

### RecoverySelector

```python
class RecoverySelector:
    """Selects appropriate recovery strategies based on failure type."""

    def __init__(self, undo_journal: Optional[UndoJournal] = None):
        self._undo_journal = undo_journal
        self._strategy_matrix = self._build_strategy_matrix()

    def select(self, failure: FailureType) -> RecoveryAdvice:
        """Select the best recovery strategy for the failure."""
        # Implementation logic
        pass

    def rank(self, failure: FailureType) -> list[RecoveryStrategy]:
        """Rank all applicable recovery strategies."""
        # Implementation logic
        pass

    def _build_strategy_matrix(self) -> dict[FailureCategory, list[RecoveryStrategy]]:
        """Build the failure-to-strategy mapping."""
        # Implementation logic
        pass
```

### RecoveryAdviceFormatter

```python
class RecoveryAdviceFormatter:
    """Formats recovery advice for display to the operator."""

    def format(self, advice: RecoveryAdvice) -> str:
        """Format advice as human-readable text."""
        # Implementation logic
        pass

    def format_json(self, advice: RecoveryAdvice) -> dict:
        """Format advice as JSON for programmatic use."""
        # Implementation logic
        pass
```

---

## Strategy Matrix

| Failure Category | Primary Strategy | Secondary Strategies | Reasoning |
|------------------|------------------|----------------------|-----------|
| TOOL_FAILURE | inspect | undo, retry | Inspect audit to understand tool failure, then undo or retry |
| APPROVAL_DENIED | inspect | manual | Inspect why denied, manual intervention may be needed |
| BUDGET_EXCEEDED | manual | resume with lower budget | Budget is hard limit, manual intervention required |
| TIMEOUT | resume | retry with longer timeout | Resume from checkpoint, retry with more time |
| PERMISSION_ERROR | retry with safer mode | manual | Permission mode too permissive, retry with stricter mode |
| PARTIAL_SUCCESS | undo | manual | Some work completed, undo to clean state |
| UNKNOWN | inspect | manual | Unknown failure, inspect audit for clues |

---

## Implementation Phases

### Phase 1: Core Failure Classification (Week 1)

**Goal:** Implement `FailureAnalyzer` to classify run failures

**Tasks:**
1. Create `FailureType`, `FailureCategory`, `FailureSeverity` dataclasses
2. Implement `FailureAnalyzer.classify()` method
3. Add unit tests for failure classification
4. Integrate with existing `RunResult` and `AuditLogger`

**Acceptance:**
- All failure categories can be classified correctly
- Unit tests cover all failure scenarios
- Classification completes within 1 second

### Phase 2: Recovery Strategy Selection (Week 1-2)

**Goal:** Implement `RecoverySelector` to recommend recovery actions

**Tasks:**
1. Create `RecoveryStrategy`, `RecoveryAdvice` dataclasses
2. Implement strategy matrix mapping
3. Implement `RecoverySelector.select()` method
4. Add unit tests for strategy selection
5. Integrate with existing `UndoJournal` and resume functionality

**Acceptance:**
- All failure categories have at least one recovery strategy
- Strategy selection is deterministic and testable
- Recommendations match strategy matrix

### Phase 3: Display Integration (Week 2)

**Goal:** Display recovery advice to operators after failed runs

**Tasks:**
1. Implement `RecoveryAdviceFormatter`
2. Integrate advice display into CLI (`agent run` output)
3. Integrate advice display into TUI
4. Add acceptance test `test_guided_recovery_flow.py`

**Acceptance:**
- Recovery advice displays after failed runs in CLI
- Recovery advice displays after failed runs in TUI
- Acceptance test verifies end-to-end flow

---

## Integration Points

### Existing Undo Functionality

**File:** `teaagent/run_undo.py`
**Class:** `UndoJournal`
**Integration:** Pass `UndoJournal` instance to `RecoverySelector` to check if undo is available

```python
undo_journal = UndoJournal(root=workspace_root, path=journal_path)
selector = RecoverySelector(undo_journal=undo_journal)
```

### Existing Resume Functionality

**Command:** `agent resume <run_id>`
**Integration:** Generate resume command in recovery advice

```python
strategy = RecoveryStrategy(
    name="resume",
    command_template="agent resume {run_id} --root {root}",
    requires_confirmation=True,
    destructive=False
)
```

### Existing Audit Log

**File:** `teaagent/audit.py`
**Class:** `AuditLogger`
**Integration:** Pass `AuditLogger` instance to `FailureAnalyzer` for event analysis

```python
analyzer = FailureAnalyzer(audit_logger=audit_logger)
```

---

## Acceptance Criteria

### Unit Tests

1. `test_failure_classifier_tool_failure()`
2. `test_failure_classifier_approval_denied()`
3. `test_failure_classifier_budget_exceeded()`
4. `test_failure_classifier_timeout()`
5. `test_failure_classifier_permission_error()`
6. `test_failure_classifier_partial_success()`
7. `test_recovery_selector_undo_available()`
8. `test_recovery_selector_resume_available()`
9. `test_recovery_selector_inspect_fallback()`
10. `test_strategy_matrix_completeness()`

### Acceptance Test

**File:** `tests/acceptance/test_guided_recovery_flow.py`

**Scenario:** Failed run displays recovery advice

```python
def test_guided_recovery_flow(tmp_path: Path) -> None:
    # 1. Run a task that fails
    # 2. Verify recovery advice is displayed
    # 3. Verify advice includes strategy, reasoning, and command
    # 4. Verify command is executable
    # 5. Verify executing command performs the recovery action
```

---

## Open Questions

1. **False Positives:** What if the recovery recommendation is wrong? Should operators be able to override?
   - **Decision:** Always show alternatives, require confirmation for destructive actions

2. **Multiple Failures:** What if a run has multiple failure types?
   - **Decision:** Classify as the highest-severity failure, show all in analysis

3. **No Recovery Available:** What if no recovery strategy applies?
   - **Decision:** Default to "inspect audit" with manual intervention recommendation

4. **TUI Integration:** How should recovery advice be displayed in the TUI?
   - **Decision:** Add a "Recovery" panel or modal after failed runs

---

## Dependencies

### Existing Components
- `teaagent/run_undo.py` - `UndoJournal` class
- `teaagent/audit.py` - `AuditLogger` class
- `teaagent/cli/_handlers/_agent.py` - resume command
- `teaagent/runner/_core.py` - `RunResult` class

### New Components
- `teaagent/recovery.py` - New module for recovery functionality
- `tests/test_recovery.py` - Unit tests
- `tests/acceptance/test_guided_recovery_flow.py` - Acceptance test

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Incorrect recovery recommendation | Medium | Medium | Show alternatives, require confirmation, operator can override |
| Performance degradation on large audit logs | Low | Low | Cache analysis results, limit event processing |
| Integration conflicts with existing undo/resume | Low | Medium | Thorough integration testing, use existing APIs |
| Operator confusion from too many options | Medium | Low | Show primary recommendation prominently, hide alternatives |

---

## Success Metrics

1. **Accuracy:** Recovery recommendations are correct 90%+ of the time (measured by operator feedback)
2. **Adoption:** Operators follow recovery recommendations 80%+ of the time
3. **Time to Recovery:** Average time from failure to recovery action decreases by 30%
4. **Operator Satisfaction:** Operator satisfaction survey score > 4/5

---

**Spec Author:** Devin AI
**Created:** 2026-05-31
**Status:** Draft - Ready for review
