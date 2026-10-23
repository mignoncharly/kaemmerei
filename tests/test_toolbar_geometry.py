"""Viewport movement must neither masquerade as nor conceal a dialog layout shift."""
import pytest

from scripts.browser_layout import (
    CONTRACT_GEOMETRY_FIELDS, contract_geometry, focus_filter_for_measurement, geometry_unchanged,
)


def geometry(width=390, scroll=0):
    return dict(viewport_width=width, viewport_height=1000, page_width=width,
        page_height=4110, client_width=width, client_height=1000,
        scroll_x=0, scroll_y=scroll, row_viewport_x=33, row_viewport_y=650-scroll,
        row_document_x=33, row_document_y=650, row_width=910, row_height=90,
        table_scroll_x=0, table_scroll_y=0)


@pytest.mark.parametrize('width', [390, 768, 1280, 1440])
def test_focus_is_completed_before_dialog_baseline_and_scroll_is_not_layout(width):
    # Reproduce the failure's negative viewport Y after an independent scroll test.
    class Page:
        state = geometry(width, scroll=2266.796875)
        focused = False
        def evaluate(self, expression):
            assert 'scrollX' in expression and 'scrollY' in expression
            return dict(self.state)
        def wait_for_function(self, expression):
            assert self.focused
    page = Page()
    class Toggle:
        def focus(self):
            page.focused = True
            page.state = geometry(width)  # Native focus brings the header into view.
    result = {}
    old_baseline = contract_geometry(page, result, 'before_focus')
    assert old_baseline['row_viewport_y'] == -1616.796875
    baseline = focus_filter_for_measurement(page, Toggle(), result, 'focused_closed')
    opened = contract_geometry(page, result, 'opened')
    assert not geometry_unchanged(old_baseline, opened)
    assert geometry_unchanged(baseline, opened)
    assert result['contract_geometry']['before_focus']['row_document_y'] == baseline['row_document_y']
    assert baseline['scroll_y'] == 0


@pytest.mark.parametrize('field', CONTRACT_GEOMETRY_FIELDS)
def test_dialog_assertion_rejects_changes_in_every_measured_property(field):
    before = geometry()
    after = dict(before)
    after[field] += 3
    assert not geometry_unchanged(before, after)


def test_equal_viewport_y_cannot_hide_simultaneous_reflow_and_scrolling():
    before = geometry()
    after = dict(before, row_document_y=670, scroll_y=20)
    assert before['row_viewport_y'] == after['row_viewport_y']
    assert not geometry_unchanged(before, after)


def test_equal_document_y_does_not_hide_scroll_jump():
    assert not geometry_unchanged(geometry(scroll=100), geometry(scroll=0))


@pytest.mark.parametrize('value', [None, float('nan'), float('inf'), True])
def test_invalid_geometry_is_never_accepted(value):
    assert not geometry_unchanged(geometry(), dict(geometry(), scroll_y=value))


def test_unchanged_overflow_is_still_failure():
    state = dict(geometry(), page_width=816)
    assert not geometry_unchanged(state, state)
