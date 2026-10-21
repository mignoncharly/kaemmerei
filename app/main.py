from app.request_boundary import parsed_form
"""Server-rendered, department-scoped contract register (no external services)."""
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import os
from pathlib import Path
from types import SimpleNamespace
import secrets
from urllib.parse import quote, urlencode
from urllib.parse import urlsplit
from uuid import uuid4
from zipfile import BadZipFile

from fastapi import Depends, FastAPI, HTTPException, Request, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import case, delete, func, select, update, text
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.exc import IntegrityError, TimeoutError as PoolTimeout, OperationalError
from sqlalchemy.orm import Session, joinedload
from starlette.datastructures import UploadFile
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from app.presentation import safe_values, review_options, FIELD_LABELS

from app.workflow import begin_mutation, lock_actor, expected_version, material_change, decide, activation, tax_values, submission, WorkflowConflict, MATERIAL_FIELDS
from app.documents import ensure_storage, stage_upload, new_document, process_document, download_response, audit_denied, ClamAVScanner, MEDIA
from app.models import ReviewDecision
from app.config import Settings, get_settings
from app.authorization import can_decide_review, contract_query, contract_scope, load_child, load_contract
from app.identity_service import audit, lock_identities, save_user, validate_user_fields
from app.db import make_engine, make_session_factory
from app.excel import EXPORT_COLUMNS, MAX_IMPORT_ROWS, excel_date, make_xlsx, read_xlsx
from app.logic import ValidationError, active_access, can_read, can_write, snapshot, validate_data
from app.dates import add_months, calculate_notice_deadline, calculate_next_end_date, contract_dates
from app.financial import current_groups, inventory_trend
from app.listing import normalize_filters, filtered_contracts, EXPORT_MAX_ROWS
from app.models import (ContactIdentity, Contract, ContractDocument, ContractReview, ContractTask, Department,
                        IntegrationToken, LoginAttempt, LoginSession, RecipientTeam, Revision, User, now_utc)
from app.options import (CONTACT_PERSONS, CONTRACT_STATUSES, CONTRACT_TYPES, FINANCIAL_DIRECTIONS,
                         PAYMENT_INTERVALS, REVIEW_RECIPIENTS, CONTRACT_REVIEW_STATUSES,
                         TASK_KINDS, TASK_STATUSES, TAX_REVIEW_STATUSES)
from app.security import (COOKIE_NAME, attempt_key, clear_failures, cookie_response,
                          get_login_session, get_user, hash_value, new_session, record_failure,
                          ph, require_csrf, require_user, throttled, verify_password, reserve_login)

BASE = Path(__file__).resolve().parent
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
MAX_DOCUMENTS_PER_UPLOAD = 5
REMINDER_WINDOW_DAYS = 90
DOCUMENT_TYPES = MEDIA
TEMPLATES = Jinja2Templates(directory=str(BASE / "templates"))
TEMPLATES.env.globals['recovery_labels']=FIELD_LABELS
TEMPLATES.env.globals['new_request_id']=lambda: str(uuid4())
TEMPLATES.env.filters["euro"] = lambda amount: format_euro(amount)
SUCCESS_NOTICES = {
    "login": "Anmeldung erfolgreich.",
    "logout": "Sie wurden erfolgreich abgemeldet.",
    "created": "Der Vertrag wurde erfolgreich angelegt.",
    "imported": "Der Excel-Import wurde erfolgreich abgeschlossen.",
    "updated": "Die Vertragsänderungen wurden erfolgreich gespeichert.",
    "archived": "Der Vertrag wurde erfolgreich archiviert.",
    "document_uploaded": "Unterlagen wurden zum Vertrag hinzugefügt.",
    "task_created": "Die Aufgabe wurde angelegt.",
    "task_updated": "Die Aufgabe wurde aktualisiert.",
    "review_created": "Der Vertrag wurde zur Prüfung weitergeleitet.",
    "review_updated": "Der Prüf- und Freigabestatus wurde gespeichert.",
    "user_created": "Benutzer wurde angelegt.",
    "user_updated": "Benutzer und Berechtigungen wurden gespeichert.",
    "integration_revoked": "Der API-Zugriff wurde widerrufen.",
}
USER_ROLES = (
    ("department", "Fachbereichsnutzer"),
    ("reviewer", "Leseberechtigung; Freigaben nur mit expliziter Zuweisung"),
    ("admin", "Administrator"),
)
ROLE_LABELS = dict(USER_ROLES)
TASK_KIND_LABELS = dict(TASK_KINDS)
TASK_STATUS_LABELS = dict(TASK_STATUSES)
TAX_REVIEW_LABELS = dict(TAX_REVIEW_STATUSES)
CONTRACT_REVIEW_STATUS_LABELS = dict(CONTRACT_REVIEW_STATUSES)


def get_db(request: Request):
    factory = request.app.state.integration_session_factory if request.scope['path'].startswith('/api/') else request.app.state.session_factory
    with factory() as db:
        cookie = request.cookies.get(COOKIE_NAME,'')
        scheme, _, credential = request.headers.get('authorization','').partition(' ')
        db.info['enforce_rls'] = request.app.state.config.enforce_database_security
        db.info['request_context'] = {'session_hash':hash_value(cookie) if cookie and len(cookie)<=150 else '',
                                      'token_hash':hash_value(credential) if scheme.casefold()=='bearer' and credential.startswith('ohvr_') and len(credential)<=128 else '',
                                      'correlation_id':getattr(request.state,'correlation_id',str(uuid4()))}
        yield db


def html(request: Request, template: str, context: dict, status_code: int = 200):
    user = context.get('user')
    if template == 'form.html' and user is not None:
        with request.app.state.session_factory() as catalog_db:
            statement = select(ContactIdentity.display_name).where(ContactIdentity.is_active.is_(True))
            if user.role == 'department':
                statement = statement.where((ContactIdentity.department_id == user.department_id) |
                                            ContactIdentity.department_id.is_(None))
            names = catalog_db.scalars(statement).all()
        context = {**context, 'contact_persons': sorted(set(CONTACT_PERSONS) | set(names))}
    notice = SUCCESS_NOTICES.get(request.query_params.get("notice", ""))
    ambiguity = request.query_params.get('ambiguous_rows','')
    if notice:
        if request.query_params.get("notice") == "imported" and request.query_params.get("imported_count", "").isdigit():
            notice += f" {request.query_params.get('imported_count')} Verträge wurden übernommen."
            if ambiguity.isdigit() and 0 < int(ambiguity[:4]) <= MAX_IMPORT_ROWS:
                context['import_warning'] = f'{int(ambiguity[:4])} rows match existing descriptions; review the new records. Descriptions are not unique identities.'
        context = {**context, "notice": notice}
    return TEMPLATES.TemplateResponse(request, template, context, status_code=status_code)


def base_context(request: Request, user: User | None, csrf_token: str = "") -> dict:
    return {"user": user, "csrf_token": csrf_token,
            "contract_types": CONTRACT_TYPES, "contact_persons": CONTACT_PERSONS,
            "contract_statuses": CONTRACT_STATUSES,
            "financial_directions": FINANCIAL_DIRECTIONS,
            "payment_intervals": PAYMENT_INTERVALS,
            "payment_interval_labels": dict(PAYMENT_INTERVALS),
            "tax_review_statuses": TAX_REVIEW_STATUSES,
            "tax_review_labels": TAX_REVIEW_LABELS,
            "review_recipients": REVIEW_RECIPIENTS,
            "contract_review_statuses": CONTRACT_REVIEW_STATUSES,
            "contract_review_status_labels": CONTRACT_REVIEW_STATUS_LABELS,
            "status_labels": dict(CONTRACT_STATUSES)}


def user_csrf(request: Request, db: Session) -> tuple[User, str]:
    user = require_user(request, db)
    session = get_login_session(request, db)
    assert session is not None
    return user, session.csrf_token


def require_integration_token(request: Request, db: Session) -> IntegrationToken:
    scheme, _separator, credential = request.headers.get("authorization", "").partition(" ")
    from app.api_rate import reserve_api
    # Separate short transaction: never commit an application read/sync snapshot.
    if not getattr(request.state,'api_admitted',False):
        if not reserve_api(request.app.state.integration_session_factory,
                enforced=request.app.state.config.enforce_database_security,
                credential=credential[:512], address=request.client.host if request.client else 'unknown'):
            raise HTTPException(429,'API request budget exhausted',headers={'Retry-After':'60'})
        # v2 deliberately authenticates again after its serialization barrier.
        # That revalidation must not start a second independent write transaction.
        request.state.api_admitted=True
    if scheme.casefold() != "bearer" or not credential.startswith("ohvr_") or len(credential) > 128:
        raise HTTPException(status_code=401, detail="Bearer-Token erforderlich",
                            headers={"WWW-Authenticate": "Bearer"})
    if db.info.get('enforce_rls'):
        token_id = db.scalar(text('SELECT ohvr_security.resolve_token(:prefix,:hash)'), {'prefix':credential[:16],'hash':hash_value(credential)})
        token = db.get(IntegrationToken, token_id) if token_id else None
        if token:
            set_committed_value(token, 'token_hash', hash_value(credential))
    else:
        token = db.scalar(select(IntegrationToken).where(IntegrationToken.token_prefix == credential[:16]))
    if (not token or not token.is_active or
            not secrets.compare_digest(token.token_hash, hash_value(credential))):
        raise HTTPException(status_code=401, detail="Ungültiger Integrationstoken",
                            headers={"WWW-Authenticate": "Bearer"})
    if token.expires_at and token.expires_at <= now_utc():
        raise HTTPException(status_code=401, detail="Integrationstoken abgelaufen",
                            headers={"WWW-Authenticate": "Bearer"})
    if token.department_id is not None and (token.department is None or not token.department.is_active):
        raise HTTPException(status_code=401, detail="Integrationstoken deaktiviert",
                            headers={"WWW-Authenticate": "Bearer"})
    if db.info.get('enforce_rls'):
        if db.scalar(text("SELECT ohvr_security.resolve_principal()->>'id'"))!=str(token.id):
            raise HTTPException(401,'Token owner or grant suspended')
    elif token.owner_user_id is not None:
        owner=db.get(User,token.owner_user_id)
        if owner is None or not active_access(owner):raise HTTPException(401,'Token owner suspended')
    if token.revoked_at is not None:raise HTTPException(401,'Token revoked')
    if request.scope['path'].startswith('/api/v1/') and token.api_scopes!='legacy_v1':
        raise HTTPException(403,'This capability token must use API v2')
    request.state.usage_token_id=token.id
    request.state.usage_context=dict(db.info.get('request_context',{}))
    return token


def redirect(target: str):
    return RedirectResponse(target, status_code=303)


def check_read(user: User, contract: Contract):
    if not can_read(user, contract):
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden")


def check_write(user: User, contract: Contract | None = None):
    if not can_write(user, contract):
        raise HTTPException(status_code=403, detail="Keine Schreibberechtigung")


def check_admin(user: User):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Nur Administratoren dürfen Benutzer verwalten")


def form_values(request_form):
    return safe_values(request_form)


def validate_task_fields(form, db: Session, contract: Contract, creating: bool = False) -> dict:
    title = str(form.get("title", "")).strip()
    if not title or len(title) > 160:
        raise ValueError("Bitte einen Aufgabentitel mit höchstens 160 Zeichen angeben")
    kind = str(form.get("kind", "")).strip()
    if kind not in TASK_KIND_LABELS:
        raise ValueError("Bitte eine gültige Aufgabenart auswählen")
    status = str(form.get("status", "open" if creating else "")).strip()
    if status not in TASK_STATUS_LABELS:
        raise ValueError("Bitte einen gültigen Bearbeitungsstatus auswählen")
    description = str(form.get("description", "")).strip()
    if len(description) > 2000:
        raise ValueError("Die Aufgabenbeschreibung darf höchstens 2.000 Zeichen enthalten")
    due_date_text = str(form.get("due_date", "")).strip()
    try:
        due_date = date.fromisoformat(due_date_text) if due_date_text else None
    except ValueError as exc:
        raise ValueError("Bitte ein gültiges Fälligkeitsdatum angeben") from exc
    assignee_text = str(form.get("assigned_user_id", "")).strip()
    assignee = None
    if assignee_text:
        try:
            assignee_id = int(assignee_text)
        except ValueError as exc:
            raise ValueError("Bitte eine gültige zuständige Person auswählen") from exc
        assignee = db.get(User, assignee_id)
        if (not assignee or not assignee.is_active or
                not (assignee.role == "admin" or
                     (assignee.role == "department" and assignee.department_id == contract.department_id))):
            raise ValueError("Die ausgewählte Person ist für diesen Vertrag nicht verfügbar")
    return {"title": title, "kind": kind, "status": status,
            "description": description, "due_date": due_date,
            "assigned_user_id": assignee.id if assignee else None}


def task_snapshot(task: ContractTask) -> dict:
    return {"task_id": task.id, "version":task.version, "task_title": task.title, "task_kind": task.kind,
            "task_status": task.status, "task_description": task.description,
            "task_due_date": task.due_date.isoformat() if task.due_date else "",
            "assigned_to": task.assigned_user.username if task.assigned_user else ""}


def review_snapshot(review: ContractReview) -> dict:
    return {"review_id": review.id, "version":review.version,"content_revision":review.content_revision,"provenance":review.provenance, "recipient": review.recipient,
            "recipient_detail": review.recipient_detail, "subject": review.subject,
            "request_text": review.request_text, "status": review.status,
            "result_text": review.result_text,
            "due_date": review.due_date.isoformat() if review.due_date else ""}


def contract_reminder(contract: Contract, today: date) -> dict | None:
    if contract.status in ("draft", "ended") or contract.end_date is None:
        return None
    dates = contract_dates(contract, today)
    effective_end = dates['next_end_date']
    if effective_end is None:
        return None
    if contract.status != "terminated" and contract.notice_period_months is not None:
        due_date = dates['notice_deadline']
        label = "Rechnerischer Kündigungstermin (unbestätigt)"
    else:
        due_date = effective_end
        label = ("Rechnerischer Laufzeitstichtag"
                 if contract.automatic_renewal and contract.status != "terminated" else "Erfasstes Vertragsende")
    if due_date is None:
        return None
    return {"contract": contract, "due_date": due_date, "label": label,
            "days_remaining": (due_date - today).days}


def split_deadline_reminders(contracts, today: date) -> tuple[list[dict], list[dict]]:
    overdue, upcoming = [], []
    window_end = today + timedelta(days=REMINDER_WINDOW_DAYS)
    for contract in contracts:
        reminder = contract_reminder(contract, today)
        if reminder is None:
            continue
        if reminder["due_date"] < today:
            overdue.append(reminder)
        elif reminder["due_date"] <= window_end:
            upcoming.append(reminder)
    overdue.sort(key=lambda item: item["due_date"])
    upcoming.sort(key=lambda item: item["due_date"])
    return overdue, upcoming


def read_reminder_contracts(db,statement,departments=None):
    columns=(Contract.id,Contract.contract_number,Contract.designation,Contract.department_id,
        Contract.status,Contract.end_date,Contract.notice_period_months,
        Contract.automatic_renewal,Contract.renewal_period_months)
    rows=db.execute(statement.with_only_columns(*columns).where(
        Contract.end_date.is_not(None),Contract.status.not_in(('draft','ended')))).mappings()
    return [SimpleNamespace(**row,department=(departments or {}).get(row['department_id'])) for row in rows]


def listing_spec(db, user, values):
    filters = normalize_filters(values)
    upcoming_ids = []
    if filters['focus'] == 'expiring':
        population = read_reminder_contracts(db,contract_query(user).where(
            Contract.archived_at.is_(None)).order_by(Contract.id))
        _, upcoming = split_deadline_reminders(population, date.today())
        upcoming_ids = [item['contract'].id for item in upcoming]
    return filters, filtered_contracts(user, filters, upcoming_ids=upcoming_ids).order_by(Contract.updated_at.desc(), Contract.id.desc())


def format_euro(amount) -> str:
    raw = f"{amount:,.2f}"
    whole, cents = raw.rsplit(".", 1)
    whole = whole.replace(",", ".")
    return f"{whole}{',' + cents if cents != '00' else ''} €"


def store_uploaded_document(upload: UploadFile, storage_dir: Path, settings=None) -> dict:
    from app.documents import stage_upload_sync
    return stage_upload_sync(upload,storage_dir,settings)


def safe_external_url(settings,document):
    if document.state!='link':return None
    try:return approved_external_url(settings,document.external_url)
    except HTTPException:return None


def approved_external_url(settings,value):
    url=validate_external_document_url(value)
    host=urlsplit(url).hostname.casefold()
    if settings.dms_allowed_hosts and host not in settings.dms_allowed_hosts:
        raise HTTPException(400,'DMS domain is not approved')
    if settings.production and urlsplit(url).scheme!='https':
        raise HTTPException(400,'Production DMS links require HTTPS')
    return url


def validate_external_document_url(value: str) -> str:
    url = value.strip()
    try:
        parsed = urlsplit(url)
        valid = (not any(ord(c)<32 for c in url) and len(url) <= 2048 and parsed.scheme.lower() in ("http", "https")
                 and bool(parsed.hostname) and parsed.username is None and parsed.password is None)
    except ValueError:
        valid = False
    if not valid:
        raise HTTPException(status_code=400, detail="Bitte eine gültige HTTP- oder HTTPS-Adresse ohne Zugangsdaten angeben")
    return url


HISTORY_FIELDS = (
    ("designation", "Vertragsbezeichnung"),
    ("contract_type", "Vertragsart"),
    ("contract_partner", "Vertragspartner"),
    ("relevant_date", "Vertragsbeginn"),
    ("date_description", "Bezeichnung des Datums"),
    ("end_date", "Vertragsende"),
    ("notice_period_months", "Kündigungsfrist"),
    ("automatic_renewal", "Automatische Verlängerung"),
    ("renewal_period_months", "Verlängerungszeitraum"),
    ("contract_value", "Gesamtvertragswert"),
    ("annual_value", "Jahreswert"),
    ("value_basis", "Wertbasis"),
    ("external_reference", "Externe Referenz"),
    ("financial_direction", "Finanzielle Richtung"),
    ("payment_interval", "Zahlungsintervall"),
    ("budget_assignment", "Haushaltszuordnung"),
    ("tax_review_status", "§ 2b UStG-Prüfstatus"),
    ("tax_review_result", "§ 2b UStG-Prüfergebnis"),
    ("tax_reviewed_by", "Geprüft von"),
    ("tax_reviewed_at", "Geprüft am"),
    ("department_id", "Fachbereich"),
    ("contact_person", "Zuständige Person"),
    ("deputy_contact_person", "Vertretung"),
    ("status", "Vertragsstatus"),
)


def history_value(key: str, value, department_names: dict[int, str]) -> str:
    if value is None or value == "":
        return "—"
    if key in ("relevant_date", "end_date"):
        try:
            return date.fromisoformat(str(value)).strftime("%d.%m.%Y")
        except ValueError:
            return str(value)
    if key == "task_due_date":
        try:
            return date.fromisoformat(str(value)).strftime("%d.%m.%Y")
        except ValueError:
            return str(value)
    if key == "due_date":
        try:
            return date.fromisoformat(str(value)).strftime("%d.%m.%Y")
        except ValueError:
            return str(value)
    if key == "tax_reviewed_at":
        try:
            return datetime.fromisoformat(str(value)).strftime("%d.%m.%Y %H:%M") + ' UTC'
        except ValueError:
            return str(value)
    if key in ("annual_value", "contract_value"):
        try:
            return format_euro(Decimal(str(value)))
        except (InvalidOperation, ValueError):
            return str(value)
    if key == "notice_period_months":
        return f"{value} {'Monat' if str(value) == '1' else 'Monate'}"
    if key == "automatic_renewal":
        return "Ja" if value else "Nein"
    if key == "renewal_period_months":
        return f"{value} {'Monat' if str(value) == '1' else 'Monate'}"
    if key == "value_basis":
        return {"net":"Netto","gross":"Brutto","unknown":"Unbekannt"}.get(str(value), str(value))
    if key == "financial_direction":
        return dict(FINANCIAL_DIRECTIONS).get(str(value), str(value))
    if key == "payment_interval":
        return dict(PAYMENT_INTERVALS).get(str(value), str(value))
    if key == "tax_review_status":
        return TAX_REVIEW_LABELS.get(str(value), str(value))
    if key == "department_id":
        try:
            return department_names.get(int(value), f"Fachbereich {value}")
        except (TypeError, ValueError):
            return str(value)
    if key == "status":
        return dict(CONTRACT_STATUSES).get(str(value), str(value))
    if key == "task_kind":
        return TASK_KIND_LABELS.get(str(value), str(value))
    if key == "task_status":
        return TASK_STATUS_LABELS.get(str(value), str(value))
    return str(value)


def build_history(revisions, department_names: dict[int, str]) -> list[dict]:
    labels = {"created": "Vertrag erstellt", "updated": "Vertrag geändert",
              "archived": "Vertrag archiviert", "document_uploaded": "Unterlage hinzugefügt",
              "task_created": "Aufgabe angelegt", "task_updated": "Aufgabe aktualisiert",
              "review_created": "Prüfung weitergeleitet", "review_updated": "Prüfung aktualisiert"}
    entries = []
    for revision in revisions:
        changes = []
        if revision.action == "updated" and revision.before:
            for key, label in HISTORY_FIELDS:
                old = revision.before.get(key)
                new = revision.after.get(key)
                if old != new:
                    changes.append({"label": label,
                                    "before": history_value(key, old, department_names),
                                    "after": history_value(key, new, department_names)})
        if revision.action == "task_updated" and revision.before:
            task_fields = (("task_title", "Aufgabe"), ("task_kind", "Aufgabenart"),
                           ("task_status", "Bearbeitungsstatus"),
                           ("task_description", "Beschreibung"), ("task_due_date", "Fälligkeit"),
                           ("assigned_to", "Zuständig"))
            for key, label in task_fields:
                old = revision.before.get(key)
                new = revision.after.get(key)
                if old != new:
                    changes.append({"label": label,
                                    "before": history_value(key, old, department_names),
                                    "after": history_value(key, new, department_names)})
        if revision.action == "review_updated" and revision.before:
            review_fields = (("recipient", "Prüfstelle"), ("recipient_detail", "Zuständige Stelle"),
                             ("subject", "Betreff"), ("request_text", "Prüfauftrag"),
                             ("status", "Prüfstatus"), ("result_text", "Rückmeldung"),
                             ("due_date", "Frist"))
            for key, label in review_fields:
                old, new = revision.before.get(key), revision.after.get(key)
                if old != new:
                    old_value = CONTRACT_REVIEW_STATUS_LABELS.get(old, old) if key == "status" else history_value(key, old, department_names)
                    new_value = CONTRACT_REVIEW_STATUS_LABELS.get(new, new) if key == "status" else history_value(key, new, department_names)
                    changes.append({"label": label, "before": old_value or "—", "after": new_value or "—"})
        entries.append({
            "action": revision.action,
            "label": labels.get(revision.action, "Änderung"),
            "actor": revision.actor.username,
            "created_at": revision.created_at,
            "changes": changes,
            "contract_number": revision.after.get("contract_number", ""),
            "filename": revision.after.get("filename", ""),
            "size_bytes": revision.after.get("size_bytes"),
            "task_title": revision.after.get("task_title", ""),
            "task_kind": TASK_KIND_LABELS.get(revision.after.get("task_kind", ""), ""),
            "task_status": TASK_STATUS_LABELS.get(revision.after.get("task_status", ""), ""),
            "task_due_date": revision.after.get("task_due_date", ""),
            "review_recipient": revision.after.get("recipient", ""),
            "review_recipient_detail": revision.after.get("recipient_detail", ""),
            "review_subject": revision.after.get("subject", ""),
            "review_status": CONTRACT_REVIEW_STATUS_LABELS.get(revision.after.get("status", ""), ""),
            "version": revision.after.get("version"),
        })
    return entries


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.validate()
    engine = make_engine(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Schema must be migrated separately; don't silently alter production data.
        try:
            if settings.enforce_database_security:
                from app.db_roles import validate_runtime_engine
                validate_runtime_engine(engine, 'web')
                validate_runtime_engine(app.state.integration_engine, 'integration')
            if settings.production:
                from app.server_security import validate_server_security
                for target in {engine,app.state.integration_engine}:
                    validate_server_security(target)
            if settings.mfa_key_file is not None:
                from app.mfa_codec import SeedCipher
                if settings.production:
                    from app.documents import verify_private_acl
                    verify_private_acl(settings.mfa_key_file)
                    verify_private_acl(settings.mfa_key_file.parent)
                app.state.mfa_cipher=SeedCipher(settings.mfa_key_file)
            if settings.human_mfa:
                with app.state.session_factory() as db:
                    if settings.enforce_database_security:
                        enabled=db.scalar(text('SELECT ohvr_security.mfa_policy_required()'))
                    else:
                        from app.models import MfaPolicy
                        policy=db.get(MfaPolicy,1)
                        enabled=policy and policy.required
                    if not enabled:
                        raise ValueError('Owner must explicitly enable database MFA policy before human MFA startup')
            yield
        finally:
            engine.dispose()
            if app.state.integration_engine is not engine:
                app.state.integration_engine.dispose()

    app = FastAPI(title="OPEN.HERZ Vertragsregister", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    @app.exception_handler(WorkflowConflict)
    async def workflow_conflict(request, exc):
        if request.scope['path'].startswith('/api/'):
            return JSONResponse({'detail':'Changed since this form was loaded'},status_code=409)
        return TEMPLATES.TemplateResponse(request=request, name='workflow_conflict.html', context={
            'request':request,'submitted':exc.submitted,'current_version':exc.current_version,
            'reload_url':'/'.join(request.scope['path'].split('/')[:3]),'user':None},status_code=409)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        if 300 <= exc.status_code < 400:
            return Response(status_code=exc.status_code,headers=exc.headers)
        if request.scope['path'].startswith('/api/'):
            return JSONResponse({'detail':exc.detail},status_code=exc.status_code,headers=exc.headers)
        messages={400:'Die Anfrage konnte nicht verarbeitet werden.',401:'Bitte erneut anmelden.',
            403:'Keine Berechtigung oder abgelaufenes Formular. Bitte neu laden und erneut anmelden.',
            404:'Der Eintrag ist nicht vorhanden oder für Sie nicht zugänglich.',
            409:'Der Vorgang steht im Konflikt mit dem aktuellen Zustand. Bitte neu laden.',
            413:'Die Anfrage oder der Export ist zu groß. Bitte den Umfang verkleinern.',
            422:'Bitte die Angaben prüfen und korrigieren.',429:'Zu viele Anfragen. Bitte später erneut versuchen.'}
        return TEMPLATES.TemplateResponse(request=request,name='error.html',context={
            'user':None,'status_code':exc.status_code,'message':messages.get(exc.status_code,'Der Vorgang konnte nicht abgeschlossen werden.'),
            'submitted':getattr(request.state,'safe_values',{}),
            'reload_url':request.scope['path'] if request.method=='GET' else '/'.join(request.scope['path'].split('/')[:3]) or '/'},
            status_code=exc.status_code,headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        if request.scope['path'].startswith('/api/'):
            return JSONResponse({'detail':'Invalid request parameters'},status_code=422)
        return await http_error(request,HTTPException(422))

    @app.exception_handler(PoolTimeout)
    async def database_capacity_error(request, exc):
        return await http_error(request,HTTPException(503,'Database capacity exhausted',headers={'Retry-After':'5'}))

    @app.get('/health/live', include_in_schema=False)
    def live():
        return Response(status_code=204)

    @app.get('/health/ready', include_in_schema=False)
    def ready():
        try:
            for target in {engine, app.state.integration_engine}:
                with target.connect() as connection:
                    connection.execute(text('SELECT 1'))
        except (OperationalError, PoolTimeout):
            return Response(status_code=503)
        return Response(status_code=204)

    app.state.config = settings
    app.state.document_storage_dir = ensure_storage(settings)
    app.state.document_scanner = ClamAVScanner(settings)
    app.state.mfa_cipher = None
    app.state.session_factory = make_session_factory(engine)
    app.state.engine = engine
    app.state.integration_engine = make_engine(replace(settings,database_url=settings.integration_database_url)) if settings.integration_database_url else engine
    app.state.integration_session_factory = make_session_factory(app.state.integration_engine)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))
    app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers['X-OHVR-Business-Rules'] = 'provisional-1; finance=pending; deadlines=pending; disposal=disabled'
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers.setdefault("Content-Security-Policy", (
            "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
            "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"))
        response.headers["Cache-Control"] = "no-store"
        if settings.production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request, db: Session = Depends(get_db)):
        if get_user(request, db):
            return redirect("/")
        login_session = get_login_session(request, db)
        if login_session:
            return html(request, "login.html", {"csrf_token": login_session.csrf_token})
        login_session, token = new_session(db, settings.session_hours)
        db.commit()
        response = html(request, "login.html", {"csrf_token": login_session.csrf_token})
        return cookie_response(response, token, production=settings.production, hours=settings.session_hours)

    @app.post("/login", response_class=HTMLResponse)
    def login(request: Request, db: Session = Depends(get_db)):
        form = parsed_form(request, max_files=0, max_fields=3)
        request.state.safe_values = form_values(form)
        # Serialize credential verification/session creation with password reset
        # and permission changes; no commit may release this lock in between.
        lock_identities(db)
        guest = require_csrf(request, db, str(form.get("csrf_token", "")))
        username = str(form.get("username", "")).strip().casefold()
        password = str(form.get("password", ""))
        ip = request.client.host if request.client else "unknown"
        key = attempt_key(username, ip)
        if len(username) > 80 or len(password) > 512 or throttled(db, key) or not reserve_login(db, username, ip):
            return html(request, "login.html", {"csrf_token": guest.csrf_token, "username": username[:80],
                         "error": "Anmeldung vorübergehend nicht möglich. Bitte später erneut versuchen."}, 429)
        user = db.scalar(select(User).where(User.username == username, User.is_active.is_(True)))
        if not verify_password(password, user) or not active_access(user):
            record_failure(db, key)
            return html(request, "login.html", {"csrf_token": guest.csrf_token, "username": username[:80],
                         "error": "Benutzername oder Passwort ungültig."}, 401)
        db.execute(delete(LoginAttempt).where(LoginAttempt.key_hash == key))
        db.delete(guest)
        db.flush()
        from app.mfa_service import required_for
        needs_mfa=settings.human_mfa or required_for(db,user.id)
        new_login, token = new_session(db, settings.session_hours, None if needs_mfa else user.id,
            pending_user_id=user.id if needs_mfa else None,expires_minutes=5 if needs_mfa else None)
        db.commit()
        return cookie_response(redirect('/account/mfa' if needs_mfa else '/?notice=login'), token,
                               production=settings.production, hours=settings.session_hours,seconds=300 if needs_mfa else None)

    @app.post("/logout")
    def logout(request: Request, db: Session = Depends(get_db)):
        form = parsed_form(request)
        request.state.safe_values = form_values(form)
        login_session = require_csrf(request, db, str(form.get("csrf_token", "")))
        db.delete(login_session)
        db.commit()
        response = redirect("/login?notice=logout")
        response.delete_cookie(COOKIE_NAME, path="/")
        return response

    @app.get("/admin/users", response_class=HTMLResponse)
    def users_page(request: Request, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        check_admin(user)
        users = db.scalars(select(User).order_by(User.username)).all()
        return html(request, "users.html", {**base_context(request, user, csrf),
                    "users": users, "role_labels": ROLE_LABELS})

    def render_integrations(request: Request, user: User, csrf: str, db: Session,
                            new_token: str = "", error: str = "", status_code: int = 200):
        tokens = db.scalars(select(IntegrationToken).order_by(
            IntegrationToken.created_at.desc(), IntegrationToken.id.desc())).all()
        departments = db.scalars(select(Department).where(Department.is_active.is_(True))
                                 .order_by(Department.name)).all()
        return html(request, "integrations.html", {**base_context(request, user, csrf),
                    "tokens": tokens, "departments": departments,
                    "owner_users":db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.username)).all(),
                    "new_token": new_token, "error": error, "now": now_utc(),
                    "notice": "Der API-Token wurde erstellt. Kopiere ihn aus dem grünen Feld." if new_token else ""}, status_code)

    @app.get("/admin/integrations", response_class=HTMLResponse)
    def integrations_page(request: Request, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        check_admin(user)
        return render_integrations(request, user, csrf, db)

    @app.post("/admin/integrations", response_class=HTMLResponse)
    def create_integration(request: Request, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        check_admin(user)
        form = parsed_form(request, max_fields=20)
        request.state.safe_values = form_values(form)
        require_csrf(request, db, str(form.get("csrf_token", "")))
        lock_actor(db,user)
        check_admin(user)
        name = str(form.get("name", "")).strip()
        department_text = str(form.get("department_id", "")).strip()
        expires_in = str(form.get("expires_in", "90"))
        department_id = None
        error = ""
        if not name or len(name) > 120:
            error = "Bitte einen Namen mit höchstens 120 Zeichen angeben."
        elif department_text:
            if not department_text.isdecimal():
                error = "Bitte einen gültigen Fachbereich auswählen."
            else:
                department_id = int(department_text)
                if not db.scalar(select(Department).where(
                        Department.id == department_id, Department.is_active.is_(True))):
                    error = "Der gewählte Fachbereich ist nicht aktiv."
        if expires_in not in ("90", "365", "never"):
            error = "Bitte eine gültige Laufzeit auswählen."
        if error:
            return render_integrations(request, user, csrf, db, error=error, status_code=422)
        from app.token_service import grant_fields
        try:grant=grant_fields(db,form,user)
        except ValueError as exc:return render_integrations(request,user,csrf,db,error=str(exc),status_code=422)
        raw_token = "ohvr_" + secrets.token_urlsafe(32)
        expires_at = (now_utc() + timedelta(days=int(expires_in))
                      if expires_in != "never" else None)
        token=IntegrationToken(name=name, token_prefix=raw_token[:16],
                                token_hash=hash_value(raw_token), department_id=department_id,
                                created_by_id=user.id, expires_at=expires_at,**grant)
        db.add(token);db.flush()
        audit(db,user.id,'integration_created',f'token:{token.id}',scopes=token.api_scopes,owner_user_id=token.owner_user_id)
        db.commit()
        return render_integrations(request, user, csrf, db, new_token=raw_token)

    @app.post("/admin/integrations/{token_id}/revoke")
    def revoke_integration(request: Request, token_id: int, db: Session = Depends(get_db)):
        user, _csrf = user_csrf(request, db)
        check_admin(user)
        form = parsed_form(request, max_fields=2)
        request.state.safe_values = form_values(form)
        require_csrf(request, db, str(form.get("csrf_token", "")))
        lock_actor(db,user)
        check_admin(user)
        token = db.get(IntegrationToken, token_id)
        if not token:
            raise HTTPException(status_code=404, detail="Integrationstoken nicht gefunden")
        token.is_active = False
        reason=str(form.get('reason','administrator_revocation'))
        if reason not in ('administrator_revocation','rotation_complete','service_retired','security_incident'):
            raise HTTPException(422,'Invalid revocation reason')
        token.revoked_at=now_utc();token.revocation_reason=reason
        audit(db,user.id,'integration_revoked',f'token:{token.id}',reason=token.revocation_reason)
        db.commit()
        return redirect("/admin/integrations?notice=integration_revoked")

    @app.get("/api/v1/departments")
    def api_departments(request: Request, db: Session = Depends(get_db)):
        token = require_integration_token(request, db)
        stmt = select(Department).order_by(Department.name)
        if token.department_id is not None:
            stmt = stmt.where(Department.id == token.department_id)
        departments = db.scalars(stmt).all()
        return {"data": [{"id": item.id, "name": item.name} for item in departments]}

    @app.get("/api/v1/contracts")
    def api_contracts(request: Request, limit: int = 100, offset: int = 0,
                      updated_since: str = "", db: Session = Depends(get_db)):
        token = require_integration_token(request, db)
        if not 1 <= limit <= 500 or offset < 0:
            raise HTTPException(status_code=400, detail="limit muss 1–500 und offset mindestens 0 sein")
        since = None
        if updated_since:
            try:
                since = datetime.fromisoformat(updated_since.replace("Z", "+00:00"))
                if since.tzinfo is not None:
                    since = since.astimezone(timezone.utc).replace(tzinfo=None)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="updated_since muss ein ISO-8601-Zeitpunkt sein") from exc
        stmt = contract_query(token)
        if token.department_id is not None:
            stmt = stmt.where(Contract.department_id == token.department_id)
        if since is not None:
            stmt = stmt.where(Contract.updated_at > since)
        total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        contracts = db.scalars(stmt.order_by(Contract.updated_at, Contract.id)
                               .offset(offset).limit(limit)).all()
        contract_ids = [contract.id for contract in contracts]
        documents = (db.scalars(select(ContractDocument).where(
            ContractDocument.contract_id.in_(contract_ids)
        ).order_by(ContractDocument.id)).all() if contract_ids else [])
        documents_by_contract: dict[int, list[ContractDocument]] = {}
        for document in documents:
            documents_by_contract.setdefault(document.contract_id, []).append(document)
        api_root = str(request.base_url).rstrip("/")
        items = [{
            "id": contract.id,
            "contract_number": contract.contract_number,
            "designation": contract.designation,
            "contract_type": contract.contract_type,
            "contract_partner": contract.contract_partner,
            "status": contract.status,
            "archived_at": contract.archived_at.isoformat() + "Z" if contract.archived_at else None,
            "department": {"id": contract.department_id, "name": contract.department.name},
            "relevant_date": contract.relevant_date.isoformat(),
            "end_date": contract.end_date.isoformat() if contract.end_date else None,
            "notice_period_months": contract.notice_period_months,
            "automatic_renewal": contract.automatic_renewal,
            "renewal_period_months": contract.renewal_period_months,
            "calendar_estimate": {k:v.isoformat() if hasattr(v,'isoformat') else v for k,v in contract_dates(contract).items()},
            "annual_value": format(contract.annual_value, "f") if contract.annual_value is not None else None,
            "contract_value": format(contract.contract_value, "f") if contract.contract_value is not None else None,
            "financial_direction": contract.financial_direction,
            "value_basis": contract.value_basis, "external_reference": contract.external_reference,
            "payment_interval": contract.payment_interval,
            "budget_assignment": contract.budget_assignment,
            "contact_person": contract.contact_person,
            "deputy_contact_person": contract.deputy_contact_person,
            "documents": [{
                "id": document.id,
                "filename": document.original_filename,
                "content_type": document.content_type,
                "size_bytes": document.size_bytes,
                "source": "dms" if document.external_url else "upload",
                "external_url": (safe_external_url(request.app.state.config,document) if document.external_url else None),
                "state":document.state,"sha256":document.sha256,
                "download_url": (f"{api_root}/api/v1/contracts/{contract.id}/documents/{document.id}"
                                 if document.state=='available' else None),
            } for document in documents_by_contract.get(contract.id, [])],
            "updated_at": contract.updated_at.isoformat() + "Z",
        } for contract in contracts]
        next_offset = offset + len(items) if offset + len(items) < total else None
        return JSONResponse({"data": items, "total": total, "limit": limit,
                             "offset": offset, "next_offset": next_offset})

    @app.get("/api/v1/contracts/{contract_id}/documents/{document_id}")
    def api_document(request: Request, contract_id: int, document_id: int,
                     db: Session = Depends(get_db)):
        token = require_integration_token(request, db)
        try:
            contract, document = load_child(db, token, contract_id, ContractDocument, document_id)
        except HTTPException:
            audit_denied(db,document_id,token=token)
            raise
        return download_response(db,request.app.state.config,document,request,token=token)

    @app.get("/admin/users/new", response_class=HTMLResponse)
    def new_user_page(request: Request, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        check_admin(user)
        departments = db.scalars(select(Department).where(Department.is_active.is_(True))
                                 .order_by(Department.name)).all()
        return html(request, "user_form.html", {**base_context(request, user, csrf),
                    "mode": "new", "values": {"role": "department", "is_active": True},
                    "departments": departments, "roles": USER_ROLES})

    def render_user_form(request: Request, user: User, csrf: str, db: Session,
                         mode: str, values: dict, target: User | None = None,
                         error: str = "", status_code: int = 200):
        statement = select(Department)
        if target is None:
            statement = statement.where(Department.is_active.is_(True))
        departments = db.scalars(statement.order_by(Department.name)).all()
        return html(request, "user_form.html", {**base_context(request, user, csrf),
                    "mode": mode, "values": values, "target": target,
                    "departments": departments, "roles": USER_ROLES, "error": error}, status_code)

    @app.post("/admin/users/new", response_class=HTMLResponse)
    def create_user(request: Request, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        check_admin(user)
        form = parsed_form(request, max_fields=10)
        request.state.safe_values = form_values(form)
        require_csrf(request, db, str(form.get("csrf_token", "")))
        try:
            values = validate_user_fields(form, db)
        except ValueError as exc:
            return render_user_form(request, user, csrf, db, "new", form_values(form),
                                    error=str(exc), status_code=422)
        try:
            save_user(db, form, actor_id=user.id)
            db.commit()
        except (IntegrityError, ValueError):
            db.rollback()
            return render_user_form(request, user, csrf, db, "new", form_values(form),
                                    error="Dieser Benutzername ist bereits vergeben", status_code=422)
        return redirect("/admin/users?notice=user_created")

    @app.get("/admin/users/{user_id}/edit", response_class=HTMLResponse)
    def edit_user_page(request: Request, user_id: int, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        check_admin(user)
        target = db.get(User, user_id)
        if not target:
            raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
        values = {"username": target.username, "role": target.role,
                  "department_id": target.department_id or "", "is_active": target.is_active,
                  "can_approve": target.can_approve}
        return render_user_form(request, user, csrf, db, "edit", values, target)

    @app.post("/admin/users/{user_id}/edit", response_class=HTMLResponse)
    def update_user(request: Request, user_id: int, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        check_admin(user)
        target = db.get(User, user_id)
        if not target:
            raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
        form = parsed_form(request, max_fields=10)
        request.state.safe_values = form_values(form)
        require_csrf(request, db, str(form.get("csrf_token", "")))
        try:
            target, changed = save_user(db, form, actor_id=user.id, user_id=target.id)
            db.commit()
        except (ValueError, IntegrityError) as exc:
            db.rollback()
            message = str(exc) if isinstance(exc, ValueError) else "Benutzername bereits vergeben"
            return render_user_form(request, user, csrf, db, "edit", form_values(form), target, message, 422)
        if target.id == user.id and changed:
            response = redirect("/login?notice=user_updated")
            response.delete_cookie(COOKIE_NAME, path="/")
            return response
        return redirect("/admin/users?notice=user_updated")

    @app.get("/contracts/import-template.xlsx")
    def download_import_template(request: Request, db: Session = Depends(get_db)):
        user, _csrf = user_csrf(request, db)
        check_write(user)
        headers = [label for _field, label in EXPORT_COLUMNS]
        content = make_xlsx(headers, [])
        return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": 'attachment; filename="vertragsregister_importvorlage.xlsx"'})

    @app.get("/contracts/export.xlsx")
    def export_contracts(request: Request, q: str = "", department: str = "", focus: str = "",
                         contract_type: str = "", contact_person: str = "", deputy_contact_person: str = "",
                         status: str = "", tax_review_status: str = "", db: Session = Depends(get_db)):
        user, _csrf = user_csrf(request, db)
        _filters, stmt = listing_spec(db, user, locals())
        contracts_to_export = db.scalars(stmt.options(joinedload(Contract.department)).limit(EXPORT_MAX_ROWS+1)).all()
        if len(contracts_to_export) > EXPORT_MAX_ROWS:
            raise HTTPException(413, 'Der Export ist auf 5000 Verträge begrenzt. Bitte die Filter eingrenzen.')
        payment_labels = dict(PAYMENT_INTERVALS)
        direction_labels = dict(FINANCIAL_DIRECTIONS)
        tax_labels = dict(TAX_REVIEW_STATUSES)
        status_labels = dict(CONTRACT_STATUSES)
        rows = []
        export_bytes = 0
        from time import monotonic
        export_started = monotonic()
        for contract in contracts_to_export:
            values = {
                "contract_number": contract.contract_number,
                'external_reference': contract.external_reference, 'value_basis': contract.value_basis,
                "designation": contract.designation,
                "contract_type": contract.contract_type,
                "contract_partner": contract.contract_partner,
                "relevant_date": contract.relevant_date,
                "end_date": contract.end_date,
                "notice_period_months": contract.notice_period_months,
                "automatic_renewal": contract.automatic_renewal,
                "renewal_period_months": contract.renewal_period_months,
                "annual_value": contract.annual_value,
                "contract_value": contract.contract_value,
                "financial_direction": direction_labels.get(contract.financial_direction, ""),
                "payment_interval": payment_labels.get(contract.payment_interval, ""),
                "budget_assignment": contract.budget_assignment,
                "tax_review_status": tax_labels.get(contract.tax_review_status, contract.tax_review_status),
                "tax_review_result": contract.tax_review_result,
                "contact_person": contract.contact_person,
                "deputy_contact_person": contract.deputy_contact_person,
                "status": status_labels.get(contract.status, contract.status),
                "is_archived": bool(contract.archived_at),
                "department": contract.department.name,
            }
            row = [values[field] for field, _label in EXPORT_COLUMNS]
            export_bytes += sum(len(str(value).encode('utf-8')) for value in row if value is not None)
            if export_bytes>8*1024*1024 or monotonic()-export_started>10:
                raise HTTPException(413,'Export byte/time budget exceeded; narrow the filters')
            rows.append(row)
        content = make_xlsx([label for _field, label in EXPORT_COLUMNS], rows)
        if len(content)>8*1024*1024 or monotonic()-export_started>15:
            raise HTTPException(413,'Export byte/time budget exceeded; narrow the filters')
        return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": 'attachment; filename="vertragsregister_export.xlsx"'})

    @app.get("/reports", response_class=HTMLResponse)
    def reports(request: Request, overdue_page: int = Query(1,ge=1,le=10000),
                upcoming_page: int = Query(1,ge=1,le=10000), db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        today = date.today()
        department_filter = ([Contract.department_id == user.department_id]
                             if user.role == "department" else [])
        population = contract_query(user).where(
            Contract.archived_at.is_(None), *department_filter
        )
        contract_ids = population.with_only_columns(Contract.id)
        # Only dated records can produce contract reminders. All inventory
        # amounts/counts below are database aggregates, not full ORM snapshots.
        departments = db.scalars(select(Department).where(
            *([Department.id == user.department_id] if user.role == "department" else [])
        ).order_by(Department.name)).all()
        department_by_id = {department.id: department for department in departments}
        contracts=read_reminder_contracts(db,population.order_by(Contract.designation,Contract.id),department_by_id)
        parents={contract.id:contract for contract in contracts}
        tasks=[]
        task_rows=db.execute(select(ContractTask.id.label('task_id'),ContractTask.contract_id,
            ContractTask.title,ContractTask.status,ContractTask.due_date,
            Contract.department_id,Contract.contract_number,Contract.designation)
            .select_from(ContractTask).join(Contract,Contract.id==ContractTask.contract_id).where(
            ContractTask.contract_id.in_(contract_ids),ContractTask.status!='done'
        ).order_by(ContractTask.due_date,ContractTask.id)).mappings()
        for row in task_rows:
            parent=parents.get(row['contract_id'])
            if parent is None:
                parent=SimpleNamespace(id=row['contract_id'],department_id=row['department_id'],
                    contract_number=row['contract_number'],designation=row['designation'],
                    department=department_by_id.get(row['department_id']))
                parents[parent.id]=parent
            tasks.append(SimpleNamespace(id=row['task_id'],title=row['title'],status=row['status'],
                due_date=row['due_date'],contract=parent))
        review_counts = db.execute(select(Contract.department_id,func.count(ContractReview.id))
            .join(ContractReview,ContractReview.contract_id==Contract.id).where(
            ContractReview.contract_id.in_(contract_ids),
            ContractReview.status.in_(("open", "in_review"))
        ).group_by(Contract.department_id)).all()
        by_department = {department.id: {
            "department": department, "contract_count": 0,
            "annual_expenses": Decimal("0"), "annual_income": Decimal("0"),
            "annual_unknown": Decimal("0"), "missing_annual": 0, "missing_contract_value": 0,
            "contract_value": Decimal("0"), "open_tasks": 0,
            "overdue_tasks": 0, "upcoming_tasks": 0, "open_reviews": 0,
            "overdue_deadlines": 0, "upcoming_deadlines": 0,
        } for department in departments}

        financial_groups = current_groups(db,user)
        for group in financial_groups:
            row = by_department.get(group['department_id'])
            if row is None:
                continue
            row['contract_count'] += group['record_count']
            field={'income':'annual_income','expense':'annual_expenses','unknown':'annual_unknown'}[group['direction']]
            row[field] += group['annual'] or Decimal('0')
            row['missing_annual'] += group['record_count']-group['known_count']
        known_contract_value=case((Contract.contract_value.between(0,Decimal('9999999999.99')),
                                   Contract.contract_value),else_=None)
        for department_id,total,known,count in db.execute(select(Contract.department_id,
                func.sum(known_contract_value),func.count(known_contract_value),func.count())
                .where(Contract.id.in_(contract_ids)).group_by(Contract.department_id)):
            row=by_department.get(department_id)
            if row:
                row['contract_value']=total or Decimal('0')
                row['missing_contract_value']=count-known

        overdue_deadlines, upcoming_deadlines = split_deadline_reminders(contracts, today)
        for reminder in overdue_deadlines:
            row = by_department.get(reminder["contract"].department_id)
            if row:
                row["overdue_deadlines"] += 1
        for reminder in upcoming_deadlines:
            row = by_department.get(reminder["contract"].department_id)
            if row:
                row["upcoming_deadlines"] += 1
        overdue_tasks, upcoming_tasks = [], []
        window_end = today + timedelta(days=REMINDER_WINDOW_DAYS)
        for task in tasks:
            contract = task.contract
            if not contract or task.status == "done":
                continue
            row = by_department.get(contract.department_id)
            if row:
                row["open_tasks"] += 1
            if task.due_date and task.due_date < today:
                overdue_tasks.append({"task": task, "contract": contract})
                if row:
                    row["overdue_tasks"] += 1
            elif task.due_date and task.due_date <= window_end:
                upcoming_tasks.append({"task": task, "contract": contract})
                if row:
                    row["upcoming_tasks"] += 1
        for department_id,count in review_counts:
            row = by_department.get(department_id)
            if row:
                row["open_reviews"] += count

        annual_expenses = sum((row["annual_expenses"] for row in by_department.values()), Decimal("0"))
        annual_income = sum((row["annual_income"] for row in by_department.values()), Decimal("0"))
        total_contract_value = sum((row["contract_value"] for row in by_department.values()), Decimal("0"))
        open_task_count = sum(row["open_tasks"] for row in by_department.values())
        open_review_count = sum(row["open_reviews"] for row in by_department.values())

        trend, trend_peak = inventory_trend(db, user, today)

        overdue_deadlines = [{**item, "kind": "Vertragsfrist", "title": item["contract"].designation}
                             for item in overdue_deadlines]
        upcoming_deadlines = [{**item, "kind": "Vertragsfrist", "title": item["contract"].designation}
                              for item in upcoming_deadlines]
        overdue_tasks = [{"task": item["task"], "contract": item["contract"],
                          "due_date": item["task"].due_date, "kind": "Aufgabe",
                          "title": item["task"].title} for item in overdue_tasks]
        upcoming_tasks = [{"task": item["task"], "contract": item["contract"],
                            "due_date": item["task"].due_date, "kind": "Aufgabe",
                            "title": item["task"].title} for item in upcoming_tasks]
        overdue_items = sorted(overdue_deadlines + overdue_tasks, key=lambda item: item["due_date"])
        upcoming_items = sorted(upcoming_deadlines + upcoming_tasks, key=lambda item: item["due_date"])
        def reminder_page(items,requested):
            total=len(items);pages=max(1,(total+99)//100);page=min(requested,pages)
            return items[(page-1)*100:page*100],total,page,pages
        overdue_items,overdue_total,overdue_page,overdue_pages=reminder_page(overdue_items,overdue_page)
        upcoming_items,upcoming_total,upcoming_page,upcoming_pages=reminder_page(upcoming_items,upcoming_page)
        return html(request, "reports.html", {**base_context(request, user, csrf),
                    "report_rows": list(by_department.values()),
                    "contract_count": sum(row['contract_count'] for row in by_department.values()), "annual_expenses": annual_expenses,
                    "annual_income": annual_income, "total_contract_value": total_contract_value,
                    "open_task_count": open_task_count, "open_review_count": open_review_count,
                    "overdue_items": overdue_items, "upcoming_items": upcoming_items,
                    "overdue_total":overdue_total,"upcoming_total":upcoming_total,
                    "overdue_page":overdue_page,"overdue_pages":overdue_pages,
                    "upcoming_page":upcoming_page,"upcoming_pages":upcoming_pages,
                    "trend": trend, "trend_peak": trend_peak, "financial_groups": financial_groups,
                    "unknown_direction_count": sum(g["record_count"] for g in financial_groups if g["direction"]=="unknown"),
                    "unknown_basis_count": sum(g["record_count"] for g in financial_groups if g["basis"]=="unknown"),
                    "missing_annual_count": sum(g["record_count"]-g["known_count"] for g in financial_groups),
                    "reminder_window_days": REMINDER_WINDOW_DAYS})

    @app.post("/contracts/import", response_class=HTMLResponse)
    def import_contracts(request: Request, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        check_write(user)
        form = parsed_form(request, max_files=1, max_fields=2)
        request.state.safe_values = form_values(form)
        require_csrf(request, db, str(form.get("csrf_token", "")))
        upload = form.get("file")
        if not isinstance(upload, UploadFile) or not upload.filename.lower().endswith(".xlsx"):
            raise HTTPException(status_code=400, detail="Bitte eine .xlsx-Datei auswählen.")
        data = upload.file.read(10 * 1024 * 1024 + 1)
        upload.file.close()
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Die Excel-Datei darf höchstens 10 MB groß sein.")
        try:
            rows = read_xlsx(data)
        except (ValueError, BadZipFile, OSError, RuntimeError) as exc:
            return html(request, "import_result.html", {**base_context(request, user, csrf),
                        "imported": 0, "errors": [str(exc) if isinstance(exc, ValueError) else "Die Excel-Datei ist beschädigt oder ungültig."],
                        "error_count": 1}, 422)
        # Refresh authority under the identity guard before mapping ownership,
        # tax capabilities or external identities from uploaded rows.
        lock_actor(db,user)
        check_write(user)
        departments = {item.name.casefold(): item for item in db.scalars(
            select(Department).where(Department.is_active.is_(True))).all()}
        tax_labels = {label.casefold(): code for code, label in TAX_REVIEW_STATUSES}
        status_labels = {label.casefold(): code for code, label in CONTRACT_STATUSES}
        direction_labels = {label.casefold(): code for code, label in FINANCIAL_DIRECTIONS}
        payment_labels = {label.casefold(): code for code, label in PAYMENT_INTERVALS}
        validated = []
        errors = []
        for row_number, row in rows:
            raw_row = dict(row)
            row = dict(row)
            try:
                row["relevant_date"] = excel_date(row.get("relevant_date", ""))
                row["end_date"] = excel_date(row.get("end_date", ""))
            except (ValueError, OverflowError) as exc:
                errors.append(f'Row {row_number}: {exc}')
                continue
            if row.get('contract_number'):
                errors.append(f'Row {row_number}: create-only import generates contract numbers. Remove Vertragsnummer; use external_reference for source identity.')
                continue
            for key in ("notice_period_months", "renewal_period_months"):
                raw = row.get(key, "")
                try:
                    number = Decimal(raw)
                    row[key] = str(int(number)) if number.is_finite() and 0 <= number <= 120 and number == number.to_integral_value() else raw
                except (InvalidOperation, ValueError):
                    pass
            yes_no = row.get("automatic_renewal", "").strip().casefold()
            if yes_no in ("ja", "yes", "true", "1"):
                row["automatic_renewal"] = "1"
            elif yes_no in ("", "nein", "no", "false", "0"):
                row["automatic_renewal"] = "0"
            else:
                errors.append(f"Zeile {row_number}: Automatische Verlängerung muss Ja oder Nein sein.")
                continue
            archived_value = row.get("is_archived", "").strip().casefold()
            if archived_value in ("ja", "yes", "true", "1"):
                is_archived = True
            elif archived_value in ("", "nein", "no", "false", "0"):
                is_archived = False
            else:
                errors.append(f"Zeile {row_number}: Archiviert muss Ja oder Nein sein.")
                continue
            for key, mapping in (("tax_review_status", tax_labels), ("status", status_labels),
                                 ("financial_direction", direction_labels), ("payment_interval", payment_labels)):
                raw = row.get(key, "").strip()
                if raw:
                    row[key] = mapping.get(raw.casefold(), raw)
            if user.role == "admin":
                department_name = row.get("department", "").strip()
                department_obj = departments.get(department_name.casefold())
                if not department_obj:
                    errors.append(f"Zeile {row_number}: Fachbereich „{department_name or 'leer'}“ fehlt oder ist nicht aktiv.")
                    continue
                row["department_id"] = str(department_obj.id)
            try:
                values = validate_data(row, user, db)
                if values["status"]=="active":
                    raise ValidationError("Imported active status has no verifiable approval; import as draft")
                tax_values(user,None,values)
            except ValidationError as exc:
                errors.append(f"Zeile {row_number}: {exc}")
                continue
            validated.append((row_number, values, is_archived, raw_row))
        existing_contracts = db.scalars(contract_query(user)).all()
        existing_keys = {(item.department_id, item.external_reference)
                         for item in existing_contracts if item.external_reference}
        def natural_key(values):
            return (values['department_id'], values['designation'].casefold(),
                    values['contract_type'].casefold(), values['contract_partner'].casefold(),values['relevant_date'])
        natural_keys = {natural_key({k:getattr(c,k) for k in ('department_id','designation','contract_type','contract_partner','relevant_date')})
                        for c in existing_contracts}
        ambiguous_rows = set()
        imported_keys = set()
        for row_number, values, _is_archived, _raw_row in validated:
            natural = natural_key(values)
            if natural in natural_keys:
                ambiguous_rows.add(row_number)
            natural_keys.add(natural)
            reference = values.get('external_reference')
            if reference:
                key = (values['department_id'], reference)
                if key in existing_keys or key in imported_keys:
                    errors.append(f'Row {row_number}: external reference already exists in this department or workbook.')
                imported_keys.add(key)
        if errors:
            return html(request, "import_result.html", {**base_context(request, user, csrf),
                        "imported": 0, "errors": errors[:50], "error_count": len(errors)}, 422)
        created = []
        try:
            for _row_number, values, is_archived, raw_row in validated:
                if values["tax_review_status"] == "completed":
                    values["tax_reviewed_by_id"] = user.id
                    values["tax_reviewed_at"] = now_utc()
                contract = Contract(**values, material_actor_id=user.id, created_by_id=user.id, updated_by_id=user.id,
                                    archived_at=None)
                db.add(contract)
                db.flush()
                if contract.tax_review_status == "completed":
                    contract.tax_reviewed_by = user
                contract.contract_number = f"VR-{contract.created_at.year}-{contract.id:04d}"
                if is_archived:
                    contract.archived_at=now_utc()
                db.add(Revision(contract_id=contract.id, actor_id=user.id, action="created",
                                before=None, after={**snapshot(contract), "source": "excel_import", "import_row": _row_number,
                                    "import_sha256": sha256(data).hexdigest(), "import_raw": raw_row,
                                    "ambiguous_description": _row_number in ambiguous_rows}))
                created.append(contract)
            db.commit()
        except Exception:
            db.rollback()
            raise
        return redirect(f"/?notice=imported&imported_count={len(created)}&ambiguous_rows={len(ambiguous_rows)}")

    @app.get("/", response_class=HTMLResponse)
    def contracts(request: Request, q: str = "", department: str = "",
                  focus: str = "",
                  contract_type: str = "", contact_person: str = "",
                  deputy_contact_person: str = "", status: str = "", tax_review_status: str = "",
                  page: int = Query(1, ge=1, le=1000000), page_size: int = Query(50, ge=1, le=100),
                  db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        filters, stmt = listing_spec(db, user, locals())
        q, department, focus = filters['q'], filters['department'], filters['focus']
        contract_type, contact_person = filters['contract_type'], filters['contact_person']
        deputy_contact_person, status = filters['deputy_contact_person'], filters['status']
        tax_review_status = filters['tax_review_status']
        focus_labels = {"active": "Laufende Verträge", "expiring": "Anstehende Vertragsfristen",
                        "review": "Entwürfe / in Bearbeitung",
                        "approval": "Verträge mit offenen Freigaben",
                        "ended": "Gekündigte und beendete Verträge"}
        focus = focus if focus in focus_labels else ""
        dashboard_stmt = contract_query(user).where(Contract.archived_at.is_(None))
        if user.role == "department":
            dashboard_stmt = dashboard_stmt.where(Contract.department_id == user.department_id)
        status_counts = dict(db.execute(dashboard_stmt.with_only_columns(
            Contract.status,func.count()).group_by(Contract.status)).all())
        # Undated contracts cannot produce a reminder. Do not materialize the
        # whole inventory just to count statuses or paginate fifty list rows.
        dashboard_contracts = read_reminder_contracts(db,dashboard_stmt.order_by(Contract.end_date,Contract.id))
        overdue_reminders, upcoming_reminders = split_deadline_reminders(dashboard_contracts, date.today())
        total_count = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
        page_count = max(1, (total_count + page_size - 1) // page_size)
        page = min(page, page_count)
        items = db.scalars(stmt.options(joinedload(Contract.department))
            .limit(page_size).offset((page - 1) * page_size)).all()
        def page_url(number):
            return '/?' + urlencode({**filters, 'page':number, 'page_size':page_size})
        focus_counts = {
            "active": status_counts.get('active',0),
            "expiring": len(upcoming_reminders),
            "review": status_counts.get('draft',0)+status_counts.get('in_progress',0),
            "approval": db.scalar(select(func.count(func.distinct(ContractReview.contract_id))).join(Contract).where(
                Contract.archived_at.is_(None), ContractReview.status.in_(("open", "in_review")), contract_scope(user),
                *([Contract.department_id == user.department_id] if user.role == "department" else []))),
            "ended": status_counts.get('terminated',0)+status_counts.get('ended',0),
        }
        departments = db.scalars(select(Department).order_by(Department.name)).all() if user.role != "department" else []
        metadata_scope = [contract_scope(user)]
        stored_types = set(db.scalars(select(Contract.contract_type).where(*metadata_scope).distinct()).all())
        stored_people = (set(db.scalars(select(Contract.contact_person).where(*metadata_scope).distinct()).all()) |
                         set(db.scalars(select(Contract.deputy_contact_person).where(*metadata_scope).distinct()).all())) - {""}
        contract_types = list(CONTRACT_TYPES) + sorted(stored_types - set(CONTRACT_TYPES))
        contact_persons = list(CONTACT_PERSONS) + sorted(stored_people - set(CONTACT_PERSONS))
        return html(request, "list.html", {**base_context(request, user, csrf),
                    "contracts": items, "total_count": total_count, "page":page, "page_size":page_size,
                    "page_count":page_count, "previous_page_url":page_url(page-1) if page>1 else None,
                    "next_page_url":page_url(page+1) if page<page_count else None,
                    "departments": departments, "q": q, "selected_department": department,
                    "contract_types": contract_types, "selected_contract_type": contract_type,
                    "contact_persons": contact_persons, "selected_contact_person": contact_person,
                    "selected_deputy_contact_person": deputy_contact_person,
                    "selected_status": status,
                    "selected_tax_review_status": tax_review_status,
                    "archived": status == "archived",
                    "focus": focus, "focus_label": focus_labels.get(focus, ""),
                    "focus_counts": focus_counts,
                    "overdue_reminder_total":len(overdue_reminders),
                    "upcoming_reminder_total":len(upcoming_reminders),
                    "overdue_reminders": overdue_reminders[:10],
                    "upcoming_reminders": upcoming_reminders[:10],
                    "reminder_window_days": REMINDER_WINDOW_DAYS,
                    "can_create": can_write(user)})

    @app.get("/contracts/new", response_class=HTMLResponse)
    def new_contract(request: Request, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        check_write(user)
        departments = db.scalars(select(Department).where(Department.is_active.is_(True)).order_by(Department.name)).all()
        return html(request, "form.html", {**base_context(request, user, csrf), "mode": "new",
                     "values": {}, "departments": departments})

    @app.post("/contracts/new")
    def save_new(request: Request, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        check_write(user)
        form = parsed_form(request, max_files=MAX_DOCUMENTS_PER_UPLOAD, max_fields=32)
        request.state.safe_values = form_values(form)
        require_csrf(request, db, str(form.get("csrf_token", "")))
        lock_actor(db,user)
        check_write(user)
        uploads = [item for item in form.getlist("documents")
                   if isinstance(item, UploadFile) and item.filename]
        departments = db.scalars(select(Department).where(Department.is_active.is_(True)).order_by(Department.name)).all()
        try:
            values = validate_data(form, user, db)
            if values["status"]=="active":
                raise ValidationError("Neue Verträge beginnen als Entwurf und benötigen eine unabhängige Freigabe")
            tax_values(user,None,values)
        except ValidationError as exc:
            for upload in uploads:
                upload.file.close()
            return html(request, "form.html", {**base_context(request, user, csrf), "mode": "new",
                        "values": form_values(form), "departments": departments, "error": str(exc)}, 422)
        except HTTPException:
            for upload in uploads:
                upload.file.close()
            raise
        stored_documents = []
        pending_ids = []
        try:
            for upload in uploads:
                stored_documents.append(store_uploaded_document(upload, request.app.state.document_storage_dir, request.app.state.config))
            if values["tax_review_status"] == "completed":
                values["tax_reviewed_by_id"] = user.id
                values["tax_reviewed_at"] = now_utc()
            contract = Contract(**values, material_actor_id=user.id, created_by_id=user.id, updated_by_id=user.id)
            db.add(contract)
            db.flush()
            if contract.tax_review_status == "completed":
                contract.tax_reviewed_by = user
            contract.contract_number = f"VR-{contract.created_at.year}-{contract.id:04d}"
            db.add(Revision(contract_id=contract.id, actor_id=user.id, action="created",
                            before=None, after=snapshot(contract)))
            for stored in stored_documents:
                document = new_document(db,contract,user,stored)
                pending_ids.append(document.id)
                db.add(document)
                db.flush()
                db.add(Revision(contract_id=contract.id, actor_id=user.id, action="document_uploaded",
                                before=None, after={"document_id": document.id,
                                                    "filename": stored["filename"],
                                                    "size_bytes": stored["size_bytes"],
                                                    "uploaded_at": document.uploaded_at.isoformat()}))
            db.commit()
            for pending_id in (() if request.app.state.config.queued_document_scans else pending_ids):
                try:
                    process_document(db,request.app.state.config,request.app.state.document_scanner,pending_id,user=user)
                except Exception:
                    # Committed jobs survive failed finalization/archive races.
                    db.rollback()

        except HTTPException as exc:
            db.rollback()
            return html(request, "form.html", {**base_context(request, user, csrf), "mode": "new",
                        "values": form_values(form), "departments": departments,
                        "error": str(exc.detail)}, exc.status_code)
        except Exception:
            db.rollback()
            raise
        finally:
            for upload in uploads:
                upload.file.close()
        return redirect(f"/contracts/{contract.id}?notice=created")

    @app.get("/contracts/{contract_id}", response_class=HTMLResponse)
    def detail(request: Request, contract_id: int, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        contract = load_contract(db, user, contract_id)
        check_read(user, contract)
        revisions = db.scalars(select(Revision).where(Revision.contract_id == contract_id)
                               .order_by(Revision.id.desc())).all()
        department_names = {item.id: item.name for item in db.scalars(select(Department)).all()}
        history = build_history(revisions, department_names)
        tasks = db.scalars(select(ContractTask).where(ContractTask.contract_id == contract_id)
                           .order_by(ContractTask.created_at.desc(), ContractTask.id.desc())).all()
        contract_reviews = db.scalars(select(ContractReview).where(ContractReview.contract_id == contract_id)
                                      .order_by(ContractReview.created_at.desc(), ContractReview.id.desc())).all()
        task_order = {"open": 0, "in_progress": 1, "done": 2}
        tasks.sort(key=lambda task: (task_order.get(task.status, 9), task.due_date or date.max, task.id))
        task_assignees = [person for person in db.scalars(select(User).where(
            User.is_active.is_(True), User.role.in_(("admin", "department"))).order_by(User.username)).all()
                          if person.role == "admin" or person.department_id == contract.department_id]
        documents = db.scalars(select(ContractDocument).where(ContractDocument.contract_id == contract_id)
                               .order_by(ContractDocument.uploaded_at.desc(), ContractDocument.id.desc())).all()
        return html(request, "detail.html", {**base_context(request, user, csrf),
                    "contract": contract, "history": history, "request_id":str(uuid4()),
                    "documents": documents, "dms_links":{d.id:safe_external_url(request.app.state.config,d) for d in documents}, "tasks": tasks, "task_assignees": task_assignees,
                    "contract_reviews": contract_reviews,
                    "decision_history":db.scalars(select(ReviewDecision).where(ReviewDecision.contract_id==contract.id).order_by(ReviewDecision.id.desc())).all(),
                    "assignment_teams": db.scalars(select(RecipientTeam).where(RecipientTeam.is_active.is_(True))).all() if user.role == 'admin' else [],
                    "assignment_accounts": [account for account in db.scalars(select(User).where(User.can_approve.is_(True), User.is_active.is_(True))).all() if can_read(account, contract)] if user.role == 'admin' else [],
                    "task_kinds": TASK_KINDS, "task_statuses": TASK_STATUSES,
                    "task_kind_labels": TASK_KIND_LABELS, "task_status_labels": TASK_STATUS_LABELS,
                    "today": date.today(),
                    "status_label": dict(CONTRACT_STATUSES).get(contract.status, contract.status),
                    **contract_dates(contract),
                    "can_edit": can_write(user, contract) and contract.archived_at is None,
                    "review_options": {review.id: review_options(user,contract,review,
                        can_decide_review(db,user,contract,review),CONTRACT_REVIEW_STATUSES) for review in contract_reviews}})

    @app.post("/contracts/{contract_id}/tasks")
    def create_contract_task(request: Request, contract_id: int, db: Session = Depends(get_db)):
        form = parsed_form(request, max_files=MAX_DOCUMENTS_PER_UPLOAD, max_fields=32)
        request.state.safe_values = form_values(form)
        user, _csrf = user_csrf(request, db)
        contract = begin_mutation(db, user, contract_id)
        check_read(user, contract)
        check_write(user, contract)
        if contract.archived_at is not None:
            raise HTTPException(status_code=409, detail="Archivierter Vertrag ist schreibgeschützt")
        require_csrf(request, db, str(form.get("csrf_token", "")))
        submission(db,user,contract,form)
        try:
            values = validate_task_fields(form, db, contract, creating=True)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        task = ContractTask(contract_id=contract.id, created_by_id=user.id,
                            created_at=now_utc(), updated_at=now_utc(), **values)
        db.add(task)
        db.flush()
        db.add(Revision(contract_id=contract.id, actor_id=user.id, action="task_created",
                        before=None, after=task_snapshot(task)))
        db.commit()
        return redirect(f"/contracts/{contract.id}?notice=task_created")

    @app.post("/contracts/{contract_id}/tasks/{task_id}")
    def update_contract_task(request: Request, contract_id: int, task_id: int,
                                   db: Session = Depends(get_db)):
        form = parsed_form(request, max_files=MAX_DOCUMENTS_PER_UPLOAD, max_fields=32)
        request.state.safe_values = form_values(form)
        user, _csrf = user_csrf(request, db)
        contract = begin_mutation(db, user, contract_id)
        check_read(user, contract)
        check_write(user, contract)
        if contract.archived_at is not None:
            raise HTTPException(status_code=409, detail="Archivierter Vertrag ist schreibgeschützt")
        _parent, task = load_child(db, user, contract_id, ContractTask, task_id)
        if not task or task.contract_id != contract.id:
            raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden")
        require_csrf(request, db, str(form.get("csrf_token", "")))
        try:
            values = validate_task_fields(form, db, contract)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        expected_version(task, form)
        before = task_snapshot(task)
        task.version += 1
        for key, value in values.items():
            setattr(task, key, value)
        task.updated_at = now_utc()
        db.flush()
        db.add(Revision(contract_id=contract.id, actor_id=user.id, action="task_updated",
                        before=before, after=task_snapshot(task)))
        db.commit()
        return redirect(f"/contracts/{contract.id}?notice=task_updated")

    @app.post("/contracts/{contract_id}/reviews")
    def create_contract_review(request: Request, contract_id: int, db: Session = Depends(get_db)):
        form = parsed_form(request, max_files=MAX_DOCUMENTS_PER_UPLOAD, max_fields=32)
        request.state.safe_values = form_values(form)
        user, _csrf = user_csrf(request, db)
        contract = begin_mutation(db, user, contract_id)
        check_read(user, contract)
        check_write(user, contract)
        if contract.archived_at is not None:
            raise HTTPException(status_code=409, detail="Archivierter Vertrag ist schreibgeschützt")
        require_csrf(request, db, str(form.get("csrf_token", "")))
        submission(db,user,contract,form)
        recipient = str(form.get("recipient", "")).strip()
        recipient_detail = str(form.get("recipient_detail", "")).strip()
        subject = str(form.get("subject", "")).strip()
        request_text = str(form.get("request_text", "")).strip()
        due_date_text = str(form.get("due_date", "")).strip()
        if recipient not in REVIEW_RECIPIENTS:
            raise HTTPException(status_code=400, detail="Bitte eine gültige Prüfstelle auswählen")
        if not subject or len(subject) > 200 or len(recipient_detail) > 160 or len(request_text) > 3000:
            raise HTTPException(status_code=400, detail="Bitte Betreff und gültige Angaben zur Prüfanfrage eintragen")
        try:
            due_date = date.fromisoformat(due_date_text) if due_date_text else None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Bitte eine gültige Prüffrist angeben") from exc
        review = ContractReview(contract_id=contract.id, recipient=recipient,
                                recipient_detail=recipient_detail, subject=subject,
                                request_text=request_text, status="open", due_date=due_date, content_revision=contract.content_revision,
                                created_by_id=user.id, updated_at=now_utc())
        db.add(review)
        db.flush()
        db.add(Revision(contract_id=contract.id, actor_id=user.id, action="review_created",
                        before=None, after=review_snapshot(review)))
        db.commit()
        return redirect(f"/contracts/{contract.id}?notice=review_created")

    @app.post("/contracts/{contract_id}/reviews/{review_id}")
    def update_contract_review(request: Request, contract_id: int, review_id: int,
                                     db: Session = Depends(get_db)):
        form = parsed_form(request, max_files=MAX_DOCUMENTS_PER_UPLOAD, max_fields=32)
        request.state.safe_values = form_values(form)
        # Consume bounded form input before taking shared identity/parent locks.
        lock_identities(db)
        user, _csrf = user_csrf(request, db)
        require_csrf(request, db, str(form.get("csrf_token", "")))
        # Serialize review changes with contract archival on PostgreSQL.
        contract = begin_mutation(db, user, contract_id, writer=False)
        if contract is None:
            raise HTTPException(status_code=404, detail="Vertrag nicht gefunden")
        check_read(user, contract)
        if contract.archived_at is not None:
            raise HTTPException(status_code=409, detail="Archivierter Vertrag ist schreibgeschützt")
        _parent, review = load_child(db, user, contract_id, ContractReview, review_id, lock=True)
        if not review or review.contract_id != contract.id:
            raise HTTPException(status_code=404, detail="Prüfvorgang nicht gefunden")
        if not can_decide_review(db, user, contract, review):
            raise HTTPException(status_code=403, detail="Explizite Freigabeberechtigung und Zuweisung erforderlich")
        status = str(form.get("status", "")).strip()
        result_text = str(form.get("result_text", "")).strip()
        if status not in CONTRACT_REVIEW_STATUS_LABELS:
            raise HTTPException(status_code=400, detail="Bitte einen gültigen Prüfstatus auswählen")
        if len(result_text) > 5000:
            raise HTTPException(status_code=400, detail="Die Rückmeldung darf höchstens 5.000 Zeichen enthalten")
        if status in ("approved", "changes_requested", "rejected") and not result_text:
            raise HTTPException(status_code=400, detail="Für diese Entscheidung ist eine begründete Rückmeldung erforderlich")
        expected_version(review,form)
        before = review_snapshot(review)
        decide(db,user,contract,review,status,result_text)
        review.updated_by_id = user.id
        review.updated_at = now_utc()
        db.flush()
        db.add(Revision(contract_id=contract.id, actor_id=user.id, action="review_updated",
                        before=before, after=review_snapshot(review)))
        audit(db, user.id, 'review_decided', f'review:{review.id}', status=status,
              team_id=review.team_id, assigned_user_id=review.assigned_user_id)
        db.commit()
        return redirect(f"/contracts/{contract.id}?notice=review_updated")

    @app.post("/contracts/{contract_id}/documents")
    def upload_document(request: Request, contract_id: int, db: Session = Depends(get_db)):
        form = parsed_form(request, max_files=MAX_DOCUMENTS_PER_UPLOAD, max_fields=32)
        request.state.safe_values = form_values(form)
        user, _csrf = user_csrf(request, db)
        contract = begin_mutation(db, user, contract_id)
        check_read(user, contract)
        check_write(user, contract)
        if contract.archived_at is not None:
            raise HTTPException(status_code=409, detail="Archivierter Vertrag ist schreibgesch?tzt")
        require_csrf(request, db, str(form.get("csrf_token", "")))
        submission(db,user,contract,form)
        uploads = [item for item in form.getlist("documents")
                   if isinstance(item, UploadFile) and item.filename]
        if not uploads:
            raise HTTPException(status_code=400, detail="Bitte mindestens eine Datei ausw?hlen")
        material_change(db,contract,user)
        stored_documents = []
        pending_ids = []
        try:
            for upload in uploads:
                stored_documents.append(store_uploaded_document(upload, request.app.state.document_storage_dir, request.app.state.config))
            for stored in stored_documents:
                document = new_document(db,contract,user,stored)
                pending_ids.append(document.id)
                db.add(document)
                db.flush()
                db.add(Revision(contract_id=contract.id, actor_id=user.id, action="document_uploaded",
                                before=None, after={"document_id": document.id,
                                                    "filename": stored["filename"],
                                                    "size_bytes": stored["size_bytes"],
                                                    "uploaded_at": document.uploaded_at.isoformat()}))
            db.commit()
            for pending_id in (() if request.app.state.config.queued_document_scans else pending_ids):
                try:
                    process_document(db,request.app.state.config,request.app.state.document_scanner,pending_id,user=user)
                except Exception:
                    # Committed jobs survive failed finalization/archive races.
                    db.rollback()

        except Exception:
            db.rollback()
            raise
        finally:
            for upload in uploads:
                upload.file.close()
        return redirect(f"/contracts/{contract_id}?notice=document_uploaded")

    @app.post("/contracts/{contract_id}/documents/link")
    def link_external_document(request: Request, contract_id: int, db: Session = Depends(get_db)):
        form = parsed_form(request, max_files=MAX_DOCUMENTS_PER_UPLOAD, max_fields=32)
        request.state.safe_values = form_values(form)
        user, _csrf = user_csrf(request, db)
        contract = begin_mutation(db, user, contract_id)
        check_read(user, contract)
        check_write(user, contract)
        if contract.archived_at is not None:
            raise HTTPException(status_code=409, detail="Archivierter Vertrag ist schreibgesch?tzt")
        require_csrf(request, db, str(form.get("csrf_token", "")))
        submission(db,user,contract,form)
        label = str(form.get("document_name", "")).strip()
        if not label or len(label) > 200:
            raise HTTPException(status_code=400, detail="Bitte eine Bezeichnung mit h?chstens 200 Zeichen angeben")
        external_url = approved_external_url(request.app.state.config,str(form.get("external_url", "")))
        material_change(db,contract,user)
        document = ContractDocument(contract_id=contract.id, uploaded_by_id=user.id,
                                    original_filename=label, storage_key=None,
                                    content_type="application/x-dms-link", external_url=external_url, state="link",provenance="external_link",scan_result="not_applicable",
                                    size_bytes=0)
        db.add(document)
        db.flush()
        db.add(Revision(contract_id=contract.id, actor_id=user.id, action="document_uploaded",
                        before=None, after={"document_id": document.id, "filename": label,
                                            "source": "external_document_system",
                                            "uploaded_at": document.uploaded_at.isoformat()}))
        db.commit()
        return redirect(f"/contracts/{contract_id}?notice=document_uploaded")

    @app.get("/contracts/{contract_id}/documents/{document_id}")
    def get_document(request: Request, contract_id: int, document_id: int,
                     download: bool = False, db: Session = Depends(get_db)):
        user, _csrf = user_csrf(request, db)
        try:
            contract = load_contract(db, user, contract_id)
            check_read(user, contract)
            _parent, document = load_child(db, user, contract_id, ContractDocument, document_id)
        except HTTPException:
            audit_denied(db,document_id,actor=user)
            raise
        return download_response(db,request.app.state.config,document,request,actor=user)

    @app.get("/contracts/{contract_id}/edit", response_class=HTMLResponse)
    def edit(request: Request, contract_id: int, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        contract = load_contract(db, user, contract_id)
        check_read(user, contract)
        check_write(user, contract)
        if contract.archived_at is not None:
            raise HTTPException(status_code=409, detail="Archivierter Vertrag ist schreibgeschützt")
        departments = db.scalars(select(Department).where(Department.is_active.is_(True)).order_by(Department.name)).all()
        values = snapshot(contract)
        return html(request, "form.html", {**base_context(request, user, csrf), "mode": "edit",
                    "contract": contract, "values": values, "departments": departments})

    @app.post("/contracts/{contract_id}/edit")
    def save_edit(request: Request, contract_id: int, db: Session = Depends(get_db)):
        form = parsed_form(request, max_files=0, max_fields=32)
        request.state.safe_values = form_values(form)
        user, csrf = user_csrf(request, db)
        contract = begin_mutation(db, user, contract_id)
        check_read(user, contract)
        check_write(user, contract)
        require_csrf(request, db, str(form.get("csrf_token", "")))
        if contract.archived_at is not None:
            raise HTTPException(status_code=409, detail="Archivierter Vertrag ist schreibgeschützt")
        departments = db.scalars(select(Department).where(Department.is_active.is_(True)).order_by(Department.name)).all()
        try:
            values = validate_data(form, user, db, existing=contract)
        except ValidationError as exc:
            return html(request, "form.html", {**base_context(request, user, csrf), "mode": "edit",
                        "contract": contract, "values": form_values(form),
                        "departments": departments, "error": str(exc)}, 422)
        expected_version(contract,form)
        before = snapshot(contract)
        changed=any(getattr(contract,k)!=values[k] for k in MATERIAL_FIELDS)
        if changed:
            material_change(db,contract,user,bump_version=False)
            if values['status']=='active':
                values['status']='in_progress'
            # A material edit reopens a completed assessment; require a later
            # explicit completion against the new saved content.
            if values['tax_review_status']=='completed':
                values['tax_review_status']='in_progress'
        tax_values(user,contract,values)
        for key,value in values.items():
            setattr(contract,key,value)
        if values['status']=='active' and not (before['status']=='active' and not changed and contract.approval_provenance=='legacy_unverified'):
            activation(db,contract,request.app.state.config.mandatory_review_recipients)
        contract.updated_by_id=user.id
        contract.updated_at=now_utc()
        contract.version+=1
        db.flush()
        db.expire(contract,['tax_reviewed_by'])
        db.add(Revision(contract_id=contract.id, actor_id=user.id, action="updated",
                        before=before, after=snapshot(contract)))
        db.commit()
        return redirect(f"/contracts/{contract_id}?notice=updated")

    @app.post("/contracts/{contract_id}/archive")
    def archive(request: Request, contract_id: int, db: Session = Depends(get_db)):
        user = require_user(request, db)
        form = parsed_form(request, max_files=0,max_fields=5)
        request.state.safe_values = form_values(form)
        contract = begin_mutation(db, user, contract_id)
        check_read(user, contract)
        check_write(user, contract)
        require_csrf(request, db, str(form.get("csrf_token", "")))
        expected_version(contract,form)
        before = snapshot(contract)
        contract.archived_at=now_utc()
        contract.updated_by_id=user.id
        contract.updated_at=now_utc()
        contract.version+=1
        db.flush()
        db.add(Revision(contract_id=contract.id, actor_id=user.id, action="archived",
                        before=before, after=snapshot(contract)))
        db.commit()
        return redirect(f"/contracts/{contract_id}?notice=archived")

    from app.document_routes import install_document_routes
    install_document_routes(app,get_db=get_db,user_csrf=user_csrf)
    from app.integration import install_integration_routes
    install_integration_routes(app,get_db=get_db,authenticate=require_integration_token)
    from app.token_service import install_token_routes,install_usage_recording
    install_token_routes(app,get_db=get_db,user_csrf=user_csrf,render=render_integrations)
    install_usage_recording(app)
    from app.identity_routes import install_identity_routes
    install_identity_routes(app, get_db=get_db, html=html, base_context=base_context,
                            user_csrf=user_csrf, check_admin=check_admin)
    from app.mfa_routes import install_mfa_routes
    install_mfa_routes(app,get_db=get_db,html=html)
    from app.request_boundary import RequestBoundary
    app.add_middleware(RequestBoundary, settings=settings)
    return app


app = create_app()
