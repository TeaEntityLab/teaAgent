# TeaAgent Onboarding Guide for Security Engineers

This guide helps security engineers understand and leverage TeaAgent's security-first architecture for AI agent governance.

## Overview

TeaAgent is a sovereign AI agent OS designed with cryptographic provenance, audit trails, and zero-trust supply chain security as foundational principles. Unlike other AI coding agents, TeaAgent provides enterprise-grade security guarantees out of the box.

## Core Security Architecture

### 1. Cryptographic Provenance (TSB)

TeaAgent uses **Provenanced Skill Bundles (TSB)** for skill distribution:

- **Sigstore Keyless Signing**: Skills are signed using OIDC tokens (no manual key management)
- **Path-Aware Hashing**: File paths are included in hash calculations to prevent structural attacks
- **Deterministic Builds**: Same skill produces identical hash across builds
- **Audit Chain Validation**: Complete, tamper-evident history of all changes

**Verification Workflow:**
```bash
# Verify a skill bundle with identity enforcement
teaagent skill verify-tsb skill.tsb \
  --identity "security-team@company.com" \
  --issuer "https://accounts.google.com"

# Offline verification for air-gapped environments
teaagent skill verify-tsb skill.tsb --offline
```

### 2. Permission Modes

TeaAgent provides granular permission control:

- **read-only**: No file modifications allowed
- **workspace-write**: Can modify files but not execute destructive commands
- **prompt**: Requires human approval for destructive operations (default)
- **allow**: Full automation (use with caution)
- **danger-full-access**: No restrictions (highly discouraged)

**JIT Permission Upgrades:**
```bash
# Start in safe mode, upgrade when needed
teaagent agent chat --permission-mode read-only
# In chat: /permission workspace-write
# In chat: /permission allow
```

### 3. Audit Trails

All agent actions are logged to an audit chain:

- **Immutable JSONL Logs**: Append-only audit trail
- **Cryptographic Hashing**: Each log entry is hashed
- **Chain Verification**: Detects tampering or missing entries

**Audit Verification:**
```bash
teaagent audit verify --audit-log audit.jsonl
```

### 4. Parallel Experiment Isolation

High-risk experiments run in isolated Git branches:

- **Sandbox Branches**: Each experiment gets its own Git branch
- **Quality Matrix**: Evaluates compilation, tests, performance
- **Automatic Cleanup**: Failed branches are removed automatically

**Parallel Experiments:**
```bash
teaagent run --parallel "strategy-a,strategy-b" "Optimize algorithm"
```

## Security Best Practices

### 1. Skill Supply Chain

**Never install unsigned skills:**
```bash
# Bad: Install without verification
teaagent skill install skill.tsb

# Good: Verify first, then install
teaagent skill verify-tsb skill.tsb --identity "trusted-author@company.com"
teaagent skill install skill.tsb
```

**Use identity policies:**
```bash
# Enforce specific OIDC identity
teaagent skill verify-tsb skill.tsb \
  --identity "security-team@company.com" \
  --issuer "https://token.actions.githubusercontent.com"
```

### 2. Permission Management

**Start restrictive, upgrade selectively:**
```bash
# Default to prompt mode
teaagent chat --permission-mode prompt

# Only upgrade for trusted tasks
teaagent run --permission-mode workspace-write "Update documentation"
```

**Use approval presets for common workflows:**
```bash
teaagent approval preset create --name "safe-experiments" \
  --permission-mode workspace-write \
  --allow-tools "read_file,write_file,run_command"
```

### 3. Audit Trail Management

**Regular audit verification:**
```bash
# Verify audit chain integrity
teaagent audit verify --audit-log audit.jsonl

# Check for suspicious activity
teaagent audit analyze --audit-log audit.jsonl --lookback 24h
```

**Backup audit logs:**
```bash
# Archive old audit logs
teaagent audit archive --audit-log audit.jsonl --output archive/
```

### 4. CI/CD Integration

**Use OIDC for automated signing:**
```yaml
# GitHub Actions workflow
- name: Sign TSB with OIDC
  run: |
    teaagent skill publish-tsb \
      --tsb-path skill.tsb \
      --author-key none  # Auto-detects GitHub Actions OIDC token
```

**Verify in production:**
```bash
# Production deployment with offline verification
teaagent skill verify-tsb skill.tsb --offline
teaagent skill install skill.tsb
```

## Security Checklist

Before deploying TeaAgent in production:

- [ ] Configure identity policies for skill verification
- [ ] Set up audit log retention and archival
- [ ] Define permission mode baselines for different environments
- [ ] Enable parallel experiment isolation for high-risk tasks
- [ ] Configure CI/CD OIDC integration for skill publishing
- [ ] Set up skill registry with trust scoring
- [ ] Define incident response procedures for security events
- [ ] Train team on permission escalation procedures

## Common Security Scenarios

### Scenario 1: Verifying Third-Party Skills

You receive a skill from an external vendor:

```bash
# 1. Verify with strict identity policy
teaagent skill verify-tsb vendor-skill.tsb \
  --identity "vendor@company.com" \
  --issuer "https://accounts.google.com"

# 2. Review audit chain
teaagent audit verify --audit-log vendor-skill-audit.jsonl

# 3. Test in isolated environment
teaagent run --permission-mode read-only \
  "Test vendor skill functionality"

# 4. Deploy if verification passes
teaagent skill install vendor-skill.tsb
```

### Scenario 2: Investigating Security Incidents

A skill performed unexpected actions:

```bash
# 1. Check audit log for the incident
teaagent audit analyze --audit-log audit.jsonl \
  --lookback 1h \
  --filter "tool_name=workspace_write_file"

# 2. Verify skill provenance
teaagent skill verify-tsb suspicious-skill.tsb

# 3. Revert changes using git
teaagent undo --last

# 4. Report incident with audit evidence
teaagent audit export --audit-log audit.jsonl \
  --output incident-report.json
```

### Scenario 3: Air-Gapped Deployment

Deploying in an environment without internet access:

```bash
# 1. Build and sign skills in connected environment
teaagent skill build-tsb --skill-path my-skill --output my-skill.tsb
teaagent skill publish-tsb --tsb-path my-skill.tsb

# 2. Transfer TSB to air-gapped environment
# (use secure transfer method)

# 3. Verify offline in air-gapped environment
teaagent skill verify-tsb my-skill.tsb --offline

# 4. Install skill
teaagent skill install my-skill.tsb
```

## Advanced Security Features

### Custom Approval Policies

Define custom approval logic for specific tools:

```python
# approval_policy.py
from teaagent.policy import ApprovalPolicy

class SecurityApprovalPolicy(ApprovalPolicy):
    def approve(self, request: ToolRequest) -> bool:
        # Block file writes to sensitive directories
        if request.tool_name == "workspace_write_file":
            path = request.arguments.get("path", "")
            if "/etc/" in path or "/var/" in path:
                return False
        return True
```

### Skill Trust Scoring

Implement trust scoring for skill registry:

```bash
# Check skill trust score
teaagent skill info skill-name --show-trust-score

# Only install high-trust skills
teaagent skill install skill-name --min-trust-score 0.8
```

### Multi-Signature Quorum

Require multiple signatures for critical skills:

```bash
# Build with multiple signers
teaagent skill build-tsb --skill-path critical-skill \
  --signers "security-team@company.com,cto@company.com"

# Verify quorum
teaagent skill verify-tsb critical-skill.tsb \
  --require-quorum 2
```

## Resources

- **Architecture**: [docs/architecture.md](architecture.md)
- **Security Model**: [docs/threat-model.md](threat-model.md)
- **Audit Log**: [docs/architecture.md#audit-log](architecture.md#audit-log)
- **Security ADRs**: [docs/adr/](adr/)

## Support

For security issues or questions:
- GitHub Issues: [github.com/TeaEntityLab/teaAgent/issues](https://github.com/TeaEntityLab/teaAgent/issues)
- Security Email: security@teaagent.dev
- Documentation: [docs.teaagent.dev](https://docs.teaagent.dev)
