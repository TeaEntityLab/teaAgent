# OpenCode Gap Watch Process

**Status:** Active monitoring process
**Frequency:** Monthly
**Owner:** TBD
**Last reviewed:** 2026-06-01

## Purpose

Monitor OpenCode GitHub releases and community activity for governance-related features that could impact TeaAgent's competitive positioning. Escalate if approval gates or similar governance features are added.

## Monitoring Checklist

### Monthly Review Tasks

- [ ] Check OpenCode GitHub repository for new releases
- [ ] Review release notes for governance-related features:
  - Approval gates
  - Audit trails
  - Permission modes
  - Cost tracking
  - Undo/rollback capabilities
  - Multi-sig or consensus mechanisms
- [ ] Scan OpenCode issues for governance discussions
- [ ] Check OpenCode community posts (Reddit, Discord, etc.) for governance requests
- [ ] Document findings in this file

### Automation

Run the automated monitoring script:

```bash
python3 scripts/opencode_gap_watch.py --update-docs
```

For a dry run (without updating docs):

```bash
python3 scripts/opencode_gap_watch.py
```

## Escalation Triggers

Escalate to product/strategy review if any of the following occur:

1. **Governance feature implementation:** OpenCode implements approval gates, audit trails, or permission modes
2. **Community demand:** Governance-related issues receive 50+ votes or significant community support
3. **Strategic alignment:** OpenCode positioning shifts toward governance-first messaging
4. **Feature parity:** OpenCode implements features that match TeaAgent's unique governance capabilities

## Escalation Process

When an escalation trigger is met:

1. Document the finding with:
   - Date discovered
   - Feature/issue description
   - Evidence (links, screenshots)
   - Impact assessment (high/medium/low)
2. Notify stakeholders via:
   - Update to `docs/backlog-priority.md` CP-4 section
   - Team discussion
3. Determine response:
   - Update competitive positioning (CP-1, CP-2)
   - Accelerate roadmap items
   - Adjust messaging
   - No action (if impact is low)

## Tracking Log

| Date | Review Type | Findings | Escalation Required? | Action Taken |
|------|-------------|----------|---------------------|--------------|
| 2026-06-01 | Initial setup | Process established | No | Document created |
| 2026-06-01 | Automated monitoring cycle | No new releases, no governance issues, no community governance requests | No | Monitoring cycle completed via automation script |

## Resources

- OpenCode GitHub: [Link to be added]
- OpenCode Issues: [Link to be added]
- Competitive positioning plan: `docs/plans/competitive-positioning-plan-2026-05-31.md`
- Backlog priority: `docs/backlog-priority.md`
