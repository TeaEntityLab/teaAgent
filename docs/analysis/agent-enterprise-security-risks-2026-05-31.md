# Enterprise Security Risk Landscape — AI Coding Agents
# 2026-05-31

> Supersession note, 2026-06-05: This file is historical evidence. The security
> risks described here were absorbed into the risk register
> (`docs/security/risk-register-and-threat-model-2026-06-02.md`) and the
> Phase 0 trust repair brief
> (`docs/security/phase-0-trust-repair-risk-brief-2026-06-04.md`).

**Purpose:** Evidence-based risk inventory of the industry-wide security
failures in AI coding agents, mapped to teaagent's controls and gaps.
Informs `docs/plans/ux-improvement-roadmap-2026-05-31.md` item UX4.1.

**Sources:** Gravitee.io State of AI Agent Security 2026, NIST AI Agent
Standards Initiative (Feb 2026), Kiteworks survey (225 leaders), Hacker News,
Dark Reading, AI application security research.

---

## Industry Security Failure Statistics (2026)

| Metric | Value | Source |
|---|---|---|
| Enterprises with agent security incidents | 88% | Gravitee.io |
| Healthcare sector incidents | 92.7% | Gravitee.io |
| Organizations with no audit trail | 33% | Gravitee.io |
| Organizations with runtime agent visibility | 21% | Gravitee.io |
| Organizations that can stop agents when something goes wrong | <50% | Kiteworks |
| Agents sent to production with full IT approval | 14.4% | Kiteworks |
| Executives confident in existing policies | 82% | Kiteworks |
| Agent pilots that reach production | 12% | Gravitee.io |
| Organizations treating agents as independent identities | 22% | Gravitee.io |
| Teams using shared API keys instead of per-agent identity | 78% | Gravitee.io |

**The defining gap:** Executive confidence (82%) vs actual control (14.4%).

---

## Industry Attack Surface Categories (2026)

### AS-1 — Prompt Injection via Tool Outputs [CRITICAL]

Malicious content in tool outputs (file reads, web fetches, code execution
results) causes agents to take unauthorized actions. The attack surface is
every unstructured string the agent ingests.

**Industry finding (Cycode 2026):** Prompt injection in AI coding agents is
now an active attack vector, not a theoretical risk.

**teaagent control:** Audit log + approval gates block execution of suspicious
tool sequences. `mcp_trust.py` implements per-server trust levels.
**Gap:** No formal prompt injection detection layer. Model output is not
scanned for injected instructions before tool dispatch.

---

### AS-2 — Agent Identity Proliferation [CRITICAL]

78% of teams use shared API keys for multiple agents. When something goes
wrong, there is no per-agent attribution. Shared keys also mean a compromised
agent can impersonate other agents.

**Industry finding (Gravitee.io 2026):** "Organizational agents have no clear
owner, no single approver, and no defined lifecycle."

**NIST AI Agent Standards Initiative:** Agent identity is a priority
standardization area.

**teaagent control:** `agent_id` field in `ApprovalManager`. Multi-sig quorum
uses `peer_agent_ids`. `subagent_run_context.py` tracks lineage.
**Gap:** No formal agent identity credential (certificate, signed token) that
is distinct from the operator's API key.

---

### AS-3 — Authorization Bypass via Agent-to-Agent Escalation [HIGH]

AI agents are becoming "authorization bypass paths" — a low-privilege agent
is instructed to request a high-privilege action from a peer agent, bypassing
the human approval that would have been required if requested directly.

**Industry finding (The Hacker News, Jan 2026):** "AI Agents Are Becoming
Privilege Escalation Paths."

**teaagent control:** Per-agent JIT approval (`_agent_approved_tools`). Subagent
defs with explicit capability manifests. Approval scoped per-agent (not global).
**Gap:** The capability manifest for subagents is documented as "in progress"
in the prior comprehensive audit (S-H8 plugin audit).

---

### AS-4 — Data Exfiltration via Agentic MCP Tools [HIGH]

Remote MCP tools can be configured by attackers to exfiltrate code, credentials,
or sensitive workspace data. Without per-tool annotation enforcement, the agent
cannot distinguish a legitimate MCP read from an exfiltration attempt.

**Industry finding (blog.cyberdesserts.com 2026):** "MCP, OpenClaw & Supply
Chain" are the 2026 AI agent security risk trifecta.

**teaagent control:** `mcp_trust.py`, MCP tool filter hook, HTTP auth for remote
MCP, bearer auth requirement when `TEAAGENT_STRICT_LOCAL=1`.
**Gap (from prior audit S-H5):** MCP loopback has no auth requirement by
default. Local MCP servers can invoke all tools without authentication.

---

### AS-5 — Supply Chain via Plugin Entry Points [HIGH]

Plugins installed via the plugin system can execute arbitrary code with agent
privileges. Without manifest verification and allowlists, a malicious plugin
gains full tool access.

**Industry finding (Dark Reading 2026):** "As Coders Adopt AI Agents, Security
Pitfalls Lurk" — supply chain is the top cited risk in enterprise security
reviews.

**teaagent control:** Plugin verify/install gates, entry-point audit,
`TEAAGENT_PLUGINS_STRICT=1` fails closed.
**Gap (from prior audit S-H8):** Capability manifest formalization in progress.
Plugin audit fail-open without the strict flag.

---

### AS-6 — Credential Leakage in Audit Logs [HIGH]

Audit logs at L3 contain unredacted tool arguments. If tool arguments include
API keys, passwords, or personal data (passed as inputs), these are written
to disk in plaintext.

**Industry finding:** Not unique to teaagent — all audit-capable agents face
this. The risk is log exfiltration or insider access to `.teaagent/runs/`.

**teaagent control:** Audit redaction at L0/L1/L2. `TEAAGENT_AUDIT_LEVEL`
configures the level.
**Gap (from new-risk-findings-2026-05-31.md S-NEW1):** L3 claims "encrypted
at rest" but writes plaintext. If an operator sets L3 for compliance, they
receive weaker protection than documented.

---

### AS-7 — Non-Deterministic Output as Compliance Blocker [HIGH]

70% of enterprise leaders cite non-deterministic outputs as the #1 production-
readiness barrier. This is not a correctness problem — it is a governance
problem: the organization cannot demonstrate that the agent will behave
consistently under audit.

**Industry finding (Gravitee.io 2026):** "The challenge is less about the
model being wrong and more about organizations not being able to tell ahead
of time when it is wrong."

**teaagent relevance:** The audit chain provides post-hoc evidence of behavior.
What is missing is pre-run behavioral contracts and conformance testing.

**teaagent control:** Plan-before-write enforcement, policy-as-code deny rules.
**Gap:** No formal "behavioral contract" that can be cited in a compliance audit
as evidence that the agent will behave within specified bounds.

---

## Compliance Framework Mapping

### NIST AI Agent Standards Initiative (Feb 2026 — Priority Areas)

| NIST Priority | teaagent Control | Status |
|---|---|---|
| Agent identity | `agent_id`, subagent lineage | ⚠️ Soft identity, no credential |
| Authorization (per-action) | `ApprovalPolicy`, permission modes | ✅ Implemented |
| Authorization (per-agent scope) | Per-agent JIT approval | ✅ Implemented |
| Audit trail | `AuditLogger`, hash chain | ✅ Implemented |
| Runtime visibility | TUI approval UI, CLI audit view | ⚠️ CLI only, no dashboard |
| Kill switch / halt | `RunCancelledError`, budget cap | ✅ Implemented |
| Incident response | `teaagent undo`, `git_sandbox` | ✅ Implemented |

### SOC 2 Type II Relevance

For enterprise pilots that require SOC 2:
- **CC6.1 (Logical Access):** Permission modes map to access control requirements
- **CC6.6 (Transmission):** MCP HTTP auth, bearer tokens, TLS server
- **CC6.7 (Storage):** Audit log at rest (gap: L3 not encrypted — S-NEW1)
- **CC7.2 (Monitoring):** Audit chain, `teaagent audit verify`
- **CC9.2 (Vendor Risk):** Model provider docs needed

---

## Recommended Security Posture for teaagent Deployments

### Minimum Viable Secure Deployment

```toml
# .teaagent/config.toml
[security]
permission_mode = "prompt"          # Never "danger-full-access" in production
audit_level = "L2"                  # Redacted payloads (not L3 until S-NEW1 fixed)
require_plan = true                 # Plan-before-write enforced
mcp_strict_local = true             # Require token on loopback MCP
plugins_strict = true               # Fail closed on plugin audit errors

[budget]
max_cost_usd = 5.0                  # Hard cap per session
warn_at_pct = 50                    # Warn at 50% consumed
```

### High-Security Deployment (Team or Enterprise)

Additional requirements beyond minimum:
- `TEAAGENT_ALLOW_DEV_SIGNATURES=0` (never in production)
- `TEAAGENT_STRICT_LOCAL=1`
- `TEAAGENT_PLUGINS_STRICT=1`
- `TEAAGENT_AUDIT_EXPORT_TOKEN` set for log export tier
- Multi-sig quorum for write operations on sensitive repos
- Regular `teaagent audit verify` in CI
- Per-agent `agent_id` set (not default empty string)

---

## Open Security Gaps Ranked by Enterprise Impact

| Gap | NIST Area | Severity | Plan |
|---|---|---|---|
| L3 audit plaintext (S-NEW1) | Storage | HIGH | `docs/plans/comprehensive-plan-all-aspects-2026-05-31.md` Plan S1 |
| MCP loopback no-auth default (S-H5) | Authorization | HIGH | Remediation roadmap P1.4 ✅ |
| Plugin audit fail-open (S-H8) | Supply chain | HIGH | Remediation roadmap P3.7 ✅ |
| No formal agent identity credential | Identity | MEDIUM | Not planned — NEW |
| Capability manifest for subagents | Authorization | MEDIUM | In progress (prior audit) |
| No prompt injection detection | Input validation | MEDIUM | Not planned — NEW |
| Behavioral contract / conformance | Compliance | MEDIUM | Not planned — NEW |
| Shared API key vs per-agent identity | Identity | MEDIUM | Not planned — NEW |

---

## New Gap Items (Not in Prior Plans)

### SEC-NEW1 — No Formal Agent Identity Credential

**Risk:** Agents are identified by `agent_id` (a string). If two agents share
the same ID, there is no cryptographic way to distinguish them. In multi-agent
and WAN deployments, this enables impersonation.

**Proposed mitigation:** Generate a per-session Ed25519 key pair. Sign all
outbound approval requests with the private key. Verify with the public key
at the receiving end. Store public keys in `MultiSigQuorumConfig.peer_public_keys`.

**Effort:** Medium (1–2 weeks). Builds on existing SSH signature infrastructure.

---

### SEC-NEW2 — No Prompt Injection Detection Layer

**Risk:** Model output containing injected instructions (from malicious files,
MCP responses, or tool outputs) is passed directly to the tool dispatcher.
The agent may take unauthorized actions that pass all approval gates because
the model itself authorized them under injection.

**Proposed mitigation:**
1. Pattern-based detection: flag tool calls that match known injection patterns
   (e.g., "ignore previous instructions", "you are now", structured overrides)
2. Anomaly detection: flag tool call sequences that deviate significantly from
   the user's stated goal
3. Mandatory human review for any tool call flagged by detection

**Effort:** Medium. Detection heuristics can start simple and improve over time.

---

### SEC-NEW3 — No Behavioral Contract for Compliance

**Risk:** In a compliance audit, teaagent's governance controls are evidenced
only by code and audit logs. There is no pre-run behavioral contract that states
"this agent will not do X, Y, Z under any circumstances."

**Proposed mitigation:**
A `BehavioralContract` document (human-readable + machine-checkable) per
deployment:
```yaml
contract:
  version: 1
  not_allowed:
    - delete files outside workspace_root
    - execute shell commands not in allowlist
    - access network except approved_hosts
  always_required:
    - audit_level: L2
    - permission_mode: prompt
    - plan_contract: true
```
Verified at run start. Violations are blocked. Contract is signed and stored
with the audit log.

**Effort:** High (3–4 weeks). High compliance value for enterprise.
