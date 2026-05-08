# ADR 0003: Code Mode Child-Process Sandbox

## Status

Accepted for P2 implementation.

## Decision

Execute LLM-generated Python code in a detached child process with AST allow-list
validation, CPU-time limits, wall-clock timeouts, and best-effort memory limits.
Reject container-level isolation, seccomp, and V8 isolates as P2 scope.

## Rationale

- AST allow-list validation (`ALLOWED_NODES`) prevents imports, attribute access,
  function definitions, and other dangerous constructs at parse time.
- A `multiprocessing.Process` boundary isolates the child's address space from
  the parent. Even if `exec()` corrupts the child, the parent survives.
- `RLIMIT_CPU` provides a hard CPU-time ceiling.
- Wall-clock timeout via `process.join(timeout)` prevents hung code.
- `RLIMIT_AS` provides advisory memory limits; it is silently no-op on macOS
  (macOS rejects `RLIMIT_AS` lowering) but the wall/CPU timeouts still bound
  the attack surface.

## Consequences

- Code Mode is safe for *advisory* local data manipulation but is **not**
  a production-grade sandbox. The child process shares the parent's filesystem
  view, network namespace, and process namespace.
- Production deployment should layer containers, seccomp profiles, or a managed
  execution service on top of this implementation.
- The `SAFE_BUILTINS` list is deliberately small (math, collection constructors).
  Expanding it requires an ADR and threat model review.

## Alternatives Considered

- **subinterpreters (PEP 554)**: Not available in Python 3.9; too bleeding-edge.
- **Docker/container per execution**: Latency of ~1s per Code Mode call makes
  it impractical for the dozens of calls an agent may make in one run.
- **V8/QuickJS isolate via PyMiniRacer or similar**: Adds a C extension dependency
  and a second language runtime; violates the "stdlib-only P0" policy.
- **RestrictedPython**: Transforms source code but still executes in-process;
  offers no resource limits. Rejected in favor of the process boundary.
