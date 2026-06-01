# Skill Governance and Security Audit Process

Last updated: 2026-06-02

This document defines the governance process for TeaAgent skills, including review, security auditing, and trust scoring.

## Overview

TeaAgent skills are distributed as Provenanced Skill Bundles (TSB) with cryptographic signatures. This governance process ensures that skills in the ecosystem are safe, reliable, and trustworthy.

## Governance Principles

1. **Cryptographic Provenance**: All skills must be signed with verifiable identities
2. **Audit Trail**: Complete history of skill development and changes
3. **Security Review**: Automated and manual security checks before publication
4. **Trust Scoring**: Quantitative assessment of skill trustworthiness
5. **Community Oversight**: Transparent review process with community feedback

## Skill Lifecycle

### 1. Development Phase

**Requirements:**
- Skill must have `SKILL.md` with clear documentation
- Code must follow TeaAgent coding standards
- Include unit tests with >80% coverage
- Document dependencies and their versions

**Best Practices:**
```bash
# Initialize skill with template
teaagent skill init --name my-skill --template standard

# Add documentation
teaagent skill doc --add usage-examples
teaagent skill doc --add security-considerations

# Run tests
teaagent skill test --coverage
```

### 2. Security Audit Phase

**Automated Checks:**
- Dependency vulnerability scanning
- Code static analysis (security linters)
- Path traversal detection
- Audit chain validation
- TSB format compliance

**Manual Review:**
- Code review by security team
- Architecture review
- Permission model review
- Data handling review

**Audit Checklist:**
```markdown
## Security Audit Checklist

### Code Security
- [ ] No hardcoded credentials or API keys
- [ ] Input validation on all user inputs
- [ ] Proper error handling without information leakage
- [ ] No unsafe deserialization
- [ ] Proper file permission handling

### Permissions
- [ ] Minimal permission model (prefer read-only)
- [ ] Destructive operations require explicit approval
- [ ] No unrestricted file system access
- [ ] Network access is scoped and documented

### Dependencies
- [ ] All dependencies are from trusted sources
- [ ] Dependency versions are pinned
- [ ] No known vulnerabilities (CVEs)
- [ ] License compatibility verified

### Audit Trail
- [ ] Complete audit chain for all changes
- [ ] Audit logs are tamper-evident
- [ ] Sensitive operations are logged
- [ ] Audit logs are retained per policy

### TSB Compliance
- [ ] Proper TSB format structure
- [ ] Path-aware hashing enabled
- [ ] Deterministic build process
- [ ] Signature verification passes
```

**Running Security Audit:**
```bash
# Automated security scan
teaagent skill audit --skill-path my-skill --security-scan

# Dependency vulnerability check
teaagent skill audit --skill-path my-skill --check-deps

# Audit chain validation
teaagent skill audit --skill-path my-skill --validate-audit

# Full audit report
teaagent skill audit --skill-path my-skill --full-report --output audit-report.md
```

### 3. Publication Phase

**Pre-Publication Checklist:**
```markdown
## Pre-Publication Checklist

### Documentation
- [ ] SKILL.md is complete and accurate
- [ ] Usage examples are provided
- [ ] Security considerations documented
- [ ] Known limitations listed

### Testing
- [ ] Unit tests pass (>80% coverage)
- [ ] Integration tests pass
- [ ] Manual testing completed
- [ ] Edge cases tested

### Build
- [ ] TSB builds successfully
- [ ] Bundle hash is deterministic
- [ ] Signature verification passes
- [ ] Audit chain is complete

### Review
- [ ] Code review approved
- [ ] Security audit passed
- [ ] Architecture review approved
- [ ] License review approved
```

**Building and Signing:**
```bash
# Build TSB
teaagent skill build-tsb \
  --skill-path my-skill \
  --audit-log audit.jsonl \
  --output my-skill.tsb

# Sign with OIDC (CI/CD)
teaagent skill publish-tsb \
  --tsb-path my-skill.tsb \
  --author-key none

# Verify before publishing
teaagent skill verify-tsb my-skill.tsb \
  --identity "author@organization.com"
```

### 4. Publication Phase

**Publication Options:**

1. **GitHub Release** (Public):
```bash
teaagent skill publish --to github --tag v1.0.0
```

2. **TeaAgent Registry** (Curated):
```bash
teaagent skill publish --to registry --category "security"
```

3. **Private Distribution** (Internal):
```bash
teaagent skill publish --to private --team security-team
```

**Publication Metadata:**
```json
{
  "name": "my-skill",
  "version": "1.0.0",
  "author": "author@organization.com",
  "category": "security",
  "trust_score": 0.95,
  "security_audit": "passed",
  "dependencies": [
    {"name": "cryptography", "version": "41.0.0"}
  ],
  "permissions": {
    "mode": "workspace-write",
    "destructive_requires_approval": true
  }
}
```

### 5. Post-Publication Monitoring

**Continuous Monitoring:**
- Dependency vulnerability alerts
- Usage anomaly detection
- Security incident reports
- Community feedback aggregation

**Incident Response:**
```bash
# Report security issue
teaagent skill report-issue --skill my-skill --type security

# Revoke compromised skill
teaagent skill revoke --skill my-skill --reason "security-vulnerability"

# Issue security advisory
teaagent skill advisory --skill my-skill --cve CVE-2024-XXXXX
```

## Trust Scoring

### Trust Score Components

**Base Score (0-100):**
- **Code Quality (25 points)**: Test coverage, code style, documentation
- **Security (30 points)**: Audit results, vulnerability scan, permission model
- **Provenance (20 points)**: Signature verification, audit chain, author reputation
- **Community (15 points)**: Usage statistics, user ratings, issue resolution
- **Maintenance (10 points)**: Update frequency, response time, long-term support

**Scoring Formula:**
```
Trust Score = (Code Quality + Security + Provenance + Community + Maintenance) / 100
```

**Trust Levels:**
- **0.90-1.00**: Trusted (can be used in production)
- **0.70-0.89**: Verified (suitable for development)
- **0.50-0.69**: Experimental (use with caution)
- **0.00-0.49**: Untrusted (not recommended)

**Viewing Trust Scores:**
```bash
teaagent skill info my-skill --show-trust-score
teaagent skill list --min-trust-score 0.8
```

## Review Process

### 1. Automated Review

**Triggers:**
- Skill submission to registry
- Pull request to skill repository
- Scheduled re-audit (quarterly)

**Checks:**
```yaml
automated_review:
  - name: "Build Verification"
    check: "teaagent skill build-tsb"
    required: true
  
  - name: "Security Scan"
    check: "teaagent skill audit --security-scan"
    required: true
  
  - name: "Dependency Check"
    check: "teaagent skill audit --check-deps"
    required: true
  
  - name: "Test Coverage"
    check: "teaagent skill test --coverage"
    threshold: 0.8
    required: true
  
  - name: "Audit Chain"
    check: "teaagent skill audit --validate-audit"
    required: true
```

### 2. Manual Review

**Reviewers:**
- Security Engineer (required for security-sensitive skills)
- Domain Expert (required for specialized skills)
- TeaAgent Maintainer (required for registry publication)

**Review Criteria:**
- Code quality and maintainability
- Security posture and risk assessment
- Documentation completeness
- Permission model appropriateness
- Dependency safety

**Review Workflow:**
```bash
# Request review
teaagent skill request-review --skill my-skill --reviewers security,domain

# View review status
teaagent skill review-status --skill my-skill

# Address review comments
teaagent skill address-review --skill my-skill --comment-id 123
```

### 3. Community Review

**Public Feedback:**
- GitHub issues and discussions
- Skill rating system (1-5 stars)
- Usage statistics and adoption metrics
- Security reports via responsible disclosure

**Feedback Integration:**
```bash
# View community feedback
teaagent skill feedback --skill my-skill

# Respond to feedback
teaagent skill respond --skill my-skill --feedback-id 456
```

## Security Incident Response

### Incident Classification

**Severity Levels:**
- **Critical**: Exploitable vulnerability in production use
- **High**: Vulnerability with potential impact
- **Medium**: Security issue with limited impact
- **Low**: Minor security concern

### Response Process

1. **Detection**: Automated monitoring or user report
2. **Triage**: Security team assesses severity
3. **Mitigation**: Temporary measures (warnings, revocation)
4. **Fix**: Developer patches the vulnerability
5. **Verification**: Security team validates fix
6. **Publication**: New version released with advisory
7. **Communication**: Users notified of update

**Incident Response Commands:**
```bash
# Report incident
teaagent security report --skill my-skill --severity critical --description "RCE vulnerability"

# Temporary revocation
teaagent skill revoke --skill my-skill --temporary --reason "under-investigation"

# Issue advisory
teaagent security advisory --skill my-skill --cve CVE-2024-XXXXX --severity critical

# Verify fix
teaagent skill audit --skill-path my-skill-fixed --security-scan
```

## Governance Policies

### 1. Skill Retention

- Skills with trust score < 0.5 are removed from registry after 30 days
- Inactive skills (no updates for 12 months) are marked as deprecated
- Deprecated skills are archived after 6 months

### 2. Dependency Requirements

- All dependencies must have compatible licenses
- Dependencies with known CVEs must be updated or justified
- Dependency versions must be pinned in requirements.txt

### 3. Permission Requirements

- Skills must use minimal permission mode
- Destructive operations require explicit approval
- Network access must be documented and scoped

### 4. Audit Requirements

- All skill changes must be recorded in audit chain
- Audit logs must be retained for minimum 1 year
- Audit logs must be tamper-evident

## Compliance

### Industry Standards

- **SOC 2**: Audit trail and access control
- **ISO 27001**: Information security management
- **NIST**: Security framework alignment
- **GDPR**: Data protection compliance

### Regulatory Compliance

**For Financial Services:**
- Additional security audits required
- Multi-signature verification for critical skills
- Enhanced audit retention (7 years)

**For Healthcare:**
- HIPAA compliance for data handling
- PHI handling restrictions
- Enhanced access controls

## Resources

- **Architecture Decisions**: [docs/adr/](adr/)
- **Audit Module Docs**: [docs/modules/audit/](../docs/modules/audit/)
- **Security Policies**: [SECURITY.md](../SECURITY.md)
- **Reporting**: [security@teaagent.dev](mailto:security@teaagent.dev)

## Support

For governance questions:
- Governance Team: governance@teaagent.dev
- Security Team: security@teaagent.dev
- Documentation: [docs.teaagent.dev/governance](https://docs.teaagent.dev/governance)
