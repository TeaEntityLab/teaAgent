# TeaAgent Security Specifications

## Overview
This document describes the security specifications for the TeaAgent codebase, including security requirements, threat model, and security controls implemented.

## Security Requirements

### 1. Command Execution Security
- **Requirement**: All shell command execution must use safe parsing
- **Implementation**: Use `shlex.split()` instead of `shell=True`
- **Files**: `workspace_tools/_shell.py`, `cli/_handlers/_chat.py`
- **Status**: ✅ Implemented

### 2. Input Validation
- **Requirement**: All user inputs must be validated before processing
- **Implementation**:
  - Regex pattern validation with error handling
  - Line number bounds checking
  - Path traversal prevention
  - Symlink validation
- **Files**: `workspace_tools/_files.py`
- **Status**: ✅ Implemented

### 3. Cryptographic Security
- **Requirement**: Use cryptographically secure random number generation
- **Implementation**: Use `secrets` module instead of `random`
- **Files**: `context_bus.py`, `llm/_retry.py`
- **Status**: ✅ Implemented

### 4. Environment Variable Security
- **Requirement**: Filter sensitive environment variables from subprocess environments
- **Implementation**: Use allowlist approach instead of blacklist
- **Files**: `workspace_tools/_shell.py`
- **Status**: ✅ Implemented

### 5. Token Security
- **Requirement**: Use strong hashing for tokens with salt
- **Implementation**: PBKDF2 with random salt for new tokens
- **Files**: `surface_auth.py`
- **Status**: ✅ Implemented

### 6. File Operation Security
- **Requirement**: Atomic file operations to prevent race conditions
- **Implementation**: Use temp files with atomic rename
- **Files**: `workspace_tools/_files.py`
- **Status**: ✅ Implemented

## Threat Model

### Threat Vectors
1. **Command Injection**: Malicious commands injected via shell execution
2. **Path Traversal**: Accessing files outside workspace via `..` sequences
3. **Symlink Attacks**: Accessing files through symbolic links
4. **Race Conditions**: TOCTOU attacks on file operations
5. **Information Disclosure**: Leaking sensitive environment variables
6. **Weak Cryptography**: Predictable random numbers or weak hashing

### Security Controls

### Defense in Depth
1. **Input Validation**: All inputs validated before processing
2. **Safe Parsing**: Use `shlex.split()` for command parsing
3. **Path Validation**: Validate paths are within workspace root
4. **Symlink Checks**: Block symlink access
5. **Atomic Operations**: Use temp files for atomic writes
6. **Secure Random**: Use `secrets` module for cryptographic randomness
7. **Environment Filtering**: Allowlist approach for environment variables
8. **Strong Hashing**: PBKDF2 with salt for token hashing

### Security Testing
- Unit tests for all security fixes: `tests/test_security_fixes.py`
- Integration tests for command execution
- Fuzzing tests for input validation
- Penetration testing for common vulnerabilities

## Audit Levels

- **L2 (default):** Redacted payloads suitable for routine operator review.
- **L3:** Full payloads written **without redaction and without encryption at rest**.
  Do not enable L3 on shared or compliance-sensitive storage unless a future
  audit-encryption extra is enabled and reviewed.

## Code Mode Trust Boundary

| Backend | Isolation | Use when |
| --- | --- | --- |
| `ChildProcessCodeModeBackend` | Fork + `SAFE_BUILTINS` + resource limits | Trusted user inputs only (`trusted_only=True`, default) |
| `ContainerCodeModeBackend` | Docker with network isolation | Untrusted or multi-tenant workloads |

Setting `ChildProcessCodeModeBackend(trusted_only=False)` raises at execute time.

## Security Monitoring
- Audit logging for all security-relevant operations
- Error logging for failed security checks
- Metrics for security violations prevented

## Compliance
- OWASP Top 10: Addresses injection, broken access control, security misconfiguration
- CWE: Addresses CWE-78 (OS Command Injection), CWE-20 (Improper Input Validation)
- Industry Standards: Follows secure coding best practices

## References
- OWASP Command Injection Prevention Cheat Sheet
- Python Security Best Practices
- CWE Mitigation Strategies
