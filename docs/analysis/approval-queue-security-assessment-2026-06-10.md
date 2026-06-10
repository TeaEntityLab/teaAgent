# Approval Queue Security Assessment

**Date:** 2026-06-10  
**Purpose:** Security assessment for replacing file-based approval queue with distributed message broker  
**Scope:** Redis vs RabbitMQ security comparison for TeaAgent approval queue use case

---

## 1. Current Security Boundaries (File-Based Queue)

### Current Implementation Security Features

**File-Based Security:**
- **Storage:** Local filesystem under `.teaagent/approval_queues/`
- **Access Control:** OS-level file permissions (owner/group/other)
- **Integrity Verification:** HMAC-SHA256 for queue file tamper detection
- **Concurrency Control:** fcntl locking for cross-process safety
- **Network Exposure:** None (local filesystem only)

**Security Guarantees:**
- **Confidentiality:** Filesystem-level encryption (if configured)
- **Integrity:** HMAC-SHA256 verification prevents tampering
- **Availability:** Local filesystem availability
- **Audit Trail:** Integrated with TeaAgent audit logging system

**Attack Surface:**
- Local file system access required
- No network exposure
- Physical access or local privilege escalation required for compromise

---

## 2. Networked Queue Attack Surface Analysis

### New Attack Vectors Introduced

| Attack Vector | Description | Impact | Likelihood |
|---------------|-------------|--------|------------|
| **Network Interception** | Eavesdropping on approval requests/responses | High | Medium |
| **Unauthorized Access** | External access to approval queue via network | Critical | Medium |
| **Privilege Escalation** | Compromised message broker affecting governance | Critical | Low |
| **Data Tampering in Transit** | Modification of approval data without encryption | High | Medium |
| **Denial of Service** | Message broker unavailability blocking approvals | High | Medium |
| **Credential Theft** | Message broker credentials exposed | Critical | Low |
| **Man-in-the-Middle** | TLS certificate compromise or downgrade attack | High | Low |

### Impact on Existing Threat Model

**Current Threat Model (39 threats):**
- Current threats primarily focus on local filesystem, prompt injection, shell mutation
- Networked queue introduces new threat categories:
  - Network security (TLS, authentication, authorization)
  - Distributed system security (message broker compromise)
  - Supply chain security (message broker dependencies)

**New Threats to Add:**
- NT-01: Network interception of approval queue data
- NT-02: Unauthorized access to message broker
- NT-03: Message broker compromise affecting governance
- NT-04: TLS certificate compromise
- NT-05: Denial of service via message broker

---

## 3. Redis vs RabbitMQ Security Comparison

### Redis Security Features

**Authentication & Authorization:**
- **ACLs (Access Control Lists):** Fine-grained permissions for commands, keys, and pub/sub channels (Redis 6.0+)
- **User Management:** Named users with password authentication
- **Legacy Authentication:** `requirepass` directive for password protection
- **Protected Mode:** Default mode restricts external access when no password configured

**Encryption:**
- **TLS Support:** Native TLS encryption (Redis 6.0+, requires compile-time enablement)
- **TLS Configuration:** X.509 certificates, CA bundles, DH params
- **Client Certificate Authentication:** Mutual TLS with client verification
- **Cipher Suite Control:** Configurable TLS protocols and cipher suites

**Network Security:**
- **Binding Control:** Bind to specific interfaces (not 0.0.0.0)
- **Protected Mode:** Rejects external connections when no password configured
- **Firewall Integration:** Should be used with network-level firewalls

**Audit & Monitoring:**
- **Command Logging:** Limited built-in audit capabilities
- **Slow Log:** Tracks slow commands for performance monitoring
- **Monitoring:** External monitoring required for security events

**Security Best Practices (Redis):**
- Enable ACLs with least-privilege users
- Configure TLS for all connections
- Bind to internal network only
- Disable KEYS/EVAL equivalent commands
- Use network segmentation
- Regular security updates

### RabbitMQ Security Features

**Authentication & Authorization:**
- **Multiple Authentication Methods:** Username/password, JWT tokens, x.509 certificates
- **SASL Mechanisms:** PLAIN, AMQPLAIN, ANONYMOUS, EXTERNAL (x.509)
- **Access Control:** Per-virtual host permissions (configure, write, read)
- **User Management:** Named users with password authentication
- **External Authentication:** LDAP integration available

**Encryption:**
- **TLS Support:** Native TLS for client connections and inter-node communication
- **TLS Configuration:** X.509 certificates, CA bundles, peer verification
- **Client Certificate Authentication:** Mutual TLS with x.509 certificates
- **Protocol Support:** TLS for AMQP 0-9-1 and AMQP 1.0

**Network Security:**
- **Virtual Hosts:** Logical isolation for different applications
- **Connection Encryption:** TLS for all connections recommended
- **Network Policies:** Should be used with network segmentation
- **Port Configuration:** Separate ports for plain and TLS connections

**Audit & Monitoring:**
- **Connection Logging:** Connection lifecycle events
- **Management API:** REST API for monitoring and configuration
- **Plugin Ecosystem:** Monitoring plugins available
- **Event Logging:** Security events can be logged

**Security Best Practices (RabbitMQ):**
- Enable TLS for all connections
- Use per-service credentials
- Configure virtual hosts for isolation
- Disable default/guest users
- Enable inter-cluster TLS
- Use network segmentation

### Comparison Summary

| Security Feature | Redis | RabbitMQ | Recommendation |
|-----------------|-------|----------|----------------|
| **Authentication** | ACLs (6.0+), passwords | SASL, x.509, JWT | RabbitMQ more flexible |
| **Authorization** | Command/key-level ACLs | Virtual host permissions | Redis more granular |
| **TLS Support** | Native (6.0+) | Native | Both equivalent |
| **Client Cert Auth** | Mutual TLS | Mutual TLS (EXTERNAL) | Both equivalent |
| **Network Isolation** | Binding, protected mode | Virtual hosts | RabbitMQ better isolation |
| **Audit Logging** | Limited | Better plugin ecosystem | RabbitMQ better |
| **Operational Security** | Simpler deployment | More complex but mature | Redis simpler |

---

## 4. Security Control Requirements Definition

### Required TLS Configuration

**TLS Version & Cipher Suites:**
- **Minimum TLS Version:** TLS 1.2 (prefer TLS 1.3)
- **Cipher Suites:** HIGH security level, disable weak ciphers
- **Certificate Management:** X.509 certificates with internal CA
- **Certificate Rotation:** Automated rotation (cert-manager or similar)

**TLS Configuration Template:**
```yaml
# Redis TLS Configuration
tls-port 6379
port 0  # Disable non-TLS
tls-cert-file /path/to/server.crt
tls-key-file /path/to/server.key
tls-ca-cert-file /path/to/ca.crt
tls-auth-clients yes  # Require client certificates
tls-protocols "TLSv1.2 TLSv1.3"
tls-ciphers "HIGH:!aNULL:!MD5"

# RabbitMQ TLS Configuration
listeners.ssl.default = 5671
ssl_options.cacertfile = /path/to/ca.crt
ssl_options.certfile = /path/to/server.crt
ssl_options.keyfile = /path/to/server.key
ssl_options.verify = verify_peer
ssl_options.fail_if_no_peer_cert = true
```

### Authentication & Authorization Requirements

**User Management:**
- **Per-Service Credentials:** Each TeaAgent component gets unique credentials
- **Least Privilege:** Minimum required permissions only
- **Credential Rotation:** Regular rotation (90 days maximum)
- **Credential Storage:** Secure vault (HashiCorp Vault or similar)

**ACL Requirements (Redis):**
```redis
# Approval queue user (read/write only)
USER teaagent_approval on >approval_queue:* +@read +@write -@admin -@dangerous

# Approval queue reader (read only)
USER teaagent_reader on >approval_queue:* +@read -@write -@admin

# Admin user (for operations)
USER teaagent_admin on ~* +@all
```

**Permission Requirements (RabbitMQ):**
```yaml
# Virtual host for approval queues
vhosts:
  - name: /teaagent_approval

# User permissions
permissions:
  - user: teaagent_approval
    vhost: /teaagent_approval
    configure: ^approval_queue$
    write: ^approval_queue$
    read: ^approval_queue$
```

### Network Segmentation Requirements

**Network Isolation:**
- **Private Network:** Message broker on private subnet only
- **Firewall Rules:** Whitelist specific IPs/subnets only
- **VPC Endpoints:** Use VPC endpoints if in cloud environment
- **No Internet Exposure:** Never expose message broker to internet

**Network Configuration:**
```yaml
# Firewall Rules
- Source: TeaAgent application servers
  Destination: Message broker
  Ports: 6379 (Redis TLS) or 5671 (RabbitMQ TLS)
  Action: Allow

- Source: Monitoring systems
  Destination: Message broker
  Ports: Management ports
  Action: Allow

- Source: Any
  Destination: Message broker
  Ports: Any
  Action: Deny
```

### Audit Logging Requirements

**Required Audit Events:**
- Connection attempts (success/failure)
- Authentication events
- Authorization failures
- Queue operations (publish/subscribe)
- Configuration changes
- TLS certificate events

**Audit Log Format:**
```json
{
  "timestamp": "2026-06-10T12:00:00Z",
  "event_type": "queue_operation",
  "user": "teaagent_approval",
  "operation": "publish",
  "queue": "approval_queue",
  "request_id": "req-123",
  "source_ip": "10.0.1.100",
  "result": "success"
}
```

**Audit Log Retention:**
- **Retention Period:** 90 days minimum (compliance requirement)
- **Log Storage:** Secure, tamper-evident storage
- **Log Rotation:** Automatic rotation to prevent disk exhaustion
- **Log Integrity:** Hash-chain verification or equivalent

### Monitoring & Alerting Requirements

**Security Metrics to Monitor:**
- Failed authentication attempts
- Authorization failures
- Unusual queue operation patterns
- TLS certificate expiration
- Connection anomalies
- Message broker resource exhaustion

**Alerting Thresholds:**
- **Failed Auth:** >10 failures in 1 minute
- **TLS Errors:** Any TLS handshake failure
- **Queue Depth:** >1000 pending approvals (indicates processing issue)
- **Connection Count:** >1000 concurrent connections (potential DoS)

---

## 5. Governance Impact Assessment

### Audit Trail Integrity

**Current State:**
- Audit trail integrated with TeaAgent audit logging
- Hash-chain verification for integrity
- Local filesystem storage with HMAC verification

**Networked Queue Impact:**
- **Risk:** Additional hop in audit trail (message broker)
- **Mitigation:** Message broker audit logging + correlation IDs
- **Requirement:** End-to-end audit trail from request to approval

**Audit Trail Enhancement:**
```python
# Add correlation IDs to all approval queue operations
approval_request = {
    "request_id": "req-123",
    "correlation_id": "corr-456",  # Links to TeaAgent audit trail
    "subagent_id": "subagent-1",
    "tool_name": "write_file",
    # ... other fields
}
```

### Compliance Requirements

**Data Sovereignty:**
- **Current:** Local filesystem (data stays on local machine)
- **Networked:** Message broker location matters (cloud/on-prem)
- **Requirement:** Document data location and compliance implications

**Regulatory Compliance:**
- **SOC 2:** Audit trail integrity, access controls
- **GDPR:** Data protection, right to erasure
- **HIPAA:** PHI protection if applicable
- **Requirement:** Compliance assessment for message broker deployment

### Security Control Updates

**New Security Controls Required:**
1. **TLS Certificate Management:** Lifecycle, rotation, revocation
2. **User Credential Management:** Creation, rotation, deletion
3. **Network Security:** Firewall rules, network segmentation
4. **Audit Logging:** Message broker audit integration
5. **Monitoring:** Security event monitoring and alerting
6. **Incident Response:** Message broker compromise procedures

**Updated Threat Model:**
- Add 5 new network-related threats (NT-01 through NT-05)
- Update existing threat mitigations for networked architecture
- Add new security controls to risk register

---

## 6. Operational Security Requirements

### Deployment Security

**Secure Deployment Checklist:**
- [ ] TLS certificates configured and validated
- [ ] User credentials created with least privilege
- [ ] Network segmentation configured
- [ ] Firewall rules implemented
- [ ] Audit logging enabled and tested
- [ ] Monitoring and alerting configured
- [ ] Backup and recovery procedures tested
- [ ] Security review completed
- [ ] Penetration testing completed
- [ ] Documentation updated

### Backup & Recovery

**Backup Requirements:**
- **Configuration Backups:** Message broker configuration
- **Certificate Backups:** TLS certificates and private keys
- **Data Backups:** Queue data (if persistence enabled)
- **Backup Frequency:** Daily configuration backups, real-time data replication

**Recovery Procedures:**
- **Message Broker Failure:** Failover to standby or restart
- **Certificate Expiration:** Certificate rotation procedure
- **Data Corruption:** Restore from backup
- **Security Incident:** Isolate and investigate

### Incident Response

**Security Incident Scenarios:**
1. **Message Broker Compromise:** Isolate, investigate, rotate credentials
2. **TLS Certificate Compromise:** Revoke certificates, rotate keys
3. **Unauthorized Access:** Revoke credentials, investigate logs
4. **Denial of Service:** Scale resources, implement rate limiting

**Incident Response Plan:**
- Detection: Monitoring alerts
- Containment: Isolate affected systems
- Eradication: Remove threat, patch vulnerabilities
- Recovery: Restore from backup, implement controls
- Lessons Learned: Update procedures, train team

---

## 7. Security Risk Matrix

| Risk | Likelihood | Impact | Mitigation | Residual Risk |
|------|------------|--------|------------|---------------|
| Network interception | Medium | High | TLS 1.3, strong cipher suites | Low |
| Unauthorized access | Medium | Critical | ACLs, network segmentation, per-service credentials | Low |
| Message broker compromise | Low | Critical | Hardening, monitoring, incident response | Medium |
| TLS certificate compromise | Low | High | Certificate rotation, monitoring | Low |
| Denial of service | Medium | High | Rate limiting, scaling, redundancy | Medium |
| Credential theft | Low | Critical | Secure vault, rotation, monitoring | Low |
| Audit trail compromise | Low | High | Hash-chain verification, secure storage | Low |

---

## 8. Recommendations

### Primary Recommendation

**Proceed with networked queue implementation ONLY if:**

1. **TLS Required:** All connections must use TLS 1.2+ with strong cipher suites
2. **Authentication Required:** Per-service credentials with least privilege
3. **Network Segmentation Required:** Message broker on private network only
4. **Audit Logging Required:** Comprehensive audit logging with correlation IDs
5. **Monitoring Required:** Security event monitoring and alerting
6. **Security Review Required:** Penetration testing and security review before production

### Technology Choice

**Redis Recommended for TeaAgent Approval Queue:**

**Reasons:**
- **Simpler Security Model:** ACLs easier to configure and manage
- **Better Performance:** Lower latency for approval operations
- **Simpler Deployment:** Easier to secure and harden
- **Sufficient Features:** ACLs, TLS, authentication meet requirements
- **Operational Simplicity:** Easier to monitor and troubleshoot

**RabbitMQ Considered If:**
- Advanced message routing required
- Complex virtual host isolation needed
- Enterprise messaging features needed
- Team has existing RabbitMQ expertise

### Implementation Priority

**Phase 1 (Security Foundation):**
1. Implement TLS configuration
2. Configure authentication and authorization
3. Set up network segmentation
4. Enable audit logging
5. Configure monitoring and alerting

**Phase 2 (Integration):**
1. Implement message broker client with TLS
2. Integrate audit trail with correlation IDs
3. Test security controls
4. Conduct penetration testing
5. Update documentation

**Phase 3 (Production):**
1. Security review and sign-off
2. Gradual rollout with monitoring
3. Incident response procedures validated
4. Ongoing security monitoring

---

## 9. Conclusion

The security assessment identifies significant security implications for replacing the file-based approval queue with a networked message broker. While both Redis and RabbitMQ provide robust security features, the transition requires:

- **Security Controls:** TLS, authentication, authorization, network segmentation
- **Operational Overhead:** Certificate management, credential rotation, monitoring
- **Governance Impact:** Updated threat model, audit trail integration, compliance assessment
- **Risk Acceptance:** New attack vectors introduced by networked architecture

**Recommendation:** Proceed with Redis-based implementation only if all security controls are implemented and validated through security review and penetration testing.

---

**Next Steps:**
1. Dependency evaluation (Redis vs RabbitMQ operational comparison)
2. Distributed queue benchmark (performance comparison)
3. Migration strategy design (dual-write, rollback procedures)
4. Security control implementation (TLS, authentication, monitoring)
