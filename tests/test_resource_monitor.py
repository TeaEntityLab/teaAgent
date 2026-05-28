"""Tests for resource monitor."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from teaagent.resource_monitor import (
    ResourceMonitor,
    ResourceType,
    ResourceUsage,
    ResourceViolation,
    monitor_container,
)


def test_resource_monitor_init():
    """Test resource monitor initialization."""
    monitor = ResourceMonitor(
        container_id='test-container',
        cpu_limit_cores=2.0,
        memory_limit_mb=1024,
    )

    assert monitor.container_id == 'test-container'
    assert monitor.cpu_limit_cores == 2.0
    assert monitor.memory_limit_mb == 1024
    assert monitor.is_monitoring() is False


def test_resource_monitor_start_stop():
    """Test starting and stopping monitor."""
    monitor = ResourceMonitor(container_id='test-container')

    assert monitor.is_monitoring() is False
    monitor.start()
    assert monitor.is_monitoring() is True
    monitor.stop()
    assert monitor.is_monitoring() is False


def test_resource_usage_creation():
    """Test creating resource usage."""
    usage = ResourceUsage(
        timestamp=datetime.now(timezone.utc),
        cpu_percent=50.0,
        memory_mb=512.0,
        memory_limit_mb=1024.0,
        cpu_limit_cores=2.0,
    )

    assert usage.cpu_percent == 50.0
    assert usage.memory_mb == 512.0
    assert usage.memory_limit_mb == 1024.0


def test_resource_violation_creation():
    """Test creating resource violation."""
    violation = ResourceViolation(
        resource_type=ResourceType.CPU,
        current_value=150.0,
        limit=100.0,
        timestamp=datetime.now(timezone.utc),
        severity='critical',
    )

    assert violation.resource_type == ResourceType.CPU
    assert violation.current_value == 150.0
    assert violation.limit == 100.0


def test_parse_memory_string():
    """Test parsing Docker memory strings."""
    monitor = ResourceMonitor(container_id='test')

    assert monitor._parse_memory_string('1GiB') == 1024.0
    assert monitor._parse_memory_string('512MiB') == 512.0
    assert monitor._parse_memory_string('1024KiB') == 1.0
    assert monitor._parse_memory_string('1048576') == 1.0


def test_get_current_usage():
    """Test getting current usage from Docker."""
    monitor = ResourceMonitor(container_id='test-container')

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='50.0%,512MiB / 1GiB',
            stderr='',
        )

        usage = monitor.get_current_usage()

        assert usage is not None
        assert usage.cpu_percent == 50.0
        assert usage.memory_mb == 512.0


def test_get_current_usage_docker_error():
    """Test handling Docker stats error."""
    monitor = ResourceMonitor(container_id='test-container')

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout='',
            stderr='Container not found',
        )

        usage = monitor.get_current_usage()

        assert usage is None


def test_check_violations_cpu():
    """Test checking CPU violations."""
    monitor = ResourceMonitor(container_id='test', cpu_limit_cores=1.0)
    usage = ResourceUsage(
        timestamp=datetime.now(timezone.utc),
        cpu_percent=150.0,  # Over limit
        memory_mb=512.0,
        memory_limit_mb=1024.0,
        cpu_limit_cores=1.0,
    )

    violations = monitor.check_violations(usage)

    assert len(violations) == 1
    assert violations[0].resource_type == ResourceType.CPU
    assert violations[0].severity == 'critical'


def test_check_violations_memory():
    """Test checking memory violations."""
    monitor = ResourceMonitor(container_id='test', memory_limit_mb=512)
    usage = ResourceUsage(
        timestamp=datetime.now(timezone.utc),
        cpu_percent=50.0,
        memory_mb=1024.0,  # Over limit
        memory_limit_mb=512.0,
        cpu_limit_cores=2.0,
    )

    violations = monitor.check_violations(usage)

    assert len(violations) == 1
    assert violations[0].resource_type == ResourceType.MEMORY
    assert violations[0].severity == 'critical'


def test_check_violations_none():
    """Test checking violations with no limits."""
    monitor = ResourceMonitor(container_id='test')
    usage = ResourceUsage(
        timestamp=datetime.now(timezone.utc),
        cpu_percent=150.0,
        memory_mb=1024.0,
    )

    violations = monitor.check_violations(usage)

    assert len(violations) == 0


def test_violations_tracking():
    """Test that violations are tracked."""
    from datetime import datetime, timezone

    monitor = ResourceMonitor(container_id='test', memory_limit_mb=512)
    usage = ResourceUsage(
        timestamp=datetime.now(timezone.utc),
        cpu_percent=50.0,
        memory_mb=1024.0,
        memory_limit_mb=512.0,
    )

    monitor.check_violations(usage)
    violations = monitor.get_violations()

    assert len(violations) == 1

    monitor.clear_violations()
    assert len(monitor.get_violations()) == 0


def test_monitor_container():
    """Test monitoring a container."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='50.0%,512MiB / 1GiB',
            stderr='',
        )

        snapshots = monitor_container(
            container_id='test-container',
            duration_seconds=0.1,
            check_interval_seconds=0.05,
        )

        # Should have at least one snapshot
        assert len(snapshots) >= 1
