"""Transactional human MFA state. Callers hold the identity guard and commit.

PostgreSQL web callers use scoped definer functions; owner-only CLI recovery
uses protected tables directly. SQLite provides application checks only.
"""
from datetime import timedelta
import re
import time
from uuid import uuid4

from sqlalchemy import delete, select, text

from app.identity_service import audit, lock_identities
from app.logic import active_access
from app.models import LoginSession, MfaCredential, MfaPolicy, SecurityEvent, User, now_utc


def required_for(db, user_id):
    if db.info.get('enforce_rls'):
        return bool(db.scalar(text('SELECT ohvr_security.mfa_required_for(:id)'),{'id':user_id}))
    policy=db.get(MfaPolicy,1)
    if policy is None:
        raise ValueError('MFA policy is missing; explicit forward repair required')
    credential=db.get(MfaCredential,user_id)
    return bool((policy and policy.required) or (credential and credential.enabled))


def _event(db, session, action):
    db.add(SecurityEvent(actor_id=session.pending_user_id,principal='user',action=action,
        target=f'user:{session.pending_user_id}',created_at=now_utc(),
        outcome='denied' if action=='MFA_DENIED' else 'success',
        correlation_id=db.info.get('request_context',{}).get('correlation_id') or str(uuid4()),details={}))


def material(db, session, candidate=None):
    if db.info.get('enforce_rls'):
        return db.scalar(text('SELECT ohvr_security.mfa_material(:hash,:candidate)'),
                         {'hash':session.token_hash,'candidate':candidate})
    credential=db.get(MfaCredential,session.pending_user_id)
    if credential is None or (not credential.enabled and (
            credential.authorization_expires_at is None or credential.authorization_expires_at<=now_utc())):
        return None
    if credential.seed_ciphertext is None and candidate is not None and not credential.enabled:
        credential.seed_ciphertext=candidate
        _event(db,session,'MFA_ENROLLMENT_STARTED')
    return dict(user_id=credential.user_id,ciphertext=credential.seed_ciphertext,
                enabled=credential.enabled,last_step=credential.last_step)


def confirm(db, session, step):
    if db.info.get('enforce_rls'):
        return bool(db.scalar(text('SELECT ohvr_security.mfa_confirm(:hash,:step)'),
                              {'hash':session.token_hash,'step':step}))
    credential=db.get(MfaCredential,session.pending_user_id)
    if (credential is None or credential.seed_ciphertext is None or step is None
            or step<=credential.last_step):
        return False
    current_step=int(time.time())//30
    if not current_step-1<=step<=current_step+1:
        return False
    if not credential.enabled and (credential.authorization_expires_at is None or
                                   credential.authorization_expires_at<=now_utc()):
        return False
    enrolling=not credential.enabled
    credential.enabled=True
    credential.last_step=step
    credential.authorization_expires_at=None
    if enrolling:
        db.execute(delete(LoginSession).where(
            ((LoginSession.user_id==credential.user_id)|(LoginSession.pending_user_id==credential.user_id)),
            LoginSession.token_hash!=session.token_hash))
    _event(db,session,'MFA_ENROLLED' if enrolling else 'MFA_VERIFIED')
    return True


def denied(db,session):
    if db.info.get('enforce_rls'):
        db.execute(text('SELECT ohvr_security.mfa_denied(:hash)'),{'hash':session.token_hash})
    else:
        _event(db,session,'MFA_DENIED')


def authorize_enrollment(db, username, reference, *, recovery=False):
    """Explicit operator only, after out-of-band identity verification.

    No security questions, emailed codes, emergency bypass sessions or factor
    disabling endpoint. Recovery requires a fresh password and new enrollment.
    """
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,79}',reference):
        raise ValueError('An approved nonsecret recovery case reference is required')
    lock_identities(db)
    user=db.scalar(select(User).where(User.username==username.strip().casefold()))
    if user is None or not active_access(user):
        raise ValueError('Active account and membership required; recovery never reactivates access')
    credential=db.get(MfaCredential,user.id)
    if credential and credential.enabled and not recovery:
        raise ValueError('Enabled MFA requires the separately audited recovery command')
    if credential is None:
        credential=MfaCredential(user_id=user.id)
        db.add(credential)
    credential.seed_ciphertext=None
    credential.enabled=False
    credential.last_step=-1
    credential.authorization_expires_at=now_utc()+timedelta(hours=24)
    if recovery:
        user.must_change_password=True
    db.execute(delete(LoginSession).where(
        (LoginSession.user_id==user.id)|(LoginSession.pending_user_id==user.id)))
    audit(db,None,'mfa_recovery_authorized' if recovery else 'mfa_enrollment_authorized',
          f'user:{user.id}',reference=reference,identity_verified=True,window_hours=24,sessions_revoked=True)
    return user.id


def enforce_policy(db,reference):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,79}',reference):
        raise ValueError('An approved nonsecret rollout reference is required')
    lock_identities(db)
    policy=db.get(MfaPolicy,1)
    if policy is None:
        raise ValueError('MFA migration is required')
    if not policy.required:
        policy.required=True
        db.execute(delete(LoginSession))
        audit(db,None,'mfa_policy_enabled','local_mfa_policy',reference=reference,sessions_revoked=True)
