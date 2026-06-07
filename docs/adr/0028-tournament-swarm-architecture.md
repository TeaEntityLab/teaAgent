# ADR 0028: Tournament and Swarm Execution

## Status

Accepted

## Context

Parallel experiment and tournament flows need git worktree isolation and comparable scoring.

## Decision

Implement tournament execution under `teaagent/tournament/` with branch isolation, parallel executor, and security-weighted scoring. Swarm orchestration reuses subagent approval queue and consensus where configured.

## Consequences

- Higher disk/git requirements for tournament runs
- Scoring must remain auditable — results logged to run store
- Coverage and integration tests required for executor paths
