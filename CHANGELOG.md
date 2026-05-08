# Changelog

All notable changes to TeaAgent are tracked here.

## Unreleased

- Re-licensed the project under the MIT License and added the matching PyPI classifier.
- Marked the package as typed by shipping `teaagent/py.typed` and configuring setuptools `package-data`.
- Hardened `ContainerCodeModeBackend`: rejects empty images at construction, enforces `--read-only`, `--cap-drop=ALL`, `--security-opt=no-new-privileges`, non-root `--user`, `--tmpfs /tmp`, `--memory-swap`, and a separate `--ulimit cpu` for CPU time. The `--cpus` flag now reflects an explicit CPU-share field instead of reusing the CPU-time budget.
- Added `CodeModeSandbox.max_output_bytes` and switched the container backend to `subprocess.Popen` so oversized stdout is rejected instead of buffered without bound.
- Updated `SECURITY.md` to reflect the storage-layer file locking that audit and memory writes already use, and added `docs/p3-scope.md` to mirror the existing P0/P1/P2 scope notes.
- Added a pluggable Code Mode backend boundary with the existing child-process backend and a Docker/Podman-style container backend.
- Added audit-driven metrics sinks for run and tool lifecycle counters plus basic histogram samples.
- Added release packaging basics: license file, changelog, and distribution build workflow.
