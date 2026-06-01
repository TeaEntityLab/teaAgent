# Run Store Module Spec

## Purpose

The run store is the durable record of agent work. It connects run ids to tasks, audit
events, statuses, approvals, changed files, and evidence.

## Responsibilities

- Store run lifecycle events.
- Summarize recent runs.
- Support review and resume flows.
- Preserve enough context for continuity.
- Surface corrupt or unreadable run state.

## Contracts

- A run id must map to a task or an explicit corrupted/missing state.
- Resume requires stored task and observations.
- Review requires changed-file and audit evidence.
- Corrupt run JSON should appear as degraded health, not disappear.

## Non-responsibilities

- Deciding model/provider behavior.
- Approving tool calls.
- Hiding corrupt files to keep output clean.

## Open risks

- `summarize()` can return `None` on JSON errors.
- `list_runs()` can filter out corrupt runs.
- Suspend paths may not store enough context for resume.
