"""Delayed polls must not require repeated eval or conceal automation failures."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts.browser_layout import table_keyboard_scroll, focus_filter_for_measurement
from scripts.browser_diagnostics import execution_details, safe_execution_details, browser_operation


def poll(expression, advance=True):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js unavailable: strict-eval polling model not executed')
    process = subprocess.run([node, str(Path(__file__).parent/'js/poll_predicate.cjs')],
        input=json.dumps(dict(expression=expression, advance=advance)), capture_output=True,
        text=True, timeout=20)
    return process.returncode, json.loads(process.stdout)


def test_old_scroll_expression_fails_on_second_poll_under_strict_eval_policy():
    assert poll('document.querySelector(".table-scroll").scrollLeft>0') == (
        1, {'first': False, 'error': 'EvalError'})


@pytest.mark.parametrize('advance', [True, False])
def test_real_scroll_helper_predicate_survives_delayed_poll_without_fabricating_scroll(advance):
    class Page:
        keys = []
        keyboard = SimpleNamespace(press=lambda key: Page.keys.append(key))
        def wait_for_function(self, expression):
            code, data = poll(expression, advance)
            assert code == 0
            assert data == {'first': False, 'second': advance}
            if not advance:
                raise TimeoutError('SECRET unchanged default timeout')
        def is_closed(self): return False
    region = SimpleNamespace(evaluate=lambda expression: True)
    report = {'checks': ['admin_reset_all_390']}
    if advance:
        assert table_keyboard_scroll(Page(), region, report) is True
        assert 'failed_operation' not in report
    else:
        with pytest.raises(TimeoutError): table_keyboard_scroll(Page(), region, report)
        assert report['failed_operation'] == 'table_wait_scroll'
    assert Page.keys == ['ArrowRight']


def test_non_overflowing_table_does_not_require_scrolling():
    region = SimpleNamespace(evaluate=lambda expression: False)
    assert table_keyboard_scroll(None, region, {}) is None


def test_focus_predicate_also_handles_a_delayed_condition():
    class Page:
        def wait_for_function(self, expression):
            assert poll(expression) == (0, {'first': False, 'second': True})
        def evaluate(self, expression): return {}
    focus_filter_for_measurement(Page(), SimpleNamespace(focus=lambda: None), {}, 'focus')


@pytest.mark.parametrize('operation', ['table_check_scrollable', 'table_press_arrow_right',
                                      'table_wait_scroll', 'table_read_scroll'])
def test_scroll_operation_and_partial_checks_survive_exact_original_exception(operation):
    error = RuntimeError('SECRET Target page, context or browser has been closed')
    def run(name, value=None):
        if name == operation: raise error
        return value
    class Page:
        keyboard = SimpleNamespace(press=lambda key: run('table_press_arrow_right'))
        def wait_for_function(self, expression): run('table_wait_scroll')
        def is_closed(self): return True
    class Region:
        def evaluate(self, expression):
            return run('table_check_scrollable' if 'scrollWidth' in expression else 'table_read_scroll', True)
    report = {'checks': ['admin_reset_all_390']}
    with pytest.raises(RuntimeError) as caught: table_keyboard_scroll(Page(), Region(), report)
    assert caught.value is error
    details = execution_details(error, report)
    assert details['failed_operation'] == operation
    assert details['last_completed_check'] == 'admin_reset_all_390'
    assert details['browser_error_kind'] == 'target_closed'
    assert details['page_closed_at_failure'] is True
    assert details['source_frames'][-1]['file'] == 'scripts/browser_layout.py'
    assert 'SECRET' not in json.dumps(details)


@pytest.mark.parametrize('message,kind', [
    ('EvalError unsafe-eval SECRET', 'csp_eval_blocked'),
    ('Execution context was destroyed SECRET', 'execution_context_destroyed'),
    ('Element is not attached SECRET', 'element_detached'),
    ('strict mode violation SECRET', 'strict_mode_violation'),
    ('SECRET https://private.invalid', 'unclassified'),
])
def test_diagnostic_classifies_without_exporting_exception_text(message, kind):
    details = execution_details(RuntimeError(message), {'checks': []})
    assert details['browser_error_kind'] == kind
    assert details['last_completed_check'] is None
    assert 'SECRET' not in json.dumps(details)


def test_untrusted_child_diagnostic_fields_cannot_export_secrets():
    data = dict(last_completed_check='SECRET', failed_operation='SECRET', browser_error_kind='SECRET',
        page_closed_at_failure='SECRET', source_frames=[
            {'file': 'scripts/browser_layout.py', 'line': 65, 'locals': 'SECRET'},
            {'file': 'C:/secret/password.txt', 'line': 1},
            {'file': 'scripts/browser_layout.py', 'line': True}, 'SECRET'])
    assert safe_execution_details(data, ['admin_reset_all_390']) == {
        'last_completed_check': 'admin_reset_all_390',
        'source_frames': [{'file': 'scripts/browser_layout.py', 'line': 65}]}


def test_failed_diagnostic_does_not_replace_original_error():
    error = RuntimeError('SECRET')
    with pytest.raises(RuntimeError) as caught:
        with browser_operation({}, 'table_wait_scroll', None): raise error
    assert caught.value is error


@pytest.mark.parametrize('module_name', ['verify_contract_toolbar', 'verify_excel_selection'])
def test_browser_report_retains_operation_and_sanitized_stack_on_generic_error(monkeypatch, capsys, module_name):
    from importlib import import_module
    from scripts import pilot_verification
    from tests.support import scratch_directory
    module = import_module('scripts.' + module_name)
    class Error(Exception): pass
    def execute(args, output, report):
        report.update(stage='browser_scenarios', checks=['server_started', 'admin_reset_all_390'])
        class Page:
            keyboard = SimpleNamespace(press=lambda key: None)
            def wait_for_function(self, expression):
                raise Error('Page.wait_for_function: EvalError unsafe-eval SECRET password and URL')
            def is_closed(self): return False
        table_keyboard_scroll(Page(), SimpleNamespace(evaluate=lambda expression: True), report)
    monkeypatch.setattr(module, 'execute', execute)
    monkeypatch.setattr(pilot_verification, 'source_identity', lambda *args: 'a'*40)
    with scratch_directory('ohvr-poll-report-') as directory:
        output = Path(directory) / 'browser'
        monkeypatch.setattr(sys, 'argv', ['browser', '--output', str(output)])
        with pytest.raises(SystemExit) as exited: module.main()
        assert exited.value.code == 1
        report = json.loads((output/'result.json').read_text())
        assert report['last_completed_check'] == 'admin_reset_all_390'
        assert report['failed_operation'] == 'table_wait_scroll'
        assert report['browser_error_kind'] == 'csp_eval_blocked'
        assert report['error_code'] == 'browser_execution_failed' and report['exception_type'] == 'Error'
        assert report['source_frames'][-1]['file'] == 'scripts/browser_layout.py'
        assert report['page_closed_at_failure'] is False
        assert 'failed_check' not in report  # Do not invent a failed assertion.
        assert 'SECRET' not in json.dumps(report) + capsys.readouterr().out


def test_integrated_parent_preserves_safe_failure_location_without_trusting_child_text():
    from scripts.verify_integrated_browsers import SUITES, validate_result
    from tests.support import scratch_directory
    data = dict(source='a'*40, run_id='b'*32, format=SUITES[1][2], synthetic_only=True,
        status='failed', checks=['server_started', 'admin_reset_all_390'],
        error_code='browser_execution_failed', exception_type='Error', failing_stage='browser_scenarios',
        failed_operation='table_wait_scroll', browser_error_kind='csp_eval_blocked',
        last_completed_check='SECRET', diagnostic_summary='SECRET',
        source_frames=[{'file':'scripts/browser_layout.py','line':65,'locals':'SECRET'}])
    with scratch_directory('ohvr-poll-parent-') as directory:
        path = Path(directory)/'result.json'; path.write_text(json.dumps(data))
        passed, result = validate_result(path, 'a'*40, 'b'*32, SUITES[1], 1)
    assert not passed
    assert result['check_count'] == 2 and result['failed_check'] is None
    assert result['failed_operation'] == 'table_wait_scroll'
    assert result['last_completed_check'] == 'admin_reset_all_390'
    assert result['source_frames'] == [{'file':'scripts/browser_layout.py','line':65}]
    assert 'SECRET' not in json.dumps(result)
