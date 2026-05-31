from __future__ import annotations

import json

from teaagent.ergonomics.run_summary import summarize_run


def test_summarize_run_counts_tools_and_files(tmp_path) -> None:
    root = tmp_path
    run_id = 'abc123'
    (root / '.teaagent' / 'undo').mkdir(parents=True)
    (root / '.teaagent' / 'undo' / f'{run_id}.jsonl').write_text(
        '\n'.join(
            [
                json.dumps(
                    {'path': 'a.txt', 'existed_before': True, 'content_b64': 'AA=='}
                ),
                json.dumps(
                    {'path': 'b.txt', 'existed_before': False, 'content_b64': None}
                ),
                json.dumps(
                    {'path': 'a.txt', 'existed_before': True, 'content_b64': 'AA=='}
                ),
            ]
        )
        + '\n',
        encoding='utf-8',
    )
    events = [
        {
            'event_type': 'tool_call_started',
            'payload': {'annotations': {'read_only': True}},
        },
        {
            'event_type': 'tool_call_started',
            'payload': {'annotations': {'read_only': False}},
        },
        {
            'event_type': 'tool_call_started',
            'payload': {'annotations': {'read_only': False}},
        },
    ]
    summary = summarize_run(
        root=root,
        run_id=run_id,
        events=events,
        cost_cents=42.0,
        input_tokens=10,
        output_tokens=5,
        budget_cap_cents=100,
    )
    assert summary['tool_calls_total'] == 3
    assert summary['tool_calls_read'] == 1
    assert summary['tool_calls_write'] == 2
    assert summary['files_changed_count'] == 2
    assert summary['files_changed'] == ['a.txt', 'b.txt']
