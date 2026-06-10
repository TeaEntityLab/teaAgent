"""Update mechanism package for teaagent.

experimental — unwired
"""

from .changelog import (
    ChangeEntry,
    Changelog,
    ChangelogEntry,
    ChangelogFormatter,
    ChangelogLoader,
    ChangeType,
)
from .delta import (
    Delta,
    DeltaApplier,
    DeltaGenerator,
    DeltaManager,
    DeltaMetadata,
    DeltaType,
)
from .installer import (
    UpdateDownloader,
    UpdateInstaller,
    UpdateManager,
    UpdatePackage,
    UpdateProgress,
    UpdateStatus,
)
from .update import (
    UpdateChannel,
    UpdateChecker,
    UpdateInfo,
    UpdateServer,
    Version,
    check_for_updates,
    get_current_version,
)

__all__ = [
    # Changelog
    'ChangeEntry',
    'ChangeType',
    'Changelog',
    'ChangelogEntry',
    'ChangelogFormatter',
    'ChangelogLoader',
    # Delta updates
    'Delta',
    'DeltaApplier',
    'DeltaGenerator',
    'DeltaManager',
    'DeltaMetadata',
    'DeltaType',
    # Update installer
    'UpdateDownloader',
    'UpdateInstaller',
    'UpdateManager',
    'UpdatePackage',
    'UpdateProgress',
    'UpdateStatus',
    # Update check
    'UpdateChannel',
    'UpdateChecker',
    'UpdateInfo',
    'UpdateServer',
    'Version',
    'check_for_updates',
    'get_current_version',
]
