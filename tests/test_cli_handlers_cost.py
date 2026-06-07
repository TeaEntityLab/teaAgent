from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch


def _make_args(**overrides: object) -> argparse.Namespace:
    defaults = dict(root='/tmp', last='30d', label=None, pr=None, format='json')
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


@patch('teaagent.cli._handlers._cost.print_json')
@patch('teaagent.cli._handlers._cost.CostTracker')
def test_cost_report_all(mock_tracker: MagicMock, mock_print: MagicMock) -> None:
    from teaagent.cli._handlers._cost import cost_report_command

    mock_tracker.return_value.report_all.return_value = {'total': 42}
    result = cost_report_command(_make_args())

    assert result == 0
    mock_tracker.return_value.report_all.assert_called_once_with(days=30)
    mock_print.assert_called_once_with({'total': 42})


@patch('teaagent.cli._handlers._cost.print_json')
@patch('teaagent.cli._handlers._cost.CostTracker')
def test_cost_report_by_label(mock_tracker: MagicMock, mock_print: MagicMock) -> None:
    from teaagent.cli._handlers._cost import cost_report_command

    mock_tracker.return_value.report_by_label.return_value = {
        'label': 'gpt',
        'cost': 10,
    }
    result = cost_report_command(_make_args(label='gpt'))

    assert result == 0
    mock_tracker.return_value.report_by_label.assert_called_once_with('gpt')
    mock_print.assert_called_once_with({'label': 'gpt', 'cost': 10})


@patch('teaagent.cli._handlers._cost.print_json')
@patch('teaagent.cli._handlers._cost.CostTracker')
def test_cost_report_by_pr(mock_tracker: MagicMock, mock_print: MagicMock) -> None:
    from teaagent.cli._handlers._cost import cost_report_command

    mock_tracker.return_value.report_by_label.return_value = {'pr': 42}
    result = cost_report_command(_make_args(pr=42))

    assert result == 0
    mock_tracker.return_value.report_by_label.assert_called_once_with('pr:42')


@patch('teaagent.cli._handlers._cost.print_json')
@patch('teaagent.cli._handlers._cost.CostTracker')
def test_cost_report_last_7d(mock_tracker: MagicMock, mock_print: MagicMock) -> None:
    from teaagent.cli._handlers._cost import cost_report_command

    mock_tracker.return_value.report_all.return_value = {'total': 0}
    cost_report_command(_make_args(last='7d'))

    mock_tracker.return_value.report_all.assert_called_once_with(days=7)


@patch('teaagent.cli._handlers._cost.print_json')
@patch('teaagent.cli._handlers._cost.CostTracker')
def test_cost_report_last_plain_number_defaults_30(
    mock_tracker: MagicMock, mock_print: MagicMock
) -> None:
    from teaagent.cli._handlers._cost import cost_report_command

    mock_tracker.return_value.report_all.return_value = {'total': 0}
    cost_report_command(_make_args(last='30'))

    mock_tracker.return_value.report_all.assert_called_once_with(days=30)


@patch('teaagent.cli._handlers._cost.print_json')
@patch('teaagent.cli._handlers._cost.CostTracker')
def test_cost_report_output_format_json(
    mock_tracker: MagicMock, mock_print_json: MagicMock
) -> None:
    from teaagent.cli._handlers._cost import cost_report_command

    data = {'total': 42}
    mock_tracker.return_value.report_all.return_value = data
    cost_report_command(_make_args())

    mock_print_json.assert_called_once_with(data)


@patch('teaagent.cli._handlers._cost.CostTracker')
def test_cost_report_csv(mock_tracker: MagicMock) -> None:
    from teaagent.cli._handlers._cost import cost_report_command

    mock_tracker.return_value.report_all.return_value = {}
    mock_tracker.export_csv.return_value = 'name,cost\ntest,42'
    result = cost_report_command(_make_args(format='csv'))

    assert result == 0
    mock_tracker.export_csv.assert_called_once_with({})
