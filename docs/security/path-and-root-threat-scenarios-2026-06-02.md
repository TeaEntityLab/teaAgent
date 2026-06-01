# Path And Root Threat Scenarios
# 2026-06-02

Threat scenarios around path handling and workspace root.

## Scenario PR-001: Saved root overrides explicit root

User launches from repo B with `--root B`, but saved state restores repo A.

Impact:

- Agent reads or writes wrong project.
- Approvals refer to surprising paths.
- Audit evidence is attached to wrong context.

Mitigation:

- Explicit root sentinel.
- Visible active root.
- Test saved root A vs explicit root B.

## Scenario PR-002: Parent traversal in pinned file

User or tool pins `../secret`.

Impact:

- Context can include files outside workspace.

Mitigation:

- Require relative path.
- Resolve and containment-check.
- Reject symlink escape.

## Scenario PR-003: Absolute path approval

Approval stores an absolute path that does not normalize to workspace semantics.

Impact:

- Matching may be broader or narrower than displayed.

Mitigation:

- Normalize before display and storage.
- Reject outside-workspace paths unless explicit external-resource approval exists.

## Scenario PR-004: Suffix confusion

Approval for `src/foo.py` matches `src/foo.py.bak`.

Impact:

- Write authority expands unexpectedly.

Mitigation:

- Exact path matching for files.
- Separate directory-recursive grants.
