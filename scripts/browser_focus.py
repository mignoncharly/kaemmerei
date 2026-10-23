"""Filter focus diagnostics using only fixed target names; never serialize DOM text."""
import re

TARGETS = {
    'toggle': '#filter-toggle',
    'close': '.contract-filter-dialog [data-filter-close]',
    'search': '#q',
    'department': '#department',
    'contract_type': '#contract_type',
    'contact_person': '#contact_person',
    'deputy': '#deputy_contact_person',
    'status': '#status',
    'tax_review': '#tax_review_status',
    'page_size': '#page_size',
    'apply': '#contract-filter-form button[type=submit]',
    'reset': '#contract-filter-form .advanced-filter-actions a',
}


def focus_snapshot(page, result, name, expected):
    if not re.fullmatch('[a-z][a-z0-9_]{0,99}', name) or expected not in TARGETS:
        raise ValueError('Invalid focus diagnostic identifier')
    state = page.evaluate("""({targets, expected}) => {
        const dialog = document.querySelector('.contract-filter-dialog');
        const active = document.activeElement;
        let actual = !active ? 'none' : active === document.body ? 'body'
            : active === document.documentElement ? 'html' : active === dialog ? 'dialog'
            : dialog?.contains(active) ? 'other_inside' : 'other_outside';
        for (const [name, selector] of Object.entries(targets)) {
            if (active && active === document.querySelector(selector)) { actual = name; break; }
        }
        return {expected_target:expected, actual_target:actual,
            matches_expected:actual === expected, active_in_dialog:!!dialog?.contains(active),
            document_has_focus:document.hasFocus(), dialog_open:!!dialog?.open,
            native_modal:!!dialog?.matches(':modal'), aria_modal:dialog?.getAttribute('aria-modal') === 'true',
            expanded:document.querySelector('#filter-toggle')?.getAttribute('aria-expanded') === 'true',
            controls_dialog:document.querySelector('#filter-toggle')?.getAttribute('aria-controls') === dialog?.id};
    }""", {'targets': TARGETS, 'expected': expected})
    result.setdefault('focus_measurements', {})[name] = state
    return state
