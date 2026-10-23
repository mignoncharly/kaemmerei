"""Numeric layout evidence only: no page text, input values, URLs or DOM dumps."""
import re
import math


CONTRACT_GEOMETRY_FIELDS = (
    'viewport_width', 'viewport_height', 'page_width', 'page_height',
    'client_width', 'client_height', 'scroll_x', 'scroll_y',
    'row_viewport_x', 'row_viewport_y', 'row_document_x', 'row_document_y',
    'row_width', 'row_height', 'table_scroll_x', 'table_scroll_y',
)


def contract_geometry(page, result, name):
    """Record document and viewport coordinates together, before any assertion."""
    if not re.fullmatch('[a-z][a-z0-9_]{0,99}', name):
        raise ValueError('Invalid geometry check name')
    metrics = page.evaluate("""() => {
        const root = document.documentElement;
        const row = document.querySelector('.table-panel tbody tr').getBoundingClientRect();
        const table = document.querySelector('.table-scroll');
        return {viewport_width:innerWidth, viewport_height:innerHeight,
            page_width:root.scrollWidth, page_height:root.scrollHeight,
            client_width:root.clientWidth, client_height:root.clientHeight,
            scroll_x:scrollX, scroll_y:scrollY,
            row_viewport_x:row.x, row_viewport_y:row.y,
            row_document_x:row.x + scrollX, row_document_y:row.y + scrollY,
            row_width:row.width, row_height:row.height,
            table_scroll_x:table.scrollLeft, table_scroll_y:table.scrollTop};
    }""")
    result.setdefault('contract_geometry', {})[name] = metrics
    return metrics


def geometry_unchanged(before, after):
    """Do not mistake scrolling for reflow, or let either mask the other."""
    for field in CONTRACT_GEOMETRY_FIELDS:
        values = (before.get(field), after.get(field))
        if not all(type(v) in (int, float) and math.isfinite(v) for v in values):
            return False
        if abs(values[0] - values[1]) >= 2:
            return False
    return after['page_width'] <= after['viewport_width'] + 1


def focus_filter_for_measurement(page, toggle, result, name):
    # Focus is a separate user action and may legitimately scroll an offscreen
    # trigger into view. Measure opening only AFTER that action, never before it.
    toggle.focus()
    # Playwright caches a function predicate. A bare expression is re-evaluated
    # on each animation frame and can hit script-src's unsafe-eval restriction.
    page.wait_for_function('() => document.activeElement === document.querySelector("#filter-toggle")')
    return contract_geometry(page, result, name)


def table_keyboard_scroll(page, region, result):
    """Exercise real keyboard scrolling; retain the exact failed operation."""
    from scripts.browser_diagnostics import browser_operation
    with browser_operation(result, 'table_check_scrollable', page):
        scrollable = region.evaluate('(e)=>e.scrollWidth>e.clientWidth+1')
    if not scrollable:
        return None
    with browser_operation(result, 'table_press_arrow_right', page):
        page.keyboard.press('ArrowRight')
    with browser_operation(result, 'table_wait_scroll', page):
        page.wait_for_function('() => document.querySelector(".table-scroll").scrollLeft > 0')
    with browser_operation(result, 'table_read_scroll', page):
        return region.evaluate('(e)=>e.scrollLeft>0')


def measure_reflow(page, output, result, name):
    """Save evidence BEFORE a caller asserts; a failed assertion must not lose it."""
    if not re.fullmatch('[a-z][a-z0-9_]{0,99}', name):
        raise ValueError('Invalid layout check name')
    metrics = page.evaluate("""() => {
        const selectors = ['body', '.app-workspace', 'main', '.sidebar',
            '.contract-header-actions', '.contract-filter-dialog', '.table-scroll',
            '.table-scroll table', '.table-scroll th .visually-hidden',
            '.selection-export', '.excel-action-row'];
        const boxes = {};
        for (const selector of selectors) {
            const e = document.querySelector(selector);
            if (!e || !e.getClientRects().length) continue;
            const r = e.getBoundingClientRect(), s = getComputedStyle(e);
            boxes[selector] = {left:r.left, right:r.right, width:r.width,
                clientWidth:e.clientWidth, scrollWidth:e.scrollWidth,
                position:s.position, overflowX:s.overflowX,
                containingBlockInTable:!!e.offsetParent?.closest('.table-scroll')};
        }
        return {viewport:innerWidth, pageWidth:document.documentElement.scrollWidth,
            passed:document.documentElement.scrollWidth <= innerWidth + 1, boxes};
    }""")
    result.setdefault('layout_measurements', {})[name] = metrics
    if not metrics['passed']:
        filename = name + '-failed.png'
        page.screenshot(path=str(output / filename), full_page=True)
        result.setdefault('screenshots', []).append(filename)
    return metrics['passed']
