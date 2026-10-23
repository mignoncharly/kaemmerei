"""Numeric layout evidence only: no page text, input values, URLs or DOM dumps."""
import re


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
