"""Execute the real focus handler and diagnostic expression without a browser driver.

Native inertness, Escape, rendering and actual Tab navigation remain browser gates.
"""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from scripts.browser_focus import focus_snapshot

HARNESS = Path(__file__).parent / 'js' / 'filter_dialog_focus.cjs'


@pytest.fixture
def node():
    executable = shutil.which('node')
    if not executable:
        pytest.skip('Node.js unavailable: real JavaScript focus regression not executed')
    return executable


def test_actual_filter_dialog_keyboard_handler(node):
    # node:test runs in this process; no unnecessary per-file worker is needed.
    result = subprocess.run([node, '--test-reporter=tap', str(HARNESS)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '# tests 10' in result.stdout


@pytest.mark.parametrize('active,expected_actual,contained', [
    ('close', 'close', True), ('reset', 'reset', True), ('search', 'search', True),
    ('toggle', 'toggle', False), ('body', 'body', False),
    ('outside', 'other_outside', False), ('inside', 'other_inside', True),
])
def test_focus_diagnostics_record_actual_target_without_reading_sensitive_dom(node, active, expected_actual, contained):
    class Page:
        def evaluate(self, expression, arguments):
            # DOM double throws on any value/text/markup read, including unknown targets.
            result = subprocess.run([node, str(HARNESS), 'diagnostics'], input=json.dumps(
                dict(expression=expression, arguments=arguments, active=active)),
                capture_output=True, text=True, timeout=20)
            assert result.returncode == 0, 'Diagnostic must not access sensitive DOM data'
            return json.loads(result.stdout)
    report = {}
    state = focus_snapshot(Page(), report, 'admin_after_tab_390', 'close')
    assert report['focus_measurements']['admin_after_tab_390'] == state
    assert state == dict(expected_target='close', actual_target=expected_actual,
        matches_expected=active == 'close', active_in_dialog=contained,
        document_has_focus=True, dialog_open=True, native_modal=True,
        aria_modal=True, expanded=True, controls_dialog=True)


@pytest.mark.parametrize('name,expected', [('invalid secret', 'close'), ('valid', 'secret-value')])
def test_diagnostics_reject_dynamic_identifiers(name, expected):
    report = {}
    with pytest.raises(ValueError, match='Invalid focus diagnostic identifier'):
        focus_snapshot(None, report, name, expected)
    assert report == {}
