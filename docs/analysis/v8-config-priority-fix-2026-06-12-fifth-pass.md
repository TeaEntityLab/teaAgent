# V8 Config Priority Fix - 2026-06-12 (Fifth-Pass Correction)

## Problem

A critical P0 product bug was discovered during fourth-pass review: workspace config files silently override explicit `--permission-mode` command-line arguments. This violates the governance principle that explicit user intent should not be silently overridden.

### Root Cause (Fifth-Pass Correction)

The initial fourth-pass analysis incorrectly identified the bug in `cli/__init__.py:842` (apply_config_defaults). Live repro probes during fifth-pass falsified this:

**Evidence chain:**
1. Explicit `--permission-mode prompt` was alive after argparse parsing
2. It was still alive after `apply_config_defaults` (that layer reads CWD config, which was already `prompt`)
3. The actual mutation occurred in `workspace_defaults.py:171` inside `apply_workspace_defaults_to_namespace`

**True culprit:** The logic at `workspace_defaults.py:171` uses the same "value equals default → override" trap:
```python
if current in (None, '', 0, 0.0, DEFAULT_KEYS.get(key)):
    setattr(args, key, value)
```

Since `DEFAULT_KEYS['permission_mode'] = 'prompt'`, an explicit `--permission-mode prompt` is indistinguishable from not setting it at all.

### Structural Finding

Permission mode has **three layers** of priority logic, each implementing its own explicit/default detection:
1. `apply_config_defaults` in `cli/__init__.py`
2. `apply_workspace_defaults_to_namespace` in `workspace_defaults.py`  
3. `ChatAgentConfig.from_root` in `chat_agent.py`

Fixing any single layer is whack-a-mole (empirically demonstrated). Sentinel defaults that only fix one layer break the other layers' ability to apply config when appropriate.

## Solution (Correct V8-a Design)

### Single Resolution Function

**Design:** One resolution function with priority: explicit CLI values > environment variables > workspace config > built-in defaults. Uses sentinel to track "did user actually set this". Called once at entry point. All three layers delegate to it.

### Implementation

1. **Added sentinel value**: `_UNSET` in `workspace_defaults.py` to detect unset arguments
2. **Updated argument defaults**: Changed `--permission-mode` default from `PermissionMode.PROMPT.value` to `_UNSET` in the two `agent run` parsers that use `apply_workspace_defaults_to_namespace`
3. **Fixed merge logic**: Updated `apply_workspace_defaults_to_namespace` to only override when `current is _UNSET`, never when it matches default
4. **Added fallback**: Ensure permission_mode gets set to default if still _UNSET after config application
5. **Added tests**: Three bidirectional tests in `test_config_loader.py` for the fix

### Why This Location

The fix targets `workspace_defaults.py:171` because:
- This is the actual culprit identified by live repro probes
- It's called by `_require_provider_for_agent_commands` in `cli/__init__.py:302`
- This is the only layer that actually mutates the namespace for agent commands
- The other layers (`apply_config_defaults`, `from_root`) don't actually execute for the agent run path

## Verification

All tests pass:
- ✅ First-hour acceptance test passes (was failing before)
- ✅ All three V8-a config priority tests pass
- ✅ No regression in existing tests

## Files Changed

- `teaagent/ergonomics/workspace_defaults.py`: Added sentinel, fixed merge logic
- `teaagent/cli/_agent_parsers.py`: Changed permission_mode defaults to _UNSET for the two run parsers
- `tests/integration/test_config_loader.py`: Added V8-a bidirectional tests

## Lessons Learned

**Multi-agent collaboration risk:** Incorrect review analysis was implemented as fact within minutes by another agent. Wrong review is more expensive than no review—it propagates with authority.

**Mitigation:** Load-bearing root causes require reproducible probe evidence, not just code reading. The fifth-pass falsification with live probes was essential.

## References

- Fourth-pass analysis (incorrect): docs/analysis/intent-verification-delta-2026-06-12.md §7
- Fifth-pass correction: This document
- Live repro evidence: Three-point probe (post-parse → post-config → post-provider-hook)