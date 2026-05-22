from __future__ import annotations

import platform
import subprocess


def notify(title: str, message: str, *, sound: bool = False) -> bool:
    """Best-effort desktop notification (macOS/Linux)."""
    system = platform.system()
    try:
        if system == 'Darwin':
            script = f'display notification "{_escape(message)}" with title "{_escape(title)}"'
            if sound:
                script += ' sound name "Glass"'
            subprocess.run(['osascript', '-e', script], check=False, timeout=5)
            return True
        if system == 'Linux':
            subprocess.run(
                ['notify-send', title, message],
                check=False,
                timeout=5,
            )
            return True
    except (OSError, subprocess.TimeoutExpired):
        return False
    return False


def _escape(value: str) -> str:
    return value.replace('"', '\\"')
