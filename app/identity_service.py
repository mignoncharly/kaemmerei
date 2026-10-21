"""Identity validation and transactional administration shared by CLI and web.

Callers commit once after mutation and audit. Never put secrets in audit details.
"""
from sqlalchemy import delete, select, update
from app.logic import active_access
from app.models import Department, IdentityAudit, IdentityGuard, LoginSession, User
from app.security import ph


def lock_identities(db):
    # One pre-existing row serializes last-admin/membership changes on PostgreSQL
    # and acquires SQLite's writer lock. All identity writers use the same lock.
    if db.execute(update(IdentityGuard).where(IdentityGuard.id == 1).values(
            epoch=IdentityGuard.epoch + 1)).rowcount != 1:
        raise ValueError('Identity administration migration is required')
    db.expire_all()


def audit(db, actor_id, action, target, **details):
    db.add(IdentityAudit(actor_id=actor_id, principal='user' if actor_id else 'operator',
                         action=action, target=str(target), details=details,
                         outcome='denied' if action.endswith('_denied') else 'success'))


def validate_password(password):
    if not 12 <= len(password) <= 256:
        raise ValueError('Passwörter müssen 12 bis 256 Zeichen lang sein')
    return password


def validate_department_name(name):
    name = str(name).strip()
    if not name or len(name) > 150:
        raise ValueError('Fachbereich muss 1–150 Zeichen haben')
    return name


def validate_user_fields(form, db, existing=None):
    username = str(form.get('username', '')).strip().casefold()
    if (not username or len(username) > 80 or
            not username.replace('_', 'a').replace('-', 'a').replace('.', 'a').isalnum()):
        raise ValueError('Ungültiger Benutzername (1–80 Zeichen)')
    if existing and username != existing.username:
        raise ValueError('Benutzername und Identität sind unveränderlich')
    duplicate = db.scalar(select(User).where(User.username == username))
    if duplicate and (existing is None or duplicate.id != existing.id):
        raise ValueError('Dieser Benutzername ist bereits vergeben')
    role = str(form.get('role', ''))
    if role not in ('admin', 'reviewer', 'department'):
        raise ValueError('Ungültige Rolle')
    raw = str(form.get('department_id', '') or '').strip()
    department_id = None
    if role != 'department' and raw:
        raise ValueError('Nur Fachbereichsnutzer erhalten eine Fachbereichszuordnung')
    if role == 'department':
        try:
            department_id = int(raw)
        except ValueError:
            raise ValueError('Ein aktiver Fachbereich ist erforderlich') from None
        department = db.get(Department, department_id)
        # Permit retaining an inactive department for a suspended account, never
        # activate a membership against it or silently move legacy records.
        if not department or (not department.is_active and str(form.get('is_active', '')) == '1'):
            raise ValueError('Ein aktiver Fachbereich ist erforderlich')
    password = str(form.get('password', ''))
    if password:
        validate_password(password)
    elif existing is None:
        raise ValueError('Ein Startpasswort ist erforderlich')
    return dict(username=username, role=role, department_id=department_id,
                is_active=str(form.get('is_active', '')) == '1', password=password,
                can_approve=str(form.get('can_approve', '')) == '1')


def save_user(db, form, *, actor_id=None, user_id=None):
    lock_identities(db)
    if actor_id is not None:
        actor = db.get(User, actor_id)
        if not actor or not active_access(actor) or actor.role != 'admin' or actor.must_change_password:
            raise ValueError('Aktive Administration erforderlich')
    target = db.get(User, user_id) if user_id else None
    if user_id and target is None:
        raise ValueError('Benutzer nicht vorhanden')
    values = validate_user_fields(form, db, target)
    removes_admin = target and target.role == 'admin' and target.is_active and not (
        values['role'] == 'admin' and values['is_active'])
    if removes_admin:
        admins = db.scalars(select(User.id).where(User.role == 'admin', User.is_active.is_(True))).all()
        if len(admins) <= 1:
            raise ValueError('Der letzte aktive Administrator darf nicht gesperrt oder zurückgestuft werden')
    if actor_id == user_id and removes_admin:
        raise ValueError('Das eigene Administratorkonto darf hier nicht gesperrt oder zurückgestuft werden')
    before = None if target is None else {key: getattr(target, key) for key in
                                         ('role', 'department_id', 'is_active', 'can_approve')}
    created = target is None
    if created:
        target = User(username=values['username'])
        db.add(target)
    for field in ('role', 'department_id', 'is_active', 'can_approve'):
        setattr(target, field, values[field])
    if values['password']:
        target.password_hash = ph.hash(values['password'])
        target.must_change_password = True
    db.flush()
    after = {key: getattr(target, key) for key in ('role', 'department_id', 'is_active', 'can_approve')}
    changed = created or before != after or bool(values['password'])
    if changed:
        db.execute(delete(LoginSession).where(LoginSession.user_id == target.id))
    audit(db, actor_id, 'user_created' if created else 'user_updated', f'user:{target.id}',
          before=before, after=after, password_reset=bool(values['password']))
    return target, changed
