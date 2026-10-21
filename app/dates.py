"""Calendar display estimates, never evidence that legal cancellation is possible."""
from calendar import monthrange
from datetime import date


def add_months(value: date, months: int) -> date:
    index = (value.year - 1) * 12 + value.month - 1 + months
    if not 0 <= index < 9999 * 12:
        raise ValueError('Calendar result is outside years 0001–9999')
    year, month = divmod(index, 12)
    return date(year + 1, month + 1, min(value.day, monthrange(year + 1, month + 1)[1]))


def calculate_notice_deadline(end_date, months):
    if end_date is None or months is None:
        return None
    if not 0 <= months <= 120:
        raise ValueError('Invalid notice period')
    return add_months(end_date, -months)


def calculate_next_end_date(end_date, renewal_period_months, today=None):
    if end_date is None or renewal_period_months is None:
        return end_date
    if not 1 <= renewal_period_months <= 120:
        raise ValueError('Invalid renewal period')
    today = today or date.today()
    elapsed = max(0, (today.year - end_date.year) * 12 + today.month - end_date.month)
    periods = elapsed // renewal_period_months
    candidate = add_months(end_date, periods * renewal_period_months)
    # Always use the original anchor: February clamping must not drift March.
    return (add_months(end_date, (periods + 1) * renewal_period_months)
            if candidate < today else candidate)


def contract_dates(contract, today=None):
    today = today or date.today()
    try:
        renewal = (contract.renewal_period_months if contract.automatic_renewal
                   and contract.status not in ('terminated', 'ended') else None)
        end = calculate_next_end_date(contract.end_date, renewal, today)
        notice = (calculate_notice_deadline(end, contract.notice_period_months)
                  if contract.status not in ('terminated', 'ended') else None)
        return dict(next_end_date=end, notice_deadline=notice,
                    notice_missed=notice is not None and notice < today,
                    date_error=None, legal_cancellation_verified=False)
    except ValueError:
        # Historical out-of-range data stays visible, with no invented deadline.
        return dict(next_end_date=None, notice_deadline=None, notice_missed=False,
                    date_error='Date calculation outside supported calendar range',
                    legal_cancellation_verified=False)
