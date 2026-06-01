# ADR 0024: Automated Memory Invalidation

## Status

Accepted and Implemented - 2026-05-29

## Context

The TeaAgent memory system required automated invalidation mechanisms to prevent memory poisoning and ensure that failure cards remain relevant as the codebase evolves. The initial memory system (ADR 0001 Post-Implementation) provided basic failure card storage and manual curation, but lacked:

1. **Automated invalidation rules** - No automatic invalidation when target files change
2. **File signature tracking** - No detection of file modifications that invalidate memory
3. **Conservative default rules** - No pre-configured rules for common invalidation scenarios
4. **Per-project customization** - No support for project-specific invalidation rules
5. **CLI integration** - No CLI commands for automated invalidation
6. **Memory hygiene enforcement** - No TTL expiration or automatic cleanup

These gaps created operational risks where failure cards could become stale, memory could accumulate irrelevant observations, and there was no mechanism to ensure memory hygiene without manual intervention.

## Decision

Implement automated memory invalidation with conservative default rules, file signature tracking, per-project customization, and CLI integration:

### Core Components

#### 1. AutoInvalidationRule System

**Implementation:**
- Extended `FailureCardStorage` with `AutoInvalidationRule` and `MemoryAutoInvalidationConfig`
- Implemented conservative default rules for common scenarios
- Added `apply_auto_invalidation()` method with file signature tracking
- Support for per-project custom rules via `.teaagent/config.json`

**Files:**
- `teaagent/memory/failure_card.py` (186 lines added)

**Features:**
- Conservative default rules (file_signature_change, test_refactor, dependency_version_change)
- File signature tracking for detecting modifications
- Per-project custom rules via configuration
- Configurable invalidation actions (invalidate, warn, ignore)

**Default Rules:**
- **file_signature_change**: Invalidate when target file signature changes
- **test_refactor**: Warn when test files are modified
- **dependency_version_change**: Warn when dependency versions change

**Rule Structure:**
```python
@dataclass
class AutoInvalidationRule:
    name: str
    pattern: str  # File pattern to match
    action: InvalidationAction  # invalidate, warn, ignore
    confidence_threshold: float = 0.5  # Minimum confidence to trigger
```

#### 2. File Signature Tracking

**Implementation:**
- File signature calculation using SHA-256 hashing
- Signature storage in failure card metadata
- Automatic signature comparison on invalidation check
- Efficient signature caching for performance

**Features:**
- SHA-256 hashing for file signatures
- Signature storage in failure card metadata
- Automatic signature comparison
- Signature caching for performance

**Signature Structure:**
```python
@dataclass
class FileSignature:
    file_path: str
    signature: str  # SHA-256 hash
    last_modified: datetime
    size: int
```

#### 3. MemoryAutoInvalidationConfig

**Implementation:**
- Configuration for automated invalidation behavior
- Support for enabling/disabling automated invalidation
- Configurable confidence thresholds
- TTL expiration rules

**Configuration:**
```python
@dataclass
class MemoryAutoInvalidationConfig:
    enabled: bool = True
    default_action: InvalidationAction = InvalidationAction.INVALIDATE
    confidence_threshold: float = 0.5
    ttl_hours: int = 720  # 30 days
    custom_rules: List[AutoInvalidationRule] = field(default_factory=list)
```

#### 4. CLI Integration

**Implementation:**
- Added `teaagent memory failures auto-invalidate` CLI command
- Added `teaagent memory failures prune --max-age-hours` CLI command
- Integration with existing memory curation commands
- Support for dry-run mode

**Files:**
- `teaagent/cli/_handlers/_memory.py` (31 lines added)
- `teaagent/cli/_memory_parsers.py` (6 lines added)

**CLI Commands:**
- `teaagent memory failures auto-invalidate` - Apply automated invalidation rules
- `teaagent memory failures prune --max-age-hours 168` - Clean up old failure cards
- `teaagent memory failures review --confidence <threshold>` - Review failure cards by confidence
- `teaagent memory failures invalidate <card_id>` - Manually invalidate specific card

**Features:**
- Automated invalidation with configurable rules
- Manual prune command for cleanup
- Confidence-based filtering
- Dry-run mode for preview

#### 5. Per-Project Customization

**Implementation:**
- Support for custom invalidation rules in `.teaagent/config.json`
- Project-specific rule overrides
- Rule priority and conflict resolution
- Configuration validation

**Configuration Format:**
```json
{
  "memory_auto_invalidation": {
    "enabled": true,
    "default_action": "invalidate",
    "confidence_threshold": 0.5,
    "ttl_hours": 720,
    "custom_rules": [
      {
        "name": "custom_rule",
        "pattern": "src/**/*.py",
        "action": "invalidate",
        "confidence_threshold": 0.7
      }
    ]
  }
}
```

#### 6. Governance Fuzz Tests

**Implementation:**
- Comprehensive adversarial fuzz tests in `tests/test_governance_fuzz.py`
- Tests for automated memory invalidation
- Validates conservative defaults and path filtering
- Tests for rule evaluation and signature tracking

**Files:**
- `tests/test_governance_fuzz.py` (381 lines)

**Test Coverage:**
- Automated invalidation rule evaluation
- File signature tracking and comparison
- Per-project custom rules
- CLI command integration
- Memory hygiene enforcement

### Configuration

**MemoryAutoInvalidationConfig:**
```python
@dataclass
class MemoryAutoInvalidationConfig:
    enabled: bool = True
    default_action: InvalidationAction = InvalidationAction.INVALIDATE
    confidence_threshold: float = 0.5
    ttl_hours: int = 720  # 30 days
    custom_rules: List[AutoInvalidationRule] = field(default_factory=list)
```

**InvalidationAction:**
```python
class InvalidationAction(Enum):
    INVALIDATE = "invalidate"  # Immediately invalidate matching cards
    WARN = "warn"  # Log warning but keep card
    IGNORE = "ignore"  # No action
```

**Default Rules:**
```python
DEFAULT_RULES = [
    AutoInvalidationRule(
        name="file_signature_change",
        pattern="**/*",
        action=InvalidationAction.INVALIDATE,
        confidence_threshold=0.5
    ),
    AutoInvalidationRule(
        name="test_refactor",
        pattern="tests/**/*.py",
        action=InvalidationAction.WARN,
        confidence_threshold=0.7
    ),
    AutoInvalidationRule(
        name="dependency_version_change",
        pattern="pyproject.toml",
        action=InvalidationAction.WARN,
        confidence_threshold=0.8
    )
]
```

## Implementation Timeline

**2026-05-29 09:10:36 +0800** - Implement governance hardening decisions
- Commit: `47e969bf1448db445ef8636d85b4f4117cecb666`
- Files: memory/failure_card.py, CLI handlers/parsers
- Tests: Governance fuzz tests for memory invalidation

**2026-05-29 09:39:35 +0800** - Wire centralized approval queue into subagents and CI governance gate
- Commit: `7f24de2a1c30e774373efe401728a6584ff8f097`
- Files: Enhanced CLI handlers, documentation
- Tests: Integration tests for memory invalidation

## Git History

**Key Commits:**
- `47e969bf1448db445ef8636d85b4f4117cecb666` (2026-05-29 09:10:36) - "Implement governance hardening decisions: centralized approval queue, strict plan-before-write, and automated memory invalidation"
- `7f24de2a1c30e774373efe401728a6584ff8f097` (2026-05-29 09:39:35) - "Wire centralized approval queue into subagents and CI governance gate"

**Implementation Files:**
- `teaagent/memory/failure_card.py` - AutoInvalidationRule system (186 lines added)
- `teaagent/cli/_handlers/_memory.py` - CLI handlers (31 lines added)
- `teaagent/cli/_memory_parsers.py` - CLI parsers (6 lines added)

**Test Files:**
- `tests/test_governance_fuzz.py` - Governance fuzz tests (381 lines)
- `tests/test_tranche_bc_governance.py` - Tranche B/C governance tests (22 lines)

## Consequences

**Positive:**
- Automated invalidation prevents memory poisoning
- Conservative default rules for common scenarios
- File signature tracking detects modifications
- Per-project customization supports diverse workflows
- CLI integration enables automated memory hygiene
- Comprehensive test coverage (403 lines of tests)

**Negative:**
- Increased complexity in memory management
- Additional computational overhead for signature tracking
- Conservative defaults may invalidate too aggressively
- Per-project configuration requires documentation
- TTL expiration may remove useful memory

**Risk:**
- Low - automated memory invalidation affects memory hygiene only
- Mitigated by comprehensive unit and fuzz tests
- Conservative defaults with configurable thresholds
- Per-project customization for diverse workflows
- Dry-run mode for preview before execution

## Alternatives Considered

1. **Keep manual memory curation only** - Rejected due to operational overhead
2. **Implement only TTL expiration without rules** - Rejected as incomplete coverage
3. **Use external memory hygiene framework** - Rejected as over-engineering
4. **Defer automated invalidation to later phases** - Rejected as operational risk for memory hygiene

## References

- [ADR 0001: P0 Agent Harness Framework](0001-p0-framework.md) (Post-Implementation section)
- [ADR 0009: 5-Loop Governance System](0009-5-loop-governance-system.md)
- [Governance Hardening Plan](../plans/governance-hardening.md)
- [Architecture - Loop 4: Memory / Failure Loop](../architecture.md#loop-4-memory--failure-loop-curation--warning-injection)

## Verification Commands

```bash
# Memory invalidation tests
pytest tests/test_governance_fuzz.py -v
pytest tests/test_tranche_bc_governance.py -v

# Memory tests
pytest tests/test_memory.py -v
pytest tests/test_failure_card.py -v

# CLI commands
teaagent memory failures auto-invalidate
teaagent memory failures prune --max-age-hours 168
teaagent memory failures review --confidence 0.7
teaagent memory failures invalidate <card_id>

# Selftest
teaagent selftest --root .
```

## Post-Implementation Notes (2026-05-29)

Automated memory invalidation is now fully implemented with conservative default rules, file signature tracking, per-project customization, and CLI integration. The system prevents memory poisoning by automatically invalidating failure cards when target files change, with configurable rules and confidence thresholds. Per-project customization supports diverse workflows, and CLI integration enables automated memory hygiene. Remaining work includes monitoring invalidation performance and optimizing signature tracking overhead.
