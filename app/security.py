"""Opaque server-side sessions, password handling and login rate limiting."""
import hashlib
import secrets
from datetime import timedelta
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
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
    return login_session.user


def require_user(request: Request, db: Session) -> User:
    user = get_user(request, db)
    if user is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
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


def record_failure(db: Session, key: str) -> None:
    db.add(LoginAttempt(key_hash=key))
    db.commit()


def clear_failures(db: Session, key: str) -> None:
    db.execute(delete(LoginAttempt).where(LoginAttempt.key_hash == key))
    db.commit()


def verify_password(password: str, user: User | None) -> bool:
    try:
        ph.verify(user.password_hash if user else DUMMY_HASH, password)
        return user is not None
    except (VerifyMismatchError, VerificationError):
        return False
