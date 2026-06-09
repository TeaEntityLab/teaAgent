#!/usr/bin/env python3
"""
OpenCode Gap Watch - Monthly Monitoring Script

This script automates the monthly OpenCode monitoring process defined in
docs/processes/opencode-gap-watch.md

Usage:
    python3 scripts/opencode_gap_watch.py [--update-docs]
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path


def _api_fallback(label: str, exc: Exception) -> dict:
    print(f'  Warning: {label} unavailable ({exc})')
    return {}


def check_opencode_releases():
    """Check OpenCode GitHub for new releases."""
    print('Checking OpenCode GitHub releases...')
    try:
        from _github_api import get_latest_release_tag, repo_from_env

        owner, repo = repo_from_env('OPENCODE_GITHUB_REPO', 'anomalyco/opencode')
        latest = get_latest_release_tag(owner, repo)
        return {
            'latest_release': latest or 'none',
            'new_releases': [latest] if latest else [],
        }
    except Exception as exc:
        return {
            'latest_release': 'unavailable',
            'new_releases': [],
            **_api_fallback('releases', exc),
        }


def check_opencode_issues():
    """Check OpenCode issues for governance discussions."""
    print('Checking OpenCode issues for governance discussions...')
    try:
        from _github_api import repo_from_env, search_issues

        owner, repo = repo_from_env('OPENCODE_GITHUB_REPO', 'anomalyco/opencode')
        query = (
            f'repo:{owner}/{repo} is:issue '
            '(approval OR audit OR permission OR governance) in:title,body'
        )
        items = search_issues(query, per_page=10)
        governance_issues = [
            {
                'title': item.get('title', ''),
                'url': item.get('html_url', ''),
                'state': item.get('state', ''),
            }
            for item in items
        ]
        high_vote_issues = [
            {
                'title': item.get('title', ''),
                'votes': int(item.get('comments', 0) or 0),
                'url': item.get('html_url', ''),
            }
            for item in items
            if int(item.get('comments', 0) or 0) >= 10
        ]
        return {
            'governance_issues': governance_issues,
            'high_vote_issues': high_vote_issues,
        }
    except Exception as exc:
        return {
            'governance_issues': [],
            'high_vote_issues': [],
            **_api_fallback('issues', exc),
        }


def check_opencode_community():
    """Check OpenCode community posts for governance requests."""
    print('Checking OpenCode community posts...')
    # Community platform checks require additional API integrations
    # For now, return placeholder
    return {'reddit_mentions': [], 'discord_mentions': []}


def escalate_if_needed(findings):
    """Check if escalation triggers are met."""
    escalation_triggers = []

    # Check for governance feature implementation
    if findings.get('governance_features'):
        escalation_triggers.append('Governance feature implementation detected')

    # Check for high-vote governance issues
    high_vote_issues = findings.get('high_vote_issues', [])
    for issue in high_vote_issues:
        if issue.get('votes', 0) >= 50:
            escalation_triggers.append(
                f'High-vote governance issue: {issue.get("title")}'
            )

    # Check for strategic alignment shifts
    if findings.get('positioning_shift'):
        escalation_triggers.append('Strategic alignment shift detected')

    # Check for feature parity
    if findings.get('feature_parity'):
        escalation_triggers.append('Feature parity with TeaAgent detected')

    return escalation_triggers


def update_tracking_log(findings, escalation_triggers, update_docs=False):
    """Update the tracking log in the process document."""
    process_doc = Path('docs/processes/opencode-gap-watch.md')

    if not update_docs:
        print('Dry run - would update tracking log with:')
        print(f'  Date: {datetime.now().strftime("%Y-%m-%d")}')
        print(f'  Findings: {findings}')
        print(f'  Escalation required: {"Yes" if escalation_triggers else "No"}')
        if escalation_triggers:
            print(f'  Triggers: {escalation_triggers}')
        return

    # Check if all findings are placeholders - skip document update if so
    def is_placeholder_data(data):
        """Check if data contains only placeholder values."""
        if isinstance(data, dict):
            return all(is_placeholder_data(v) for k, v in data.items() if k != 'date')
        elif isinstance(data, list):
            return len(data) == 0
        else:
            return data == 'TBD'

    if is_placeholder_data(findings):
        print('All findings are placeholders - skipping document update')
        return

    # Implement actual document update
    if not process_doc.exists():
        print(f'Process document not found: {process_doc}')
        return

    try:
        content = process_doc.read_text(encoding='utf-8')
        # Append new tracking log entry
        new_entry = f'\n## {datetime.now().strftime("%Y-%m-%d")}\n\n'
        new_entry += f'**Findings:** {findings}\n\n'
        if escalation_triggers:
            new_entry += (
                f'**Escalation Required:** Yes\n**Triggers:** {escalation_triggers}\n\n'
            )
        else:
            new_entry += '**Escalation Required:** No\n\n'

        # Append to the document
        process_doc.write_text(content + new_entry, encoding='utf-8')
        print(f'Updated {process_doc} with new tracking log entry')
    except Exception as exc:
        print(f'Failed to update document: {exc}')


def main():
    parser = argparse.ArgumentParser(
        description='OpenCode Gap Watch monthly monitoring'
    )
    parser.add_argument(
        '--update-docs',
        action='store_true',
        help='Update the process document with findings (default: dry run)',
    )
    args = parser.parse_args()

    print(f'OpenCode Gap Watch - {datetime.now().strftime("%Y-%m-%d")}')
    print('=' * 60)

    # Run monitoring checks
    releases = check_opencode_releases()
    issues = check_opencode_issues()
    community = check_opencode_community()

    findings = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'releases': releases,
        'issues': issues,
        'community': community,
    }

    # Check for escalation triggers
    escalation_triggers = escalate_if_needed(findings)

    # Update tracking log
    update_tracking_log(findings, escalation_triggers, args.update_docs)

    # Report escalation status
    if escalation_triggers:
        print('\n⚠️  ESCALATION REQUIRED')
        for trigger in escalation_triggers:
            print(f'  - {trigger}')
        print('\nNext steps:')
        print('  1. Document findings with evidence')
        print('  2. Update docs/backlog-priority.md CP-4 section')
        print('  3. Determine response strategy')
        return 1
    else:
        print('\n✅ No escalation required')
        return 0


if __name__ == '__main__':
    sys.exit(main())
