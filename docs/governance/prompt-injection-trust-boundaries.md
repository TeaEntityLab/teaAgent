# Prompt-Injection Trust Boundaries (WS3-005)

> **Status:** Current truth for untrusted content handling.
> **Scope:** Tool outputs, skills, memory, repository docs.

## Trust model

TeaAgent treats model-visible content by **provenance**, not by file extension:

| Source | Default trust | Harness behavior |
| --- | --- | --- |
| System / harness instructions | High | Fixed by operator configuration |
| User task messages | Medium | Executed as intent, not as tool policy |
| Tool outputs | **Untrusted** | Data only; must not override permission mode or approval gates |
| Skills (`SKILL.md`, injected skill bodies) | **Untrusted** | Routed through skill loader; cannot disable destructive-tool checks |
| Memory catalog entries | **Untrusted** | Injected as context; writes require normal workspace policy |
| Repository docs (`*.md`, plans, ADRs) | **Untrusted** | Readable context; not executable policy unless explicitly promoted by operator config |

## Boundaries enforced in code

1. **Destructive tools** — Require scoped approval tokens or JIT approval regardless of content in tool results, skills, or memory (`ApprovalPolicy.assert_allowed`).
2. **Path containment** — Workspace path arguments validated before destructive writes (`ApprovalManager._assert_paths_in_workspace`).
3. **Audit redaction** — Sensitive keys stripped before persistence (`audit.redact_audit_payload`).
4. **Skills supply chain** — Active skill directories are write-protected unless dev opt-in (`_assert_skill_path_not_protected`).

## Operator guidance

- Do not paste untrusted tool output back as system instructions.
- Treat memory and skill content as **hints**, not authorization.
- Enable `TEAAGENT_COMPLIANCE_MODE=1` when audit durability must fail closed (WS3-001).

## Verification

```bash
python3 -m pytest tests/test_prompt_injection_boundaries.py tests/test_ws3_schema_path_containment.py -q
```
