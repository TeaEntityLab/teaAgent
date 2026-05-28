"""CLI handlers for environment provisioning commands."""

from __future__ import annotations

import argparse
import json
import sys

from teaagent.env_manager import EnvironmentManager


def print_json(value: dict) -> None:
    """Print value as JSON."""
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def env_provision_command(args: argparse.Namespace) -> int:
    """Provision hermetic environment from teaagent.toml."""
    try:
        manager = EnvironmentManager(args.root)
        lockfile = manager.provision()

        print_json(
            {
                'status': 'success',
                'environment_type': lockfile.environment_type,
                'python_version': lockfile.python_version,
                'packages_count': len(lockfile.entries),
                'lockfile_path': str(manager._lockfile_path),
            }
        )
        return 0
    except FileNotFoundError as exc:
        print_json(
            {
                'status': 'error',
                'message': str(exc),
            }
        )
        return 1
    except Exception as exc:
        print_json(
            {
                'status': 'error',
                'message': str(exc),
            }
        )
        return 1


def env_verify_command(args: argparse.Namespace) -> int:
    """Verify environment compliance against lockfile."""
    try:
        manager = EnvironmentManager(args.root)
        is_compliant = manager.verify()

        if is_compliant:
            print_json(
                {
                    'status': 'success',
                    'compliant': True,
                    'message': 'Environment is compliant with lockfile',
                }
            )
            return 0
        else:
            print_json(
                {
                    'status': 'error',
                    'compliant': False,
                    'message': 'Environment is not compliant with lockfile',
                }
            )
            return 1
    except Exception as exc:
        print_json(
            {
                'status': 'error',
                'message': str(exc),
            }
        )
        return 1


def env_lock_command(args: argparse.Namespace) -> int:
    """Generate lockfile from current environment."""
    try:
        manager = EnvironmentManager(args.root)
        spec = manager.load_spec()

        from teaagent.env_config import generate_lockfile, write_lockfile

        lockfile = generate_lockfile(
            spec, f'{sys.version_info.major}.{sys.version_info.minor}'
        )
        write_lockfile(lockfile, manager._lockfile_path)

        print_json(
            {
                'status': 'success',
                'lockfile_path': str(manager._lockfile_path),
                'packages_count': len(lockfile.entries),
            }
        )
        return 0
    except FileNotFoundError as exc:
        print_json(
            {
                'status': 'error',
                'message': str(exc),
            }
        )
        return 1
    except Exception as exc:
        print_json(
            {
                'status': 'error',
                'message': str(exc),
            }
        )
        return 1
