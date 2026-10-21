"""Shared API work budgets, including invalid/rotating credentials."""
from datetime import timedelta
from sqlalchemy import select, func, text
from app.models import LoginAttempt, now_utc
from app.security import hash_value


def reserve_api(factory, *, enforced, credential, address):
    keys = [hash_value('api:principal:'+credential), hash_value('api:address:'+address), hash_value('api:global')]
    with factory() as db:
        if enforced:
            allowed = db.scalar(text('SELECT ohvr_security.consume_api_rate(:p,:a,:g)'),
                dict(zip(('p','a','g'),keys)))
        else:
            from app.identity_service import lock_identities
            lock_identities(db)
            counts = dict(db.execute(select(LoginAttempt.key_hash,func.count()).where(
                LoginAttempt.key_hash.in_(keys), LoginAttempt.created_at>=now_utc()-timedelta(minutes=1)
            ).group_by(LoginAttempt.key_hash)).all())
            allowed = all(counts.get(key,0)<limit for key,limit in zip(keys,(120,240,1200)))
            if allowed:db.add_all(LoginAttempt(key_hash=key) for key in keys)
        db.commit()
        return bool(allowed)
