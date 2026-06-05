# Dynamic Skill And Long Result Work Items - 2026-06-05

## Purpose

This ledger converts the dynamic skill research, RSS case study, and competitor
value map into executable work. It should be updated when tasks move state.

Canonical states follow `docs/governance/document-state-model.md`.

## Priority Model

Ranking factors:

- User trust impact.
- Direct relation to the RSS failure.
- Risk reduction for persistent skill state.
- Testability in CI.
- Cost effectiveness.

P0 means the project should not claim dynamic skill reliability without it.

## Work Item Ledger

| ID | Priority | State | Work item | Owner surface | Dependencies | Acceptance criteria |
| --- | --- | --- | --- | --- | --- | --- |
| DSK-P0-001 | P0 | Complete | Add skill lifecycle state machine. | skills / audit | Existing `skill_load` events | Audit distinguishes discovered, indexed, selected, activated, resource-read, used-in-run, output-verified, superseded, and blocked. |
| DSK-P0-002 | P0 | Complete | Block or quarantine direct active-skill writes. | workspace tools / skill writer | DSK-P0-001 useful but not required | Writes to active skill dirs are blocked or converted into candidate proposals unless explicit dev opt-in is set. |
| DSK-P0-003 | P0 | Complete | Add offline RSS fixture acceptance test. | tests / skills | DSK-P0-001, fixture files | Test proves an RSS skill produces a source-backed markdown summary from fixture feeds. |
| DSK-P0-004 | P0 | Complete | Add long-result envelope. | tools / audit / run artifacts | Artifact storage path decision | Large RSS/WebSearch/skill outputs return preview, truncation metadata, artifact path, hash, and cursor. |
| DSK-P0-005 | P0 | Complete | Add output artifact validators for source-backed tasks. | tests / verifier | DSK-P0-003 | Validators check file existence, source URLs, known titles, categories, and prompt-injection resistance. |
| DSK-P0-006 | P0 | Complete | Add unmanaged skill explainability state. | skill loader / CLI | Existing `explain_skill_activation` | `skill explain` clearly labels candidate-installed, unmanaged direct-write, compatibility path, and shadowed skill states. |
| DSK-P0-007 | P0 | Complete | Make invalid tool-decision failure visible in skill flows. | chat agent / runner | Existing invalid JSON hardening | Dynamic skill tasks cannot return success when decision JSON is invalid before required output exists. |
| DSK-P1-001 | P1 | Complete | Add behavioral skill eval harness. | skill eval | DSK-P0-003 | Candidate eval compares with-skill vs without-skill behavior on deterministic fixtures. |
| DSK-P1-002 | P1 | Complete | Add skill invocation audit events. | audit / run store | DSK-P0-001 | Run evidence includes skill activation cause and final output artifact links. |
| DSK-P1-003 | P1 | Complete | Add explicit `activate_skill` runtime tool or command. | CLI / runner | DSK-P0-001 | User can force a skill, and audit records explicit activation. |
| DSK-P1-004 | P1 | Complete | Add TUI skill trust panel. | TUI | DSK-P0-006 | TUI shows reviewed, unmanaged, shadowed, and activated skill states. |
| DSK-P1-005 | P1 | Complete | Add long-result readback command. | CLI / workspace tools | DSK-P0-004 | User or model can read stored result artifacts by cursor/offset. |
| DSK-P1-006 | P1 | Complete | Add candidate repair loop after eval failure. | skill candidates | DSK-P1-001 | Failed candidate eval produces actionable repair tasks, not silent install. |
| DSK-P2-001 | P2 | Complete | Add built-in RSS starter skill. | skills / examples | DSK-P0-003 | Example skill passes offline RSS acceptance and documents limitations. |
| DSK-P2-002 | P2 | Complete | Add optional real-model dynamic skill eval profile. | eval / CI optional | DSK-P1-001 | Scheduled/manual profile measures real-model behavior without blocking PRs. |
| DSK-P2-003 | P2 | Complete | Add skill ecosystem health dashboard. | docs / TUI | DSK-P1-004 | Dashboard lists skill count, trust states, stale candidates, and failed evals. |

## P0 Implementation Notes

### DSK-P0-001: Skill lifecycle state machine

Intent:

- Stop using `skill_load` as the proxy for success.

Minimum state set:

- `discovered`
- `indexed`
- `selected`
- `activated`
- `resource_read`
- `candidate_proposed`
- `candidate_eval_passed`
- `review_passed`
- `installed`
- `used_in_run`
- `output_verified`
- `superseded`
- `blocked`

Implementation boundary:

- Add state vocabulary and audit payload shape.
- Do not require a full TUI panel in the first pass.

Acceptance:

- A test can assert that loaded-only skills do not become `used_in_run`.
- `skill explain` can summarize lifecycle state for a named skill.

### DSK-P0-002: Direct active-skill write quarantine

Intent:

- Prevent compatibility discovery from becoming an unreviewed persistence path.

Protected paths:

- `.config/agent/skills/**`
- `.claude/skills/**`
- `.opencode/skill/**`
- `.opencode/skills/**`

Allowed paths:

- Candidate proposal under `.teaagent/skill-candidates/**`.
- Candidate install to canonical project skill target.
- Explicit development opt-in.

Acceptance:

- Workspace write to `.opencode/skill/rss/SKILL.md` is blocked or quarantined.
- Candidate install still writes to `.config/agent/skills/rss-summary/SKILL.md`.
- Error message explains the candidate path and review command.

### DSK-P0-003: Offline RSS fixture acceptance

Intent:

- Test the exact user-visible failure without network dependency.

Fixture behavior:

- Use OPML plus multiple XML feeds.
- Include one large feed.
- Include a feed item with prompt-injection text.

Acceptance:

- Final markdown exists.
- Final markdown is source-backed.
- Known fixture titles and URLs appear.
- Injection text is quoted or ignored as content, not followed.
- Audit proves RSS skill activation.

### DSK-P0-004: Long-result envelope

Intent:

- Preserve evidence when tool output exceeds model-visible budget.

Minimum envelope:

```json
{
  "content_type": "text/markdown",
  "preview": "...",
  "truncated": true,
  "total_bytes": 123456,
  "preview_bytes": 50000,
  "artifact_path": ".teaagent/artifacts/tool-results/run-id/tool-id.txt",
  "content_hash": "sha256:...",
  "cursor": "offset:50000",
  "suggested_next_action": "read artifact_path with offset cursor"
}
```

Acceptance:

- Large fake RSS/WebSearch output stores full artifact.
- Observation includes preview and artifact pointer.
- Readback by offset works.
- Compaction keeps pointer and hash.

## P1 Implementation Notes

### Behavioral eval harness

The first harness should be deterministic.

Recommended design:

- Use fake adapters and fixture workspace.
- Run cases in `without_skill` and `with_skill` mode.
- Compare output artifacts, not just model text.
- Store result JSON under candidate eval output.

Pass criteria examples:

- Markdown includes known titles.
- JSON parses.
- Expected row count matches fixture.
- No placeholder scripts remain.
- No prompt-injection instruction is followed.

### Explicit activation UX

Potential surfaces:

- CLI: `teaagent skill activate <name>` for session config.
- Agent task syntax: explicit selected skill list.
- Model-facing tool: `activate_skill`.
- TUI: skill picker.

Default recommendation:

- Start with CLI/task-level explicit activation and audit.
- Add model-facing activation only after lifecycle audit shape is stable.

### TUI trust panel

Minimum display:

- Skill name.
- Source path.
- Governance status.
- Activation status.
- Shadowed paths.
- Last eval status.

Do not show full `SKILL.md` by default.

## Acceptance Test Matrix

| Scenario | Test type | Required result |
| --- | --- | --- |
| Load unmanaged `.opencode/skill` skill | Unit/acceptance | Explain output says unmanaged/direct-write. |
| Direct write to active skill dir | Acceptance | Blocked or quarantined with actionable message. |
| Candidate install | Acceptance | Candidate installs to canonical project path with provenance. |
| RSS fixture summary | Acceptance | Output artifact passes source-backed checks. |
| Long fake WebSearch result | Acceptance | Envelope stores full artifact and exposes cursor. |
| Skill loaded but ignored | Unit/acceptance | No `used_in_run` event emitted. |
| Explicit activation | Acceptance | Audit records user-explicit activation cause. |
| Eval failure | Unit/acceptance | Candidate stays uninstalled and repair task is emitted. |

## Documentation Follow-Up

| ID | Work | Acceptance |
| --- | --- | --- |
| DSK-DOC-001 | Update `docs/INDEX.md`. | Dynamic skill package appears under evidence, strategy, and plans. |
| DSK-DOC-002 | Update `docs/daily-driver-current-status.md`. | Users see current caveat: dynamic skills not yet verified end-to-end. |
| DSK-DOC-003 | Update `docs/roadmap-status.md`. | H3 references dynamic skill trust as next ecosystem gate. |
| DSK-DOC-004 | Update skills module docs. | Spec and risks link lifecycle and long-result work. |
| DSK-DOC-005 | Update skill governance. | Governance distinguishes candidate skills from unmanaged direct writes. |

## Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Blocking direct writes surprises power users. | Medium | Provide explicit dev opt-in and clear error messages. |
| Behavioral eval becomes flaky with real models. | High | Start deterministic; make real-model eval optional. |
| Long-result envelope breaks tool consumers. | Medium | Introduce behind shared helper and preserve current simple outputs when small. |
| Too many lifecycle states confuse users. | Medium | Use detailed states in audit; summarize in CLI/TUI. |
| RSS fixture becomes too synthetic. | Low | Include large feeds, malformed items, and injection text. |

## Immediate Sequence

1. Implement lifecycle event vocabulary and explain output semantics.
2. Add direct active-skill write guard or quarantine path.
3. Add RSS fixture files and acceptance test.
4. Add long-result envelope helper for a fake tool path.
5. Add output artifact validators.
6. Add CLI/TUI visibility after backend evidence exists.

## Definition Of Done

Dynamic skill reliability can be described as "early credible" when:

- The RSS fixture acceptance test passes.
- Direct active skill writes are controlled.
- Long results preserve full evidence.
- Skill use is auditable beyond prompt injection.
- A final output validator can fail a fake summary.

Until then, TeaAgent should say:

> Dynamic skills are structurally supported and governed, but end-to-end
> behavioral reliability is still under active hardening.
