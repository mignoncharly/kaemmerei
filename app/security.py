"""Opaque server-side sessions, password handling and login rate limiting."""
import hashlib
import secrets
from datetime import timedelta
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session, object_session
from fastapi import HTTPException, Request
from app.models import LoginAttempt, LoginSession, User, now_utc
from app.logic import active_access

COOKIE_NAME = "vertragsregister_session"
ph = PasswordHasher()
# Constant-time-ish password verification for unknown names as well.
DUMMY_HASH = ph.hash("unbekanntes-zufallspasswort")


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def get_login_session(request: Request, db: Session) -> LoginSession | None:
    raw = request.cookies.get(COOKIE_NAME)
    if not raw or len(raw) > 150:
        return None
    record = db.get(LoginSession, hash_value(raw))
    if record is None or record.expires_at <= now_utc():
        return None
    return record


def get_user(request: Request, db: Session) -> User | None:
    login_session = get_login_session(request, db)
    if login_session is None or login_session.user_id is None:
        return None
    if login_session.user is None or not active_access(login_session.user):
        return None
    if db.bind.dialect.name == 'sqlite':
        db.connection().info['actor_id'] = login_session.user.id
    return login_session.user


def require_user(request: Request, db: Session) -> User:
    user = get_user(request, db)
    if user is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    if user.must_change_password and request.url.path not in ('/account/password', '/logout'):
        raise HTTPException(status_code=303, headers={"Location": "/account/password"})
    return user


def require_csrf(request: Request, db: Session, supplied: str) -> LoginSession:
    session = get_login_session(request, db)
    if session is None or not secrets.compare_digest(session.csrf_token, supplied):
        raise HTTPException(status_code=403, detail="Ungültiges Formular-Token")
    return session


def new_session(db: Session, hours: int, user_id: int | None = None) -> tuple[LoginSession, str]:
    raw = secrets.token_urlsafe(48)
    record = LoginSession(token_hash=hash_value(raw), user_id=user_id,
                          csrf_token=secrets.token_hex(32),
                          expires_at=now_utc() + timedelta(hours=hours))
    db.add(record)
    db.flush()
    return record, raw


def cookie_response(response, token: str, *, production: bool, hours: int):
    response.set_cookie(COOKIE_NAME, token, max_age=hours * 3600, httponly=True,
                        secure=production, samesite="lax", path="/")
    return response


def attempt_key(username: str, ip: str) -> str:
    return hash_value(f"{username.strip().casefold()}|{ip}")


def throttled(db: Session, key: str) -> bool:
    fifteen_minutes_ago = now_utc() - timedelta(minutes=15)
    count = db.scalar(select(func.count()).select_from(LoginAttempt).where(
        LoginAttempt.key_hash == key, LoginAttempt.created_at >= fifteen_minutes_ago))
    return count >= 8


def reserve_login(db: Session, username: str, ip: str) -> bool:
    """Reserve work while the caller holds the identity lock, before Argon2.

    Shared database counters expire after 15 minutes; no permanent account lock.
    Successful credentials do not erase the aggregate spraying budget.
    """
    from ipaddress import ip_address, ip_network
    try:
        address = ip_address(ip)
        network = str(ip_network(f'{address}/{24 if address.version==4 else 64}', strict=False))
    except ValueError:
        network = 'unknown'
    dimensions = [('account', username.strip().casefold(), 32), ('ip',ip,32),
                  ('network',network,128), ('global','all',512)]
    cutoff = now_utc() - timedelta(minutes=15)
    keys = [(hash_value(f'login-budget:{kind}:{value}'), limit) for kind,value,limit in dimensions]
    counts = dict(db.execute(select(LoginAttempt.key_hash,func.count()).where(
        LoginAttempt.key_hash.in_([key for key,_ in keys]), LoginAttempt.created_at>=cutoff
    ).group_by(LoginAttempt.key_hash)).all())
    if any(counts.get(key,0)>=limit for key,limit in keys):
        return False
    db.add_all(LoginAttempt(key_hash=key) for key,_ in keys)
    db.flush()
    return True


def record_failure(db: Session, key: str) -> None:
    db.add(LoginAttempt(key_hash=key))
    db.commit()


def clear_failures(db: Session, key: str) -> None:
    db.execute(delete(LoginAttempt).where(LoginAttempt.key_hash == key))
    db.commit()


def verify_password(password: str, user: User | None) -> bool:
    try:
        db = object_session(user) if user else None
        if db is not None and db.info.get('enforce_rls'):
            stored = db.scalar(text('SELECT ohvr_security.password_hash(:id)'), {'id':user.id})
        else:
            stored = user.password_hash if user else None
        ph.verify(stored or DUMMY_HASH, password)
        return user is not None
    except (VerifyMismatchError, VerificationError):
        return False
