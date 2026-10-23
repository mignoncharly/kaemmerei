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
        const toggle = document.querySelector('#filter-toggle');
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
            controls_dialog:toggle?.getAttribute('aria-controls') === dialog?.id,
            trigger_connected:!!toggle?.isConnected,
            trigger_visible:!!toggle?.getClientRects().length && getComputedStyle(toggle).visibility === 'visible',
            trigger_enabled:!!toggle && !toggle.matches(':disabled'),
            trigger_tabbable:!!toggle && toggle.tabIndex >= 0,
            trigger_inert:!!toggle?.closest('[inert]') || (!!dialog?.matches(':modal') && !dialog.contains(toggle)),
            navigation_open:document.body.classList.contains('nav-open'),
            scroll_locked:document.body.classList.contains('contract-filter-open')};
    }""", {'targets': TARGETS, 'expected': expected})
    result.setdefault('focus_measurements', {})[name] = state
    return state


def escape_filter_and_wait(page, result, name):
    focus_snapshot(page, result, name + '_before', 'reset')
    page.keyboard.press('Escape')
    return wait_filter_closed(page, result, name)


def wait_filter_closed(page, result, name):
    """Wait for application close cleanup, not for focus to become conveniently correct.

    Native Escape removes open/modal state and restores focus before its queued
    close event runs. That event updates aria-expanded and the scroll lock.
    """
    focus_snapshot(page, result, name + '_immediate', 'toggle')
    page.wait_for_function("""() => {
        const dialog = document.querySelector('.contract-filter-dialog');
        const toggle = document.querySelector('#filter-toggle');
        return !!dialog && !!toggle && !dialog.open
            && toggle.getAttribute('aria-expanded') === 'false'
            && !document.body.classList.contains('contract-filter-open');
    }""")
    settled = focus_snapshot(page, result, name, 'toggle')
    page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => resolve()))')
    stable = focus_snapshot(page, result, name + '_frame', 'toggle')
    return settled, stable


def filter_focus_restored(state):
    """Completion cannot hide a wrong, missing, disabled or inert return target."""
    return (state['matches_expected'] and state['document_has_focus']
            and not any(state[key] for key in ('dialog_open', 'native_modal', 'expanded',
                        'active_in_dialog', 'trigger_inert', 'navigation_open', 'scroll_locked'))
            and all(state[key] for key in ('controls_dialog', 'trigger_connected',
                        'trigger_visible', 'trigger_enabled', 'trigger_tabbable')))
