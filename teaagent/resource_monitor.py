"""Resource monitoring for sandbox execution.

This module provides real-time resource usage tracking for Docker containers
and other sandbox types, with alerting on resource violations.
"""

from __future__ import annotations

import errno
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Types of resources to monitor."""

    CPU = 'cpu'
    MEMORY = 'memory'
    DISK = 'disk'


@dataclass
class ResourceUsage:
    """Current resource usage metrics."""

    timestamp: datetime
    cpu_percent: float
    memory_mb: float
    memory_limit_mb: Optional[float] = None
    cpu_limit_cores: Optional[float] = None


@dataclass
class ResourceViolation:
    """Resource violation event."""

    resource_type: ResourceType
    current_value: float
    limit: float
    timestamp: datetime
    severity: str = 'warning'  # warning, critical


class ResourceMonitor:
    """Monitor resource usage for sandboxes."""

    def __init__(
        self,
        container_id: Optional[str] = None,
        cpu_limit_cores: Optional[float] = None,
        memory_limit_mb: Optional[float] = None,
        check_interval_seconds: float = 5.0,
    ) -> None:
        """Initialize resource monitor.

        Args:
            container_id: Docker container ID to monitor
            cpu_limit_cores: CPU limit in cores
            memory_limit_mb: Memory limit in MB
            check_interval_seconds: How often to check resources
        """
        self.container_id = container_id
        self.cpu_limit_cores = cpu_limit_cores
        self.memory_limit_mb = memory_limit_mb
        self.check_interval_seconds = check_interval_seconds
        self._monitoring = False
        self._violations: list[ResourceViolation] = []

    def start(self) -> None:
        """Start resource monitoring."""
        if self._monitoring:
            logger.warning('Resource monitoring already started')
            return

        self._monitoring = True
        logger.info(f'Started resource monitoring for container {self.container_id}')

    def stop(self) -> None:
        """Stop resource monitoring."""
        self._monitoring = False
        logger.info('Stopped resource monitoring')

    def get_current_usage(self) -> Optional[ResourceUsage]:
        """Get current resource usage.

        Returns:
            Current resource usage, or None if monitoring is not active
        """
        if not self.container_id:
            return None

        try:
            # Get Docker stats
            result = subprocess.run(
                [
                    'docker',
                    'stats',
                    self.container_id,
                    '--no-stream',
                    '--format',
                    '{{.CPUPerc}},{{.MemUsage}}',
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.warning(f'Failed to get Docker stats: {result.stderr}')
                return None

            # Parse output
            parts = result.stdout.strip().split(',')
            if len(parts) != 2:
                logger.warning(f'Unexpected Docker stats output: {result.stdout}')
                return None

            cpu_str = parts[0].strip()
            memory_str = parts[1].strip()

            # Parse CPU (remove % sign)
            cpu_percent = float(cpu_str.rstrip('%'))

            # Parse memory (e.g., "1.2GiB / 2GiB" or "512MiB / 1GiB")
            if '/' in memory_str:
                used_str, _ = memory_str.split('/')
                memory_mb = self._parse_memory_string(used_str.strip())
            else:
                memory_mb = self._parse_memory_string(memory_str.strip())

            return ResourceUsage(
                timestamp=datetime.now(timezone.utc),
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                memory_limit_mb=self.memory_limit_mb,
                cpu_limit_cores=self.cpu_limit_cores,
            )
        except Exception as exc:
            logger.error(f'Error getting resource usage: {exc}')
            return None

    def check_violations(self, usage: ResourceUsage) -> list[ResourceViolation]:
        """Check for resource violations.

        Args:
            usage: Current resource usage

        Returns:
            List of violations found
        """
        violations = []

        # Check CPU
        if self.cpu_limit_cores and usage.cpu_percent > (self.cpu_limit_cores * 100):
            violations.append(
                ResourceViolation(
                    resource_type=ResourceType.CPU,
                    current_value=usage.cpu_percent,
                    limit=self.cpu_limit_cores * 100,
                    timestamp=datetime.now(timezone.utc),
                    severity='critical',
                )
            )

        # Check memory
        if self.memory_limit_mb and usage.memory_mb > self.memory_limit_mb:
            violations.append(
                ResourceViolation(
                    resource_type=ResourceType.MEMORY,
                    current_value=usage.memory_mb,
                    limit=self.memory_limit_mb,
                    timestamp=datetime.now(timezone.utc),
                    severity='critical',
                )
            )

        # Store violations
        self._violations.extend(violations)
        return violations

    def get_violations(self) -> list[ResourceViolation]:
        """Get all recorded violations.

        Returns:
            List of violations
        """
        return self._violations

    def clear_violations(self) -> None:
        """Clear recorded violations."""
        self._violations = []

    def _parse_memory_string(self, memory_str: str) -> float:
        """Parse Docker memory string to MB.

        Args:
            memory_str: Memory string (e.g., "1.2GiB", "512MiB")

        Returns:
            Memory in MB
        """
        memory_str = memory_str.strip().upper()

        # Remove unit suffix
        if memory_str.endswith('GIB') or memory_str.endswith('GB'):
            value = float(memory_str[:-3].strip())
            return value * 1024
        elif memory_str.endswith('MIB') or memory_str.endswith('MB'):
            # Remove unit suffix (3 chars for MiB/MiB, 2 chars for MB/MB)
            if memory_str.endswith('MIB'):
                memory_str = memory_str[:-3]
            else:
                memory_str = memory_str[:-2]
            value = float(memory_str.strip())
            return value
        elif memory_str.endswith('KIB') or memory_str.endswith('KB'):
            # Remove unit suffix (3 chars for KiB/KiB, 2 chars for KB/KB)
            if memory_str.endswith('KIB'):
                memory_str = memory_str[:-3]
            else:
                memory_str = memory_str[:-2]
            value = float(memory_str.strip())
            return value / 1024
        else:
            # Assume bytes
            return float(memory_str) / (1024 * 1024)

    def is_monitoring(self) -> bool:
        """Check if monitoring is active.

        Returns:
            True if monitoring is active
        """
        return self._monitoring


def monitor_container(
    container_id: str,
    cpu_limit_cores: Optional[float] = None,
    memory_limit_mb: Optional[float] = None,
    duration_seconds: float = 60.0,
    check_interval_seconds: float = 5.0,
) -> list[ResourceUsage]:
    """Monitor a container for a duration.

    Args:
        container_id: Docker container ID
        cpu_limit_cores: CPU limit in cores
        memory_limit_mb: Memory limit in MB
        duration_seconds: How long to monitor
        check_interval_seconds: How often to check

    Returns:
        List of resource usage snapshots
    """
    monitor = ResourceMonitor(
        container_id=container_id,
        cpu_limit_cores=cpu_limit_cores,
        memory_limit_mb=memory_limit_mb,
        check_interval_seconds=check_interval_seconds,
    )

    monitor.start()
    usage_snapshots = []

    start_time = time.time()
    while time.time() - start_time < duration_seconds:
        usage = monitor.get_current_usage()
        if usage:
            usage_snapshots.append(usage)
            violations = monitor.check_violations(usage)
            if violations:
                for violation in violations:
                    logger.warning(
                        f'Resource violation: {violation.resource_type.value} '
                        f'{violation.current_value} > {violation.limit}'
                    )

        time.sleep(check_interval_seconds)

    monitor.stop()
    return usage_snapshots


def is_process_alive(pid: int) -> bool:
    """Check if a process with the given PID is alive.

    Uses os.kill with signal 0 to check process existence without sending a signal.
    This is the standard POSIX way to check if a process exists.

    Args:
        pid: Process ID to check

    Returns:
        True if process is alive, False otherwise
    """
    if pid <= 0:
        return False

    try:
        os.kill(pid, 0)  # Signal 0 doesn't actually send a signal
        return True
    except OSError as err:
        if err.errno == errno.ESRCH:  # No such process
            return False
        elif err.errno == errno.EPERM:  # Permission denied, but process exists
            return True
        else:
            # Other error, conservatively assume process might exist
            logger.warning(f'Unexpected error checking PID {pid}: {err}')
            return False
