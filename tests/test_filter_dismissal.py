"""Native dismissal and its queued close event are separate synchronization stages."""
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from scripts.browser_focus import escape_filter_and_wait, filter_focus_restored


def lifecycle(width):
    # Capture the actual diagnostic and wait expressions without duplicating them.
    class Capture:
        keyboard = SimpleNamespace(press=lambda key: None)
        def evaluate(self, expression, arguments=None):
            if arguments:
                self.expression, self.arguments = expression, arguments
            return {}
        def wait_for_function(self, expression): self.wait_expression = expression
    capture = Capture()
    escape_filter_and_wait(capture, {}, 'case')
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js unavailable: actual close handler regression not executed')
    child = subprocess.run([node, str(Path(__file__).parent/'js/filter_dialog_focus.cjs'), 'dismissal'],
        input=json.dumps(dict(width=width, expression=capture.expression, arguments=capture.arguments,
                             waitExpression=capture.wait_expression)), capture_output=True, text=True, timeout=20)
    assert child.returncode == 0, child.stdout + child.stderr
    return json.loads(child.stdout), capture.wait_expression


@pytest.mark.parametrize('width', [390, 768, 1280, 1440])
def test_waits_for_actual_close_handler_at_all_acceptance_widths(width):
    states, wait_expression = lifecycle(width)
    assert states['before']['actual_target'] == 'reset'
    assert states['immediate']['actual_target'] == 'toggle'
    assert not states['immediate']['dialog_open'] and not states['immediate']['native_modal']
    assert states['immediate']['expanded'] and states['immediate']['scroll_locked']
    assert states['completedImmediately'] is False
    assert states['completedAfterEvent'] is True
    assert not filter_focus_restored(states['immediate'])
    assert filter_focus_restored(states['settled'])
    class Page:
        stage = 'before'
        def __init__(self): self.keyboard = SimpleNamespace(press=self.press)
        def press(self, key):
            assert key == 'Escape'; self.stage = 'immediate'
        def evaluate(self, expression, arguments=None):
            return dict(states[self.stage]) if arguments else None
        def wait_for_function(self, expression):
            assert self.stage == 'immediate' and expression == wait_expression
            self.stage = 'settled'
    result = {}
    final = escape_filter_and_wait(Page(), result, f'admin_escape_{width}')
    assert all(filter_focus_restored(state) for state in final)
    recorded = result['focus_measurements']
    assert recorded[f'admin_escape_{width}_immediate']['expanded'] is True
    assert recorded[f'admin_escape_{width}']['expanded'] is False
    assert recorded[f'admin_escape_{width}_frame']['actual_target'] == 'toggle'


@pytest.mark.parametrize('key,value', [
    ('matches_expected', False), ('document_has_focus', False), ('dialog_open', True),
    ('native_modal', True), ('expanded', True), ('active_in_dialog', True),
    ('trigger_inert', True), ('navigation_open', True), ('scroll_locked', True),
    ('controls_dialog', False), ('trigger_connected', False), ('trigger_visible', False),
    ('trigger_enabled', False), ('trigger_tabbable', False),
])
def test_completed_close_does_not_allow_wrong_focus_or_unusable_trigger(key, value):
    states, _ = lifecycle(768)
    assert not filter_focus_restored(dict(states['settled'], **{key: value}))


def test_missing_close_cleanup_stays_a_timeout_with_partial_evidence():
    states, _ = lifecycle(768)
    class Page:
        keyboard = SimpleNamespace(press=lambda key: None)
        def evaluate(self, expression, arguments=None): return dict(states['immediate'])
        def wait_for_function(self, expression): raise TimeoutError('synthetic missing close event')
    result = {}
    with pytest.raises(TimeoutError): escape_filter_and_wait(Page(), result, 'admin_escape_768')
    assert result['focus_measurements']['admin_escape_768_immediate']['expanded'] is True
    assert 'admin_escape_768' not in result['focus_measurements']
