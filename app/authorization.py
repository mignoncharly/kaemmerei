"""Shared fail-closed contract queries and explicit review decision authority."""
from fastapi import HTTPException
from sqlalchemy import false, select, true, text
from app.logic import active_access, can_read
from app.models import Contract, IntegrationToken, RecipientMembership, RecipientTeam, User, now_utc


def contract_scope(principal):
    if isinstance(principal, User):
        if not active_access(principal):
            return false()
        if principal.role in ('admin', 'reviewer'):
            return true()
        return Contract.department_id == principal.department_id if principal.role == 'department' else false()
    if isinstance(principal, IntegrationToken):
        if (not principal.is_active or (principal.expires_at and principal.expires_at <= now_utc()) or
                (principal.department_id is not None and
                 (principal.department is None or not principal.department.is_active))):
            return false()
        return true() if principal.department_id is None else Contract.department_id == principal.department_id
    return false()


def contract_query(principal):
    # Authorization includes archived records. Individual views explicitly choose
    # active/archived state; archive never broadens a principal's department scope.
    return select(Contract).where(contract_scope(principal))


def load_contract(db, principal, contract_id, *, lock=False):
    statement = contract_query(principal).where(Contract.id == contract_id)
    if lock:
        if db.info.get('enforce_rls'):
            if not db.scalar(text('SELECT ohvr_security.lock_contract(:id)'), {'id': contract_id}):
                raise HTTPException(404, 'Vertrag nicht gefunden')
        else:
            statement = statement.with_for_update()
    contract = db.scalar(statement.execution_options(populate_existing=True))
    if contract is None:
        raise HTTPException(404, 'Vertrag nicht gefunden')
    return contract


def load_child(db, principal, contract_id, model, child_id, *, lock=False):
    contract = load_contract(db, principal, contract_id, lock=lock)
    child = db.scalar(select(model).where(model.id == child_id, model.contract_id == contract.id))
    if child is None:
        raise HTTPException(404, 'Eintrag nicht gefunden')
    return contract, child


def can_decide_review(db, user, contract, review):
    if not can_read(user, contract) or contract.archived_at is not None:
        return False
    if user.role == 'admin':
        return True
    return bool(user.can_approve and review.assigned_user_id == user.id and review.team_id and
                db.scalar(select(RecipientTeam.id).join(RecipientMembership).where(
                    RecipientTeam.id == review.team_id, RecipientTeam.is_active.is_(True),
                    RecipientMembership.user_id == user.id)))
