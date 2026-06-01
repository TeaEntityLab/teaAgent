# Permission And Approval Playbook
# As of 2026-06-02

This playbook is for users operating TeaAgent in repositories where tool authority
matters.

## Default modes

| Situation | Suggested mode | Rationale |
|-----------|----------------|-----------|
| First run in a repo | Prompt for approvals | Learn what tools and paths are requested. |
| Known safe read-only audit | Inspect/read-only | Avoid unnecessary write authority. |
| Repeated local task in narrow path | Path-scoped approvals | Grants authority without opening the whole repo. |
| Broad refactor or delete-heavy task | Prompt with human review | High blast radius. |

## Prompt mode

In prompt mode, approval is part of the product experience:

1. Read the tool name.
2. Read the path.
3. Read the operation.
4. Compare with the task.
5. Approve, reject, or ask the agent to narrow the plan.

## Path-scoped approval

Good path scopes:

- One file being edited.
- One docs directory for docs-only work.
- One generated output directory.
- A test file paired with its implementation file.

Risky path scopes:

- Repository root for a small change.
- Home directory.
- Empty path.
- Hidden config directories unless the task is explicitly about config.

## Pending approvals

Useful TUI/CLI concepts:

- `approvals pending` to inspect blocked calls.
- `approvals check <id>` to inspect one approval when supported.
- `approve <id>` only after matching the call to the task.
- `unapprove` or `revoke` when authority is no longer needed.

## Revoking approvals

Revoke when:

- The task changed.
- The path was broader than intended.
- The run was interrupted and resumed later.
- A child agent or tool requested authority outside its assigned scope.

## Unsafe shortcuts

- Do not approve destructive tools without an exact path and rollback story.
- Do not approve broad writes because a previous run was safe.
- Do not treat approval logs as optional; they are part of the audit chain.
- Do not hide "pending approval" behind a generic failed status.

## Maintainer checklist

- Approval prompts include run id, tool name, input summary, and path scope.
- Approval records are written to audit logs.
- Empty path approval is rejected or explicitly explained.
- TUI and CLI approval wording match.
