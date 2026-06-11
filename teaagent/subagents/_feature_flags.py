"""Feature flag system for gradual rollout of new features."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class FeatureFlagConfig:
    """Configuration for feature flags."""

    config_path: Optional[Path] = None
    environment_variable_prefix: str = 'TEAAGENT_FEATURE_'


class FeatureFlags:
    """Feature flag system for gradual rollout.

    Supports:
    - Configuration file-based flags
    - Environment variable overrides
    - Runtime flag updates
    - Flag inheritance and defaults
    """

    def __init__(
        self,
        config: Optional[FeatureFlagConfig] = None,
    ) -> None:
        self.config = config or FeatureFlagConfig()
        self._flags: dict[str, Any] = {}
        self._defaults: dict[str, Any] = {
            'use_hybrid_approval_queue': False,
            'use_redis_only': False,
            'redis_primary_writes': True,
            'enable_redis_fallback': True,
            'hybrid_queue_sync_interval': 60,
            'hybrid_queue_rollout_percentage': 0,  # 0-100% of traffic to hybrid queue
            'hybrid_queue_enable_circuit_breaker': True,
            'hybrid_queue_enable_compression': False,
            'hybrid_queue_enable_deduplication': True,
            'hybrid_queue_enable_ttl': True,
            'hybrid_queue_enable_priority': False,
            'hybrid_queue_enable_rate_limiting': False,
            'hybrid_queue_enable_audit_trail': True,
            'hybrid_queue_enable_encryption': False,
            'hybrid_queue_enable_archival': False,
        }

        # Load from config file if provided
        if self.config.config_path and self.config.config_path.exists():
            self._load_from_file()

        # Load from environment variables
        self._load_from_environment()

    def _load_from_file(self) -> None:
        """Load feature flags from configuration file."""
        if not self.config.config_path:
            return

        try:
            with self.config.config_path.open('r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self._flags.update(data)
                    logger.info(
                        f'Loaded {len(data)} feature flags from {self.config.config_path}'
                    )
        except Exception as e:
            logger.error(
                f'Failed to load feature flags from {self.config.config_path}: {e}'
            )

    def _load_from_environment(self) -> None:
        """Load feature flags from environment variables."""
        prefix = self.config.environment_variable_prefix

        for key, value in os.environ.items():
            if key.startswith(prefix):
                flag_name = key[len(prefix) :].lower()
                # Convert boolean strings
                if value.lower() in ('true', '1', 'yes'):
                    self._flags[flag_name] = True
                elif value.lower() in ('false', '0', 'no'):
                    self._flags[flag_name] = False
                elif value.isdigit():
                    self._flags[flag_name] = int(value)
                else:
                    self._flags[flag_name] = value

    def is_enabled(self, flag_name: str, default: Optional[bool] = None) -> bool:
        """Check if a feature flag is enabled.

        Args:
            flag_name: Name of the feature flag
            default: Default value if flag not set (uses _defaults if None)

        Returns:
            True if flag is enabled, False otherwise
        """
        if flag_name in self._flags:
            value = self._flags[flag_name]
            return bool(value)

        if default is not None:
            return default

        return bool(self._defaults.get(flag_name, False))

    def get(self, flag_name: str, default: Optional[Any] = None) -> Any:
        """Get the value of a feature flag.

        Args:
            flag_name: Name of the feature flag
            default: Default value if flag not set (uses _defaults if None)

        Returns:
            Value of the feature flag
        """
        if flag_name in self._flags:
            return self._flags[flag_name]

        if default is not None:
            return default

        return self._defaults.get(flag_name)

    def set(self, flag_name: str, value: Any) -> None:
        """Set a feature flag value at runtime.

        Args:
            flag_name: Name of the feature flag
            value: Value to set
        """
        self._flags[flag_name] = value
        logger.info(f"Feature flag '{flag_name}' set to {value}")

    def reset(self, flag_name: str) -> None:
        """Reset a feature flag to its default value.

        Args:
            flag_name: Name of the feature flag
        """
        if flag_name in self._flags:
            del self._flags[flag_name]
            logger.info(f"Feature flag '{flag_name}' reset to default")

    def get_all_flags(self) -> dict[str, Any]:
        """Get all feature flags with their current values.

        Returns:
            Dictionary of all feature flags
        """
        result = {}
        for flag_name in self._defaults:
            result[flag_name] = self.is_enabled(flag_name)
        return result

    def should_use_hybrid_queue(self, request_id: str) -> bool:
        """Check if a request should use the hybrid queue based on rollout percentage.

        Args:
            request_id: Request ID to use for consistent hashing

        Returns:
            True if request should use hybrid queue, False otherwise
        """
        rollout_percentage = self.get('hybrid_queue_rollout_percentage', 0)

        if rollout_percentage >= 100:
            return True
        if rollout_percentage <= 0:
            return False

        # Use consistent hashing based on request_id
        import hashlib

        hash_value = int(hashlib.md5(request_id.encode()).hexdigest(), 16)
        threshold = (rollout_percentage / 100) * (2**32)
        return hash_value % (2**32) < threshold

    def save_to_file(self, path: Optional[Path] = None) -> None:
        """Save current feature flags to configuration file.

        Args:
            path: Path to save to (uses config.config_path if None)
        """
        save_path = path or self.config.config_path
        if not save_path:
            raise ValueError('No path provided for saving feature flags')

        try:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with save_path.open('w', encoding='utf-8') as f:
                json.dump(self._flags, f, indent=2)
            logger.info(f'Saved feature flags to {save_path}')
        except Exception as e:
            logger.error(f'Failed to save feature flags to {save_path}: {e}')

    def load_from_file(self, path: Path) -> None:
        """Load feature flags from configuration file.

        Args:
            path: Path to load from
        """
        self.config.config_path = path
        self._load_from_file()


# Global feature flags instance
_global_flags: Optional[FeatureFlags] = None


def get_feature_flags() -> FeatureFlags:
    """Get the global feature flags instance.

    Returns:
        FeatureFlags instance
    """
    global _global_flags
    if _global_flags is None:
        _global_flags = FeatureFlags()
    return _global_flags


def set_feature_flags(flags: FeatureFlags) -> None:
    """Set the global feature flags instance.

    Args:
        flags: FeatureFlags instance to set
    """
    global _global_flags
    _global_flags = flags
