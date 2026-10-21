from app.presentation import safe_values
"""Identity/catalog routes, installed without replacing existing application routes."""
from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.authorization import can_decide_review, contract_query, load_child
from app.identity_service import audit, lock_identities, validate_department_name, validate_password
from app.logic import active_access, can_read
from app.models import (ContactIdentity, Contract, ContractReview, ContractTask, Department, IdentityAudit, LoginAttempt, LoginSession,
                        RecipientMembership, RecipientTeam, Revision, User)
from app.security import (attempt_key, cookie_response, new_session, ph, require_csrf,
                          require_user, throttled, verify_password)


def install_identity_routes(app, *, get_db, html, base_context, user_csrf, check_admin):
    def admin_locked(request, db):
        lock_identities(db)
        user = require_user(request, db)
        check_admin(user)
        return user

    @app.get('/account/password')
    def password_page(request: Request, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        return html(request, 'password.html', base_context(request, user, csrf))

    @app.post('/account/password')
    async def change_password(request: Request, db: Session = Depends(get_db)):
        form = await request.form(max_files=0, max_fields=4)
        request.state.safe_values = safe_values(form)
        lock_identities(db)
        user, csrf = user_csrf(request, db)
        require_csrf(request, db, str(form.get('csrf_token', '')))
        key = attempt_key('password-change:' + user.username, request.client.host if request.client else 'unknown')
        if throttled(db, key):
            raise HTTPException(429, 'Passwortprüfung vorübergehend gesperrt; später erneut versuchen')
        current = str(form.get('current_password', ''))
        if len(current) > 256 or not verify_password(current, user):
            db.add(LoginAttempt(key_hash=key))
            audit(db, user.id, 'password_change_denied', f'user:{user.id}', reason='current_password')
            db.commit()
            return html(request, 'password.html', {**base_context(request, user, csrf),
                        'error': 'Das bisherige Passwort ist nicht korrekt'}, 422)
        try:
            password = validate_password(str(form.get('new_password', '')))
            if verify_password(password, user):
                raise ValueError('Das neue Passwort muss sich vom bisherigen unterscheiden')
            if password != str(form.get('confirm_password', '')):
                raise ValueError('Die neuen Passwörter stimmen nicht überein')
        except ValueError as exc:
            db.rollback()
            return html(request, 'password.html', {**base_context(request, user, csrf), 'error': str(exc)}, 422)
        user.password_hash = ph.hash(password)
        user.must_change_password = False
        db.execute(delete(LoginAttempt).where(LoginAttempt.key_hash == key))
        db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
        _, token = new_session(db, app.state.config.session_hours, user.id)
        audit(db, user.id, 'password_changed', f'user:{user.id}', sessions_revoked=True)
        db.commit()
        return cookie_response(RedirectResponse('/', status_code=303), token,
                               production=app.state.config.production, hours=app.state.config.session_hours)

    @app.get('/admin/identities')
    def identities(request: Request, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        check_admin(user)
        return html(request, 'identities.html', {**base_context(request, user, csrf),
            'departments': db.scalars(select(Department).order_by(Department.name)).all(),
            'contacts': db.scalars(select(ContactIdentity).order_by(ContactIdentity.display_name)).all(),
            'teams': db.scalars(select(RecipientTeam).order_by(RecipientTeam.name)).all(),
            'memberships': db.scalars(select(RecipientMembership)).all(),
            'accounts': db.scalars(select(User).order_by(User.username)).all(),
            'events': db.scalars(select(IdentityAudit).order_by(IdentityAudit.id.desc()).limit(100)).all()})

    @app.post('/admin/identities/{entity}/{identity_id}')
    async def maintain_identity(request: Request, entity: str, identity_id: int, db: Session = Depends(get_db)):
        form = await request.form(max_files=0, max_fields=7)
        request.state.safe_values = safe_values(form)
        actor = admin_locked(request, db)
        require_csrf(request, db, str(form.get('csrf_token', '')))
        model = {'departments': Department, 'contacts': ContactIdentity, 'teams': RecipientTeam}.get(entity)
        if model is None or identity_id < 0:
            raise HTTPException(404, 'Identität nicht gefunden')
        target = db.get(model, identity_id) if identity_id else model()
        if target is None:
            raise HTTPException(404, 'Identität nicht gefunden')
        try:
            field = 'display_name' if entity == 'contacts' else 'name'
            before = {} if not identity_id else {field: getattr(target, field), 'is_active': target.is_active}
            name = str(form.get('name', '')).strip()
            if entity == 'departments':
                name = validate_department_name(name)
            elif not name or len(name) > (160 if entity == 'contacts' else 150):
                raise ValueError('Bitte einen gültigen Namen angeben')
            setattr(target, field, name)
            target.is_active = form.get('is_active') == '1'
            if entity == 'contacts':
                raw_department, raw_user = form.get('department_id', ''), form.get('user_id', '')
                department = db.get(Department, int(raw_department)) if raw_department else None
                account = db.get(User, int(raw_user)) if raw_user else None
                if raw_department and department is None or raw_user and account is None:
                    raise ValueError('Fachbereich oder Benutzer nicht vorhanden')
                # Existing catalog IDs keep their scope. Move by creating a new
                # identity; never turn a private backfilled name into a global one.
                scope = department.id if department else None
                if identity_id and target.department_id != scope:
                    raise ValueError('Der Geltungsbereich einer Identität ist unveränderlich')
                target.department_id, target.scope_key = scope, scope or 0
                target.user_id = account.id if account else None
            db.add(target)
            db.flush()
            if entity == 'departments' and not target.is_active:
                ids = select(User.id).where(User.role == 'department', User.department_id == target.id)
                db.execute(delete(LoginSession).where(LoginSession.user_id.in_(ids)))
                # Scoped tokens are suspended by the live department gate, not
                # irreversibly revoked. Reactivation restores their prior state.
            if entity == 'teams' and not target.is_active:
                ids = select(RecipientMembership.user_id).where(RecipientMembership.team_id == target.id)
                db.execute(delete(LoginSession).where(LoginSession.user_id.in_(ids)))
            audit(db, actor.id, entity + ('_updated' if identity_id else '_created'),
                  f'{entity}:{target.id}', before=before, after={field: name, 'is_active': target.is_active},
                  **({'department_id': target.department_id, 'user_id': target.user_id} if entity == 'contacts' else {}))
            db.commit()
        except (ValueError, IntegrityError):
            db.rollback()
            raise HTTPException(422, 'Ungültige oder bereits vorhandene Identität; keine Änderung gespeichert') from None
        return RedirectResponse('/admin/identities', status_code=303)

    @app.post('/admin/recipient-memberships')
    async def membership(request: Request, db: Session = Depends(get_db)):
        form = await request.form(max_files=0, max_fields=4)
        request.state.safe_values = safe_values(form)
        actor = admin_locked(request, db)
        require_csrf(request, db, str(form.get('csrf_token', '')))
        try:
            team_id, user_id = int(form.get('team_id', '')), int(form.get('user_id', ''))
            team, target = db.get(RecipientTeam, team_id), db.get(User, user_id)
            enabled = form.get('is_active') == '1'
            if not team or not target or (enabled and (not team.is_active or not active_access(target))):
                raise ValueError('Aktives Team und aktiver Benutzer erforderlich')
            member = db.get(RecipientMembership, (team_id, user_id))
            if enabled and member is None:
                db.add(RecipientMembership(team_id=team_id, user_id=user_id))
            elif not enabled and member is not None:
                db.delete(member)
            db.execute(delete(LoginSession).where(LoginSession.user_id == user_id))
            audit(db, actor.id, 'recipient_membership_changed', f'team:{team_id}', user_id=user_id, enabled=enabled)
            db.commit()
        except ValueError:
            db.rollback()
            raise HTTPException(422, 'Ungültige Teamzuordnung') from None
        return RedirectResponse('/admin/identities', status_code=303)

    @app.post('/contracts/{contract_id}/reviews/{review_id}/assignment')
    async def assign_review(request: Request, contract_id: int, review_id: int, db: Session = Depends(get_db)):
        from app.workflow import begin_mutation, expected_version
        form = await request.form(max_files=0, max_fields=5)
        request.state.safe_values = safe_values(form)
        actor = admin_locked(request, db)
        require_csrf(request, db, str(form.get('csrf_token', '')))
        begin_mutation(db,actor,contract_id)
        contract, review = load_child(db, actor, contract_id, ContractReview, review_id, lock=True)
        if contract.archived_at is not None:
            raise HTTPException(409, 'Archivierter Vertrag ist schreibgeschützt')
        try:
            expected_version(review,form)
            if not form.get('team_id') and not form.get('user_id'):
                team_id = user_id = None
            else:
                team_id, user_id = int(form.get('team_id', '')), int(form.get('user_id', ''))
                team, target = db.get(RecipientTeam, team_id), db.get(User, user_id)
                if (not team or not team.is_active or not target or not active_access(target) or
                        not target.can_approve or not can_read(target, contract) or
                        db.get(RecipientMembership, (team_id, user_id)) is None):
                    raise ValueError('Explizite Berechtigung, Mitgliedschaft und Vertragszugriff erforderlich')
            before = {key:getattr(review,key) for key in ('team_id','assigned_user_id','status','result_text','content_revision','provenance','version')}
            review.team_id, review.assigned_user_id = team_id, user_id
            review.version+=1
            review.status='open'
            review.result_text=''
            review.content_revision=contract.content_revision
            review.provenance='current'
            contract.approval_provenance='pending'
            if contract.status=='active':
                contract.status='in_progress'
            after = {key:getattr(review,key) for key in before}
            db.add(Revision(contract_id=contract.id, actor_id=actor.id, action='review_assigned',
                            before=before, after=after))
            audit(db, actor.id, 'review_assigned', f'review:{review.id}', before=before, after=after)
            db.commit()
        except ValueError:
            db.rollback()
            raise HTTPException(422, 'Zuweisung ohne Berechtigung oder gültige Teammitgliedschaft abgelehnt') from None
        return RedirectResponse(f'/contracts/{contract.id}', status_code=303)

    @app.get('/reviews')
    def review_inbox(request: Request, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        contract_ids = contract_query(user).where(Contract.archived_at.is_(None)).with_only_columns(Contract.id)
        reviews = db.scalars(select(ContractReview).where(ContractReview.contract_id.in_(contract_ids),
            ContractReview.assigned_user_id==user.id,ContractReview.status.in_(('open','in_review')))
            .order_by(ContractReview.due_date.asc().nulls_last(),ContractReview.id)).all()
        items = [review for review in reviews if can_decide_review(db, user, review.contract, review)
                 and review.content_revision==review.contract.content_revision]
        tasks = db.scalars(select(ContractTask).where(ContractTask.contract_id.in_(contract_ids),
            ContractTask.assigned_user_id==user.id,ContractTask.status!='done')
            .order_by(ContractTask.due_date.asc().nulls_last(),ContractTask.id)).all()
        from datetime import date
        return html(request, 'review_inbox.html', {**base_context(request, user, csrf), 'reviews': items,
                    'tasks':tasks,'today':date.today()})
