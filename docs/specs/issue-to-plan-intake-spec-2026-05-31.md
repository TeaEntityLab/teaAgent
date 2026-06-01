# Issue-to-Plan Intake Technical Specification

**Status:** Draft
**Priority:** P0
**Size:** Large (2-3 weeks)
**Acceptance Test:** `test_issue_to_plan_acceptance_flow.py`

---

## Problem Statement

Users often paste GitHub issues, support tickets, or bug reports into the agent and expect it to:
1. Understand the issue
2. Create a plan to address it
3. Suggest a safe command to execute
4. Provide an acceptance checklist

Currently, there is no structured intake process. Users must manually:
- Parse the issue text
- Determine what needs to be done
- Create a plan
- Choose the right permission mode
- Define acceptance criteria

This leads to:
- Inconsistent issue understanding
- Missed requirements
- Unsafe execution choices
- Undefined success criteria

---

## Requirements

### Functional Requirements

1. **Issue Text Parsing**
   - Extract key information from issue text (title, description, steps to reproduce, expected behavior, actual behavior)
   - Identify issue type (bug, feature, refactor, documentation)
   - Extract affected files/components if mentioned

2. **Ambiguity Detection**
   - Analyze issue text for missing or unclear information
   - Score ambiguity on a scale (0-100, where 0 is clear and 100 is highly ambiguous)
   - Identify specific missing information (e.g., "steps to reproduce not provided")

3. **Plan Generation**
   - Generate a structured plan artifact from the issue
   - Plan should include: goal, approach, steps, affected files, risks
   - Leverage existing `PlanMode` for read-only exploration
   - Store plan in `.teaagent/plans/` directory

4. **Safe Command Suggestion**
   - Suggest a safe command to execute the plan
   - Default to read-only or prompt mode for new issues
   - Include permission mode recommendation with reasoning

5. **Acceptance Checklist Generation**
   - Generate an acceptance checklist from the plan
   - Checklist should include: functional requirements, edge cases, testing requirements
   - Checklist should be falsifiable and testable

### Non-Functional Requirements

1. **Performance**: Issue analysis should complete within 5 seconds for typical issues
2. **Accuracy**: Ambiguity detection should identify missing information 85%+ of the time
3. **Safety**: Suggested commands should default to safe permission modes
4. **Clarity**: Generated plans should be understandable by developers

---

## Architecture Design

### Components

```
┌─────────────────┐
│  Issue Text     │
│  (GitHub issue, │
│   support ticket)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ IssueParser     │
│ - parse()       │
│ - extract()     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ AmbiguityDetector │
│ - detect()      │
│ - score()       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ PlanGenerator   │
│ - generate()    │
│ - explore()     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ CommandSuggester │
│ - suggest()     │
│ - recommend_mode() │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ChecklistGenerator │
│ - generate()    │
└─────────────────┘
```

### Data Structures

```python
@dataclass
class ParsedIssue:
    """Structured representation of a parsed issue."""
    title: str
    description: str
    issue_type: IssueType  # enum
    steps_to_reproduce: Optional[list[str]]
    expected_behavior: Optional[str]
    actual_behavior: Optional[str]
    affected_files: Optional[list[str]]
    affected_components: Optional[list[str]]
    priority: Optional[str]  # from issue labels
    raw_text: str

@dataclass
class AmbiguityReport:
    """Report of ambiguity analysis."""
    score: float  # 0-100
    missing_fields: list[str]
    unclear_sections: list[str]
    confidence: float  # 0-1
    recommendations: list[str]

@dataclass
class PlanArtifact:
    """Generated plan artifact."""
    id: str  # UUID
    title: str
    goal: str
    approach: str
    steps: list[PlanStep]
    affected_files: list[str]
    risks: list[str]
    created_at: datetime
    ambiguity_score: float

@dataclass
class PlanStep:
    """A single step in the plan."""
    description: str
    command: Optional[str]
    permission_mode: str
    destructive: bool

@dataclass
class CommandSuggestion:
    """Suggested command to execute the plan."""
    command: str
    permission_mode: str
    reasoning: str
    alternatives: list[str]

@dataclass
class AcceptanceChecklist:
    """Generated acceptance checklist."""
    functional_requirements: list[str]
    edge_cases: list[str]
    testing_requirements: list[str]
    success_criteria: list[str]
```

### Enums

```python
class IssueType(Enum):
    BUG = "bug"
    FEATURE = "feature"
    REFACTOR = "refactor"
    DOCUMENTATION = "documentation"
    PERFORMANCE = "performance"
    SECURITY = "security"
    UNKNOWN = "unknown"

class AmbiguityCategory(Enum):
    MISSING_STEPS = "missing_steps"
    UNCLEAR_DESCRIPTION = "unclear_description"
    MISSING_EXPECTED = "missing_expected"
    MISSING_ACTUAL = "missing_actual"
    VAGUE_SCOPE = "vague_scope"
    NO_ISSUE_TYPE = "no_issue_type"
```

---

## API Design

### IssueParser

```python
class IssueParser:
    """Parses issue text into structured format."""

    def parse(self, text: str, source: str = "manual") -> ParsedIssue:
        """Parse issue text into structured format.

        Args:
            text: Raw issue text
            source: Source of issue (manual, github, jira, etc.)

        Returns:
            ParsedIssue with extracted fields
        """
        # Implementation logic
        pass

    def extract_github_issue(self, issue_url: str) -> ParsedIssue:
        """Fetch and parse a GitHub issue from URL."""
        # Implementation logic
        pass
```

### AmbiguityDetector

```python
class AmbiguityDetector:
    """Detects ambiguity in issue descriptions."""

    def __init__(self, llm_client: Optional[Any] = None):
        self._llm = llm_client

    def detect(self, issue: ParsedIssue) -> AmbiguityReport:
        """Detect ambiguity in parsed issue.

        Args:
            issue: Parsed issue to analyze

        Returns:
            AmbiguityReport with score and missing fields
        """
        # Implementation logic
        pass

    def score(self, issue: ParsedIssue) -> float:
        """Calculate ambiguity score (0-100)."""
        # Implementation logic
        pass
```

### PlanGenerator

```python
class PlanGenerator:
    """Generates plan artifacts from issues."""

    def __init__(self, plan_mode: PlanMode, context_gatherer: ContextGatherer):
        self._plan_mode = plan_mode
        self._context_gatherer = context_gatherer

    def generate(self, issue: ParsedIssue, workspace_root: Path) -> PlanArtifact:
        """Generate a plan artifact from the issue.

        Args:
            issue: Parsed issue
            workspace_root: Workspace root directory

        Returns:
            PlanArtifact with generated plan
        """
        # Implementation logic
        pass

    def explore(self, issue: ParsedIssue, workspace_root: Path) -> dict:
        """Explore workspace to understand context (uses PlanMode)."""
        # Implementation logic
        pass
```

### CommandSuggester

```python
class CommandSuggester:
    """Suggests safe commands to execute plans."""

    def suggest(self, plan: PlanArtifact, ambiguity_score: float) -> CommandSuggestion:
        """Suggest a command to execute the plan.

        Args:
            plan: Generated plan
            ambiguity_score: Ambiguity score from issue

        Returns:
            CommandSuggestion with command and permission mode
        """
        # Implementation logic
        pass

    def recommend_mode(self, plan: PlanArtifact, ambiguity_score: float) -> str:
        """Recommend permission mode based on plan and ambiguity."""
        # Implementation logic
        pass
```

### ChecklistGenerator

```python
class ChecklistGenerator:
    """Generates acceptance checklists from plans."""

    def generate(self, plan: PlanArtifact) -> AcceptanceChecklist:
        """Generate acceptance checklist from plan.

        Args:
            plan: Generated plan

        Returns:
            AcceptanceChecklist with requirements and criteria
        """
        # Implementation logic
        pass
```

---

## Ambiguity Detection Algorithm

### Scoring Rules

| Missing Field | Score Impact | Reason |
|---------------|--------------|--------|
| Steps to reproduce | +30 | Cannot reproduce without steps |
| Expected behavior | +20 | Cannot verify fix without expected behavior |
| Actual behavior | +20 | Cannot understand problem without actual behavior |
| Issue type | +10 | Cannot choose approach without type |
| Affected files | +10 | Cannot scope work without files |
| Clear description | +10 | Vague description leads to misunderstanding |

### Thresholds

- **0-20**: Clear - proceed with plan generation
- **21-50**: Moderate ambiguity - generate plan with warnings
- **51-80**: High ambiguity - ask for clarification before planning
- **81-100**: Critical ambiguity - refuse to plan without clarification

---

## Command Suggestion Logic

### Permission Mode Selection

| Ambiguity Score | Issue Type | Recommended Mode | Reasoning |
|-----------------|------------|-------------------|-----------|
| 0-20 | Bug | prompt | Low ambiguity, safe to prompt for approvals |
| 0-20 | Feature | prompt | Low ambiguity, safe to prompt for approvals |
| 21-50 | Bug | read-only | Moderate ambiguity, explore first |
| 21-50 | Feature | read-only | Moderate ambiguity, explore first |
| 51-80 | Any | read-only | High ambiguity, must explore first |
| 81-100 | Any | None | Too ambiguous, refuse to plan |

### Command Templates

```python
# Read-only exploration
"agent plan {plan_id} --root {root} --mode read-only"

# Prompt mode execution
"agent run '{task}' --root {root} --mode prompt --from-plan {plan_id}"

# Full mode execution (rare, only for very clear issues)
"agent run '{task}' --root {root} --mode full --from-plan {plan_id}"
```

---

## Implementation Phases

### Phase 1: Issue Parsing (Week 1)

**Goal:** Implement `IssueParser` to extract structured information from issue text

**Tasks:**
1. Create `ParsedIssue`, `IssueType` dataclasses
2. Implement `IssueParser.parse()` method
3. Implement `IssueParser.extract_github_issue()` method
4. Add unit tests for parsing various issue formats
5. Add unit tests for GitHub issue extraction

**Acceptance:**
- Can parse GitHub issues, support tickets, and manual text
- Extracts all required fields accurately
- Handles missing fields gracefully

### Phase 2: Ambiguity Detection (Week 1-2)

**Goal:** Implement `AmbiguityDetector` to score issue clarity

**Tasks:**
1. Create `AmbiguityReport`, `AmbiguityCategory` dataclasses
2. Implement ambiguity scoring algorithm
3. Implement missing field detection
4. Add unit tests for ambiguity detection
5. Add unit tests for scoring edge cases

**Acceptance:**
- Ambiguity scores are consistent and reasonable
- Missing fields are correctly identified
- Thresholds are enforced correctly

### Phase 3: Plan Generation (Week 2)

**Goal:** Implement `PlanGenerator` to create plan artifacts

**Tasks:**
1. Create `PlanArtifact`, `PlanStep` dataclasses
2. Integrate with existing `PlanMode` for exploration
3. Implement plan generation logic
4. Implement plan storage in `.teaagent/plans/`
5. Add unit tests for plan generation
6. Add unit tests for plan storage

**Acceptance:**
- Plans are generated for clear issues
- Plans leverage existing PlanMode exploration
- Plans are stored and retrievable

### Phase 4: Command Suggestion (Week 2-3)

**Goal:** Implement `CommandSuggester` to recommend safe commands

**Tasks:**
1. Create `CommandSuggestion` dataclass
2. Implement permission mode recommendation logic
3. Implement command template rendering
4. Add unit tests for command suggestion
5. Add unit tests for permission mode selection

**Acceptance:**
- Commands are safe and appropriate
- Permission modes match ambiguity and issue type
- Command templates render correctly

### Phase 5: Checklist Generation (Week 3)

**Goal:** Implement `ChecklistGenerator` to create acceptance checklists

**Tasks:**
1. Create `AcceptanceChecklist` dataclass
2. Implement checklist generation logic
3. Add unit tests for checklist generation
4. Add acceptance test `test_issue_to_plan_acceptance_flow.py`

**Acceptance:**
- Checklists are comprehensive and falsifiable
- Checklists cover functional, edge cases, and testing
- Acceptance test verifies end-to-end flow

---

## Integration Points

### Existing Plan Mode

**File:** `teaagent/plan_mode.py`
**Classes:** `PlanMode`, `ContextGatherer`
**Integration:** Use `PlanMode` for read-only exploration during plan generation

```python
from teaagent.plan_mode import PlanMode, ContextGatherer

plan_mode = PlanMode()
context_gatherer = ContextGatherer()
generator = PlanGenerator(plan_mode=plan_mode, context_gatherer=context_gatherer)
```

### Existing LLM Client

**Integration:** Use existing LLM client for ambiguity detection and plan generation

```python
from teaagent.llm import create_llm_adapter

llm = create_llm_adapter(provider="openai", model="gpt-4")
detector = AmbiguityDetector(llm_client=llm)
```

### Existing CLI

**Command:** `agent plan <plan_id>` (may need to be created)
**Integration:** Add new CLI command to execute from plan

---

## Acceptance Criteria

### Unit Tests

1. `test_issue_parser_github_issue()`
2. `test_issue_parser_manual_text()`
3. `test_issue_parser_missing_fields()`
4. `test_ambiguity_detector_clear_issue()`
5. `test_ambiguity_detector_ambiguous_issue()`
6. `test_ambiguity_detector_thresholds()`
7. `test_plan_generator_bug_issue()`
8. `test_plan_generator_feature_issue()`
9. `test_command_suggester_low_ambiguity()`
10. `test_command_suggester_high_ambiguity()`
11. `test_checklist_generator_comprehensive()`

### Acceptance Test

**File:** `tests/acceptance/test_issue_to_plan_acceptance_flow.py`

**Scenario:** User pastes an issue and gets a plan with ambiguity score, safe command, and acceptance checklist

```python
def test_issue_to_plan_acceptance_flow(tmp_path: Path) -> None:
    # 1. User pastes a GitHub issue URL or issue text
    # 2. System parses the issue
    # 3. System detects ambiguity and scores it
    # 4. System generates a plan artifact
    # 5. System suggests a safe command
    # 6. System generates an acceptance checklist
    # 7. Verify all outputs are correct and actionable
```

---

## Open Questions

1. **LLM Dependency:** Should ambiguity detection use LLM or rule-based approach?
   - **Decision:** Use rule-based for MVP, LLM for enhanced accuracy later

2. **Plan Storage Format:** Should plans be stored as JSON, Markdown, or both?
   - **Decision:** JSON for machine readability, Markdown for human readability

3. **GitHub Integration:** Should we fetch GitHub issues directly or require users to paste?
   - **Decision:** Support both: fetch from URL if provided, parse from text if pasted

4. **Plan Revision:** How should plan revisions be handled?
   - **Decision:** Out of scope for this spec, covered by Plan Review and Revision spec

---

## Dependencies

### Existing Components
- `teaagent/plan_mode.py` - `PlanMode`, `ContextGatherer` classes
- `teaagent/llm/` - LLM adapter for ambiguity detection
- `teaagent/cli/` - CLI command integration

### New Components
- `teaagent/issue_intake.py` - New module for issue parsing and plan generation
- `tests/test_issue_intake.py` - Unit tests
- `tests/acceptance/test_issue_to_plan_acceptance_flow.py` - Acceptance test

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Ambiguity detection inaccurate | Medium | Medium | Use rule-based approach first, LLM later |
| Plan generation produces poor plans | Medium | High | Require human review before execution |
| Command suggestion unsafe | Low | High | Default to read-only mode, require confirmation |
| GitHub API rate limits | Low | Low | Cache fetched issues, handle rate limits gracefully |
| Issue parsing fails on complex issues | Medium | Medium | Fallback to manual parsing, warn user |

---

## Success Metrics

1. **Accuracy:** Ambiguity detection identifies missing information 85%+ of the time
2. **Adoption:** Users use generated plans 70%+ of the time instead of manual planning
3. **Time Savings:** Average time from issue to plan decreases by 40%
4. **Safety:** 0% unsafe command suggestions (no full mode on ambiguous issues)

---

**Spec Author:** Devin AI
**Created:** 2026-05-31
**Status:** Draft - Ready for review
