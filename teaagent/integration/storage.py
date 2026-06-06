"""Storage interface adapters for runs, audit, approvals, and memory (WS5-004)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from teaagent.audit import AuditLogger
from teaagent.ergonomics.approval_store import ApprovalPresetStore
from teaagent.memory.catalog import MemoryCatalog
from teaagent.run_store import RunStore, RunSummary


@runtime_checkable
class RunStorage(Protocol):
    def list_runs(self, *, limit: int = 50) -> list[RunSummary]: ...

    def show_run(self, run_id: str) -> list[dict[str, Any]]: ...

    def audit_logger(self, run_id: str | None = None) -> AuditLogger: ...


@runtime_checkable
class AuditStorage(Protocol):
    def read_events(self, run_id: str) -> list[dict[str, Any]]: ...

    def audit_logger(self, run_id: str | None = None) -> AuditLogger: ...


@runtime_checkable
class ApprovalPresetStorage(Protocol):
    def list_grants(self) -> list[dict[str, Any]]: ...


@runtime_checkable
class MemoryStorage(Protocol):
    def search(self, query: str, *, limit: int = 5) -> list[Any]: ...


class LocalRunStorage:
    def __init__(self, root: str | Path, *, readonly: bool = False) -> None:
        self._store = RunStore(root, readonly=readonly)

    @property
    def store(self) -> RunStore:
        return self._store

    def list_runs(self, *, limit: int = 50) -> list[RunSummary]:
        return self._store.list_runs(limit=limit)

    def show_run(self, run_id: str) -> list[dict[str, Any]]:
        return self._store.show_run(run_id)

    def audit_logger(self, run_id: str | None = None) -> AuditLogger:
        return self._store.audit_logger(run_id)


class LocalAuditStorage:
    def __init__(self, root: str | Path, *, readonly: bool = False) -> None:
        self._store = RunStore(root, readonly=readonly)

    def read_events(self, run_id: str) -> list[dict[str, Any]]:
        return self._store.show_run(run_id)

    def audit_logger(self, run_id: str | None = None) -> AuditLogger:
        return self._store.audit_logger(run_id)


class LocalApprovalPresetStorage:
    def __init__(self, root: str | Path) -> None:
        self._store = ApprovalPresetStore(root)

    @property
    def store(self) -> ApprovalPresetStore:
        return self._store

    def list_grants(self) -> list[dict[str, Any]]:
        return [grant.to_dict() for grant in self._store.list_grants()]


class LocalMemoryStorage:
    def __init__(self, root: str | Path) -> None:
        self._catalog = MemoryCatalog(root)

    @property
    def catalog(self) -> MemoryCatalog:
        return self._catalog

    def search(self, query: str, *, limit: int = 5) -> list[Any]:
        return self._catalog.search(query, limit=limit)


@dataclass(frozen=True)
class WorkspaceStorageBundle:
    runs: LocalRunStorage
    audit: LocalAuditStorage
    approvals: LocalApprovalPresetStorage
    memory: LocalMemoryStorage


def storage_bundle_for_workspace(
    root: str | Path,
    *,
    readonly: bool = False,
) -> WorkspaceStorageBundle:
    resolved = Path(root).resolve()
    return WorkspaceStorageBundle(
        runs=LocalRunStorage(resolved, readonly=readonly),
        audit=LocalAuditStorage(resolved, readonly=readonly),
        approvals=LocalApprovalPresetStorage(resolved),
        memory=LocalMemoryStorage(resolved),
    )
