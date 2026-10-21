"""Inventory v2: recorded EUR metadata, no payments or inferred effective history."""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from sqlalchemy import select, text
from app.models import Revision, now_utc


def amount(value):
    if value is None or str(value).strip() == '':
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and 0 <= result <= Decimal('9999999999.99') else None
    except (InvalidOperation, ValueError):
        return None


def aggregate(states):
    groups = defaultdict(lambda: dict(record_count=0, known_count=0, annual=Decimal('0')))
    for state in states:
        direction = state.get('financial_direction')
        basis = state.get('value_basis')
        key = (state['department_id'], direction if direction in ('expense','income') else 'unknown',
               basis if basis in ('net','gross') else 'unknown')
        group = groups[key]
        group['record_count'] += 1
        value = amount(state.get('annual_value'))
        if value is not None:
            group['known_count'] += 1
            group['annual'] += value
    return [dict(department_id=k[0], direction=k[1], basis=k[2], **{**v,
            'annual':v['annual'] if v['known_count'] else None}) for k,v in sorted(groups.items())]


def historical_groups(db, user, cutoff):
    if db.info.get('enforce_rls'):
        return [dict(row) for row in db.execute(text(
            'SELECT * FROM ohvr_security.financial_history(:cutoff)'), {'cutoff': cutoff}).mappings()]
    # SQLite has no multi-role database boundary. Keep this projection internal;
    # production PostgreSQL uses the scoped aggregate function above.
    latest = {}
    for r in db.scalars(select(Revision).where(Revision.created_at <= cutoff,
            Revision.action.in_(('created','updated','archived'))).order_by(Revision.created_at, Revision.id)):
        if 'department_id' in r.after and 'annual_value' in r.after:
            latest[r.contract_id] = r.after
    return aggregate(s for s in latest.values() if not s.get('archived_at') and (
        user.role in ('admin','reviewer') or s.get('department_id') == user.department_id))


def inventory_trend(db, user, today):
    now = now_utc()
    trend = []
    for year in range(max(1, today.year - 4), today.year + 1):
        cutoff = min(datetime(year,12,31,23,59,59,999999), now)
        groups = historical_groups(db,user,cutoff)
        totals = {d:sum((g['annual'] or Decimal('0') for g in groups if g['direction']==d),Decimal('0'))
                  for d in ('expense','income','unknown')}
        trend.append(dict(year=year,expenses=totals['expense'],income=totals['income'],
            unknown=totals['unknown'],groups=groups,observed=bool(groups),
            missing_count=sum(g['record_count']-g['known_count'] for g in groups)))
    peak = max((max(t['expenses'],t['income']) for t in trend), default=Decimal('0'))
    for t in trend:
        t['expense_width'] = int(t['expenses']/peak*100) if peak else 0
        t['income_width'] = int(t['income']/peak*100) if peak else 0
    return trend,peak
