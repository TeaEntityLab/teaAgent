# TeaAgent Next-Generation Usage Design

## Most Common Scenarios

### Scenario 1: Launching a Consensus-Enabled Swarm

```bash
# Initialize a swarm with consensus requirements
teaagent swarm init \
  --consensus-mode multi-sig \
  --voting-threshold 2/3 \
  --peers peer1@ssh-key.pub,peer2@ssh-key.pub

# Launch a task that requires consensus
teaagent swarm run \
  --task "Analyze security vulnerabilities in /path/to/code" \
  --risk-level high \
  --require-consensus
```

**Expected behavior:**
- Swarm orchestrator requests votes from all peers
- Each peer reviews the task and signs their vote
- Once quorum is reached, task proceeds
- Audit log records all votes and signatures

### Scenario 2: Skill Execution in WASM Sandbox

```bash
# Load a dynamic skill with WASM preference
teaagent skill load \
  --path /path/to/skill \
  --sandbox wasm \
  --memory-limit 128m \
  --cpu-quota 0.5

# Execute the skill
teaagent skill run \
  --name security-scanner \
  --target /path/to/code
```

**Expected behavior:**
- Skill is compiled to WASM if needed
- WASM runtime starts with resource limits
- Skill executes in isolated environment
- Resource usage is tracked and reported

### Scenario 3: Docker Isolation with Resource Limits

```bash
# Configure Docker isolation with constraints
teaagent config set isolation.docker.cpu-quota 2.0
teaagent config set isolation.docker.memory-limit 1g
teaagent config set isolation.docker.enable-health-checks true

# Run a subagent with Docker isolation
teaagent agent run \
  --isolation docker \
  --task "Process large dataset"
```

**Expected behavior:**
- Docker container starts with specified limits
- Health checks monitor container status
- Resource usage is logged
- Container is cleaned up on completion

## CLI / API Examples

### Consensus Management

```bash
# List registered peers
teaagent swarm peers list

# Add a new peer
teaagent swarm peers add \
  --name peer3 \
  --ssh-key /path/to/peer3.pub

# Remove a peer
teaagent swarm peers remove --name peer3

# View consensus status
teaagent swarm consensus status

# View voting history
teaagent swarm consensus history
```

### Sandbox Configuration

```bash
# List available isolation modes
teaagent isolation list

# Configure Docker limits
teaagent isolation configure docker \
  --cpu-quota 2.0 \
  --memory-limit 1g \
  --enable-health-checks

# Configure WASM runtime
teaagent isolation configure wasm \
  --memory-limit 256m \
  --enable-syscalls network,filesystem

# View sandbox status
teaagent isolation status
```

### Skill Execution

```bash
# Load skill with specific sandbox
teaagent skill load \
  --path /path/to/skill \
  --sandbox auto

# Execute skill with custom limits
teaagent skill run \
  --name analyzer \
  --sandbox docker \
  --cpu-quota 1.0 \
  --memory-limit 512m

# View skill execution history
teaagent skill history
```

## Success Examples

### Example 1: Successful Consensus Vote

```
$ teaagent swarm run --task "Deploy to production" --risk-level critical

[INFO] Initiating consensus for high-risk task
[INFO] Requesting votes from 3 peers...
[INFO] peer1: APPROVED (signature: SHA256:abc123...)
[INFO] peer2: APPROVED (signature: SHA256:def456...)
[INFO] peer3: APPROVED (signature: SHA256:ghi789...)
[INFO] Quorum reached (3/3 votes)
[INFO] Task approved, proceeding with execution
[SUCCESS] Task completed successfully
```

### Example 2: WASM Skill Execution

```
$ teaagent skill run --name scanner --sandbox wasm

[INFO] Loading skill in WASM sandbox
[INFO] Compiling to WASM... (took 45ms)
[INFO] Starting WASM runtime with 128MB limit
[INFO] Executing skill...
[INFO] Peak memory: 87MB
[INFO] Execution time: 1.2s
[SUCCESS] Skill completed successfully
```

### Example 3: Docker with Resource Limits

```
$ teaagent agent run --isolation docker --task "Process data"

[INFO] Starting Docker container
[INFO] CPU quota: 2.0 cores, Memory limit: 1GB
[INFO] Container started (id: abc123def)
[INFO] Health check: healthy
[INFO] CPU usage: 1.8/2.0 cores
[INFO] Memory usage: 890MB/1GB
[INFO] Task completed
[INFO] Container stopped and removed
[SUCCESS] Execution completed
```

## Error Examples

### Example 1: Consensus Timeout

```
$ teaagent swarm run --task "Delete database" --risk-level critical

[INFO] Initiating consensus for high-risk task
[INFO] Requesting votes from 3 peers...
[INFO] peer1: APPROVED (signature: SHA256:abc123...)
[INFO] peer2: TIMEOUT (no response)
[INFO] peer3: REJECTED (signature: SHA256:def456...)
[ERROR] Consensus timeout: quorum not reached (1/3 votes)
[ERROR] Task rejected due to insufficient consensus
[INFO] Falling back to single-agent mode (requires manual approval)
```

### Example 2: WASM Compilation Failure

```
$ teaagent skill run --name scanner --sandbox wasm

[INFO] Loading skill in WASM sandbox
[ERROR] WASM compilation failed: unsupported Python feature (async/await)
[ERROR] Falling back to Docker isolation
[INFO] Starting Docker container...
[SUCCESS] Task completed in Docker fallback mode
```

### Example 3: Resource Limit Exceeded

```
$ teaagent agent run --isolation docker --task "Process data"

[INFO] Starting Docker container
[INFO] CPU quota: 1.0 cores, Memory limit: 512MB
[INFO] Container started (id: xyz789abc)
[ERROR] Resource limit exceeded: memory usage 600MB/512MB
[ERROR] Container terminated due to OOM
[INFO] Task failed due to resource exhaustion
[INFO] Audit log updated with resource violation
```

## Confusing Parts

### 1. Voting Threshold Configuration

**Confusion**: What do "2/3", "3/4", etc. mean?

**Clarification**: These represent the fraction of peers that must approve. "2/3" means 66.6% must approve. "unanimous" means all peers must approve.

**Better UX**:
```bash
teaagent swarm config set voting-threshold 66.6%
# or
teaagent swarm config set voting-threshold majority
teaagent swarm config set voting-threshold supermajority
teaagent swarm config set voting-threshold unanimous
```

### 2. Sandbox Auto-Selection

**Confusion**: How does "auto" sandbox selection work?

**Clarification**: Auto-selection uses a risk-based heuristic:
- Low risk: directory-snapshot (fastest)
- Medium risk: Docker (balanced)
- High risk: WASM (most isolated)

**Better UX**:
```bash
teaagent skill load --path /path/to/skill --sandbox auto
# Shows what sandbox would be selected
# teaagent skill load --path /path/to/skill --sandbox auto --dry-run
```

### 3. Peer Key Management

**Confusion**: How to handle SSH key rotation?

**Clarification**: Keys can be rotated by adding the new key, then removing the old one. The system maintains a grace period for old signatures.

**Better UX**:
```bash
teaagent swarm peers rotate-key \
  --name peer1 \
  --old-key /path/to/old.pub \
  --new-key /path/to/new.pub \
  --grace-period 24h
```

## Design Issues Revealed by Usage

### Issue 1: Consensus Latency

**Problem**: Waiting for peer votes adds latency to time-sensitive tasks.

**Solution**: Add "pre-approval" mode where peers can pre-authorize certain task patterns.

```bash
teaagent swarm config set pre-approve-patterns "security-scan,code-review"
```

### Issue 2: Resource Limit Discovery

**Problem**: Users don't know what resource limits to set.

**Solution**: Add "resource profiling" mode to suggest limits based on historical data.

```bash
teaagent isolation profile --task "Process data" --dry-run
# Suggested: CPU 1.5 cores, Memory 800MB
```

### Issue 3: WASM Compatibility

**Problem**: Not all Python features work in WASM.

**Solution**: Add compatibility checker before attempting WASM compilation.

```bash
teaagent skill check-wasm-compatibility --path /path/to/skill
# Result: 85% compatible, issues: async/await, socket module
```

### Issue 4: Consensus in Offline Mode

**Problem**: Air-gapped environments can't reach peers.

**Solution**: Add "local consensus" mode using local HSM or hardware tokens.

```bash
teaagent swarm config set consensus-mode local-hsm
```
