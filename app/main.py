"""Server-rendered, department-scoped contract register (no external services)."""
from contextlib import asynccontextmanager
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
import secrets
from urllib.parse import quote
from urllib.parse import urlsplit
from uuid import uuid4
from zipfile import BadZipFile

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import Settings, get_settings
from app.db import make_engine, make_session_factory
from app.excel import EXPORT_COLUMNS, MAX_IMPORT_ROWS, excel_date, make_xlsx, read_xlsx
from app.logic import ValidationError, can_read, can_write, snapshot, validate_data
from app.models import (Contract, ContractDocument, ContractReview, ContractTask, Department,
                        IntegrationToken, LoginSession, Revision, User, now_utc)
from app.options import (CONTACT_PERSONS, CONTRACT_STATUSES, CONTRACT_TYPES, FINANCIAL_DIRECTIONS,
                         PAYMENT_INTERVALS, REVIEW_RECIPIENTS, CONTRACT_REVIEW_STATUSES,
                         TASK_KINDS, TASK_STATUSES, TAX_REVIEW_STATUSES)
from app.security import (COOKIE_NAME, attempt_key, clear_failures, cookie_response,
                          get_login_session, get_user, hash_value, new_session, record_failure,
                          ph, require_csrf, require_user, throttled, verify_password)

BASE = Path(__file__).resolve().parent
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
MAX_DOCUMENTS_PER_UPLOAD = 5
REMINDER_WINDOW_DAYS = 90
DOCUMENT_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".odp": "application/vnd.oasis.opendocument.presentation",
    ".rtf": "application/rtf",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
}
TEMPLATES = Jinja2Templates(directory=str(BASE / "templates"))
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
    ("reviewer", "Prüfer (nur Lesen)"),
    ("admin", "Administrator"),
)
ROLE_LABELS = dict(USER_ROLES)
TASK_KIND_LABELS = dict(TASK_KINDS)
TASK_STATUS_LABELS = dict(TASK_STATUSES)
TAX_REVIEW_LABELS = dict(TAX_REVIEW_STATUSES)
CONTRACT_REVIEW_STATUS_LABELS = dict(CONTRACT_REVIEW_STATUSES)


def get_db(request: Request):
    with request.app.state.session_factory() as db:
        yield db


def html(request: Request, template: str, context: dict, status_code: int = 200):
    notice = SUCCESS_NOTICES.get(request.query_params.get("notice", ""))
    if notice:
        if request.query_params.get("notice") == "imported" and request.query_params.get("imported_count", "").isdigit():
            notice += f" {request.query_params.get('imported_count')} Verträge wurden übernommen."
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
    if scheme.casefold() != "bearer" or not credential.startswith("ohvr_") or len(credential) > 128:
        raise HTTPException(status_code=401, detail="Bearer-Token erforderlich",
                            headers={"WWW-Authenticate": "Bearer"})
    token = db.scalar(select(IntegrationToken).where(
        IntegrationToken.token_prefix == credential[:16]))
    if (not token or not token.is_active or
            not secrets.compare_digest(token.token_hash, hash_value(credential))):
        raise HTTPException(status_code=401, detail="Ungültiger Integrationstoken",
                            headers={"WWW-Authenticate": "Bearer"})
    if token.expires_at and token.expires_at <= now_utc():
        raise HTTPException(status_code=401, detail="Integrationstoken abgelaufen",
                            headers={"WWW-Authenticate": "Bearer"})
    token.last_used_at = now_utc()
    db.commit()
    return token


def redirect(target: str):
    return RedirectResponse(target, status_code=303)


def fetch_contract(db: Session, contract_id: int) -> Contract:
    contract = db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden")
    return contract


def check_read(user: User, contract: Contract):
    if not can_read(user, contract):
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden")


def check_write(user: User, contract: Contract | None = None):
    if not can_write(user, contract):
        raise HTTPException(status_code=403, detail="Keine Schreibberechtigung")


def check_admin(user: User):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Nur Administratoren dürfen Benutzer verwalten")


def validate_user_fields(form, db: Session, existing: User | None = None) -> dict:
    username = str(form.get("username", "")).strip().casefold()
    if not username or len(username) > 80 or not username.replace("_", "a").replace("-", "a").replace(".", "a").isalnum():
        raise ValueError("Benutzername: 1–80 Zeichen, nur Buchstaben, Zahlen, Punkt, Bindestrich oder Unterstrich")
    duplicate = db.scalar(select(User).where(User.username == username))
    if duplicate and (existing is None or duplicate.id != existing.id):
        raise ValueError("Dieser Benutzername ist bereits vergeben")
    role = str(form.get("role", "")).strip()
    if role not in ROLE_LABELS:
        raise ValueError("Bitte eine gültige Rolle auswählen")
    raw_department_id = str(form.get("department_id", "")).strip()
    department_id = None
    if raw_department_id:
        try:
            department_id = int(raw_department_id)
        except ValueError as exc:
            raise ValueError("Bitte einen gültigen Fachbereich auswählen") from exc
        department = db.scalar(select(Department).where(
            Department.id == department_id, Department.is_active.is_(True)))
        if not department:
            raise ValueError("Der ausgewählte Fachbereich ist nicht verfügbar")
    elif role == "department":
        raise ValueError("Für Fachbereichsnutzer muss ein Fachbereich ausgewählt werden")
    password = str(form.get("password", ""))
    if existing is None and not password:
        raise ValueError("Für neue Benutzer ist ein Startpasswort erforderlich")
    if password and not 12 <= len(password) <= 256:
        raise ValueError("Passwörter müssen 12 bis 256 Zeichen lang sein")
    return {"username": username, "role": role, "department_id": department_id,
            "is_active": str(form.get("is_active", "")) == "1", "password": password}


def form_values(request_form):
    return {k: str(v) for k, v in request_form.items() if isinstance(v, str)}


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
    return {"task_id": task.id, "task_title": task.title, "task_kind": task.kind,
            "task_status": task.status, "task_description": task.description,
            "task_due_date": task.due_date.isoformat() if task.due_date else "",
            "assigned_to": task.assigned_user.username if task.assigned_user else ""}


def review_snapshot(review: ContractReview) -> dict:
    return {"review_id": review.id, "recipient": review.recipient,
            "recipient_detail": review.recipient_detail, "subject": review.subject,
            "request_text": review.request_text, "status": review.status,
            "result_text": review.result_text,
            "due_date": review.due_date.isoformat() if review.due_date else ""}


def calculate_notice_deadline(end_date: date | None, months: int | None) -> date | None:
    if end_date is None or months is None:
        return None
    month_index = end_date.year * 12 + end_date.month - 1 - months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    return date(year, month, min(end_date.day, monthrange(year, month)[1]))


def add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def calculate_next_end_date(end_date: date | None, renewal_period_months: int | None,
                            today: date | None = None) -> date | None:
    if end_date is None or renewal_period_months is None:
        return end_date
    today = today or date.today()
    elapsed_months = max(0, (today.year - end_date.year) * 12 + today.month - end_date.month)
    periods = elapsed_months // renewal_period_months
    next_end = add_months(end_date, periods * renewal_period_months)
    if next_end < today:
        next_end = add_months(end_date, (periods + 1) * renewal_period_months)
    return next_end


def contract_reminder(contract: Contract, today: date) -> dict | None:
    if contract.status in ("draft", "ended") or contract.end_date is None:
        return None
    if contract.automatic_renewal and contract.status != "terminated":
        effective_end = calculate_next_end_date(
            contract.end_date, contract.renewal_period_months, today)
    else:
        effective_end = contract.end_date
    if effective_end is None:
        return None
    if contract.status != "terminated" and contract.notice_period_months is not None:
        due_date = calculate_notice_deadline(effective_end, contract.notice_period_months)
        label = "Kündigung spätestens"
    else:
        due_date = effective_end
        label = ("Nächster Verlängerungstermin"
                 if contract.automatic_renewal and contract.status != "terminated" else "Vertragsende")
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


def format_euro(amount) -> str:
    raw = f"{amount:,.2f}"
    whole, cents = raw.rsplit(".", 1)
    whole = whole.replace(",", ".")
    return f"{whole}{',' + cents if cents != '00' else ''} €"


async def store_uploaded_document(upload: UploadFile, storage_dir: Path) -> dict:
    filename = Path(upload.filename or "").name.strip()
    suffix = Path(filename).suffix.lower()
    if not filename or len(filename) > 200 or suffix not in DOCUMENT_TYPES:
        await upload.close()
        raise HTTPException(status_code=400, detail="Dateityp nicht unterstützt. Erlaubt sind PDF, Office-/OpenDocument-, RTF-, Text-, CSV- und Bilddateien.")
    key = f"{uuid4().hex}{suffix}"
    temp_path = storage_dir / f".{key}.upload"
    final_path = storage_dir / key
    size = 0
    prefix = b""
    contains_nul = False
    try:
        storage_dir.mkdir(parents=True, exist_ok=True)
        with temp_path.open("xb") as output:
            while chunk := await upload.read(64 * 1024):
                if len(prefix) < 16:
                    prefix += chunk[:16 - len(prefix)]
                contains_nul = contains_nul or b"\x00" in chunk
                size += len(chunk)
                if size > MAX_DOCUMENT_BYTES:
                    raise HTTPException(status_code=413, detail="Dateien dürfen höchstens 25 MB groß sein")
                output.write(chunk)
        ext = suffix
        if ext == ".pdf":
            valid = prefix.startswith(b"%PDF-")
        elif ext in (".doc", ".xls", ".ppt"):
            valid = prefix.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
        elif ext in (".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp"):
            valid = prefix.startswith(b"PK\x03\x04")
        elif ext == ".rtf":
            valid = prefix.lstrip().startswith(b"{\\rtf")
        elif ext in (".txt", ".csv"):
            valid = not contains_nul
        elif ext == ".png":
            valid = prefix.startswith(b"\x89PNG\r\n\x1a\n")
        elif ext in (".jpg", ".jpeg"):
            valid = prefix.startswith(b"\xff\xd8\xff")
        elif ext == ".gif":
            valid = prefix.startswith((b"GIF87a", b"GIF89a"))
        else:
            valid = False
        if size == 0 or not valid:
            raise HTTPException(status_code=400, detail="Dateiinhalt und Dateiendung stimmen nicht überein")
        os.replace(temp_path, final_path)
        return {"filename": filename, "storage_key": key, "size_bytes": size,
                "content_type": DOCUMENT_TYPES[suffix], "path": final_path}
    except Exception:
        temp_path.unlink(missing_ok=True)
        final_path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def validate_external_document_url(value: str) -> str:
    url = value.strip()
    try:
        parsed = urlsplit(url)
        valid = (len(url) <= 2048 and parsed.scheme.lower() in ("http", "https")
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
            return datetime.fromisoformat(str(value)).strftime("%d.%m.%Y %H:%M")
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
        yield
        engine.dispose()

    app = FastAPI(title="OPEN.HERZ Vertragsregister", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    app.state.config = settings
    app.state.document_storage_dir = Path(settings.document_storage_dir).expanduser().resolve()
    app.state.session_factory = make_session_factory(engine)
    app.state.engine = engine
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))
    app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
            "form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
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
    async def login(request: Request, db: Session = Depends(get_db)):
        form = await request.form()
        guest = require_csrf(request, db, str(form.get("csrf_token", "")))
        username = str(form.get("username", "")).strip().casefold()
        password = str(form.get("password", ""))
        ip = request.client.host if request.client else "unknown"
        key = attempt_key(username, ip)
        if len(username) > 80 or len(password) > 512 or throttled(db, key):
            return html(request, "login.html", {"csrf_token": guest.csrf_token,
                         "error": "Anmeldung vorübergehend nicht möglich. Bitte später erneut versuchen."}, 429)
        user = db.scalar(select(User).where(User.username == username, User.is_active.is_(True)))
        if not verify_password(password, user):
            record_failure(db, key)
            return html(request, "login.html", {"csrf_token": guest.csrf_token,
                         "error": "Benutzername oder Passwort ungültig."}, 401)
        clear_failures(db, key)
        db.delete(guest)
        db.flush()
        new_login, token = new_session(db, settings.session_hours, user.id)
        db.commit()
        return cookie_response(redirect("/?notice=login"), token, production=settings.production, hours=settings.session_hours)

    @app.post("/logout")
    async def logout(request: Request, db: Session = Depends(get_db)):
        form = await request.form()
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
                    "new_token": new_token, "error": error, "now": now_utc(),
                    "notice": "Der API-Token wurde erstellt. Kopiere ihn aus dem grünen Feld." if new_token else ""}, status_code)

    @app.get("/admin/integrations", response_class=HTMLResponse)
    def integrations_page(request: Request, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        check_admin(user)
        return render_integrations(request, user, csrf, db)

    @app.post("/admin/integrations", response_class=HTMLResponse)
    async def create_integration(request: Request, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        check_admin(user)
        form = await request.form(max_fields=6)
        require_csrf(request, db, str(form.get("csrf_token", "")))
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
        raw_token = "ohvr_" + secrets.token_urlsafe(32)
        expires_at = (now_utc() + timedelta(days=int(expires_in))
                      if expires_in != "never" else None)
        db.add(IntegrationToken(name=name, token_prefix=raw_token[:16],
                                token_hash=hash_value(raw_token), department_id=department_id,
                                created_by_id=user.id, expires_at=expires_at))
        db.commit()
        return render_integrations(request, user, csrf, db, new_token=raw_token)

    @app.post("/admin/integrations/{token_id}/revoke")
    async def revoke_integration(request: Request, token_id: int, db: Session = Depends(get_db)):
        user, _csrf = user_csrf(request, db)
        check_admin(user)
        form = await request.form(max_fields=2)
        require_csrf(request, db, str(form.get("csrf_token", "")))
        token = db.get(IntegrationToken, token_id)
        if not token:
            raise HTTPException(status_code=404, detail="Integrationstoken nicht gefunden")
        token.is_active = False
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
        stmt = select(Contract)
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
            "annual_value": format(contract.annual_value, "f") if contract.annual_value is not None else None,
            "contract_value": format(contract.contract_value, "f") if contract.contract_value is not None else None,
            "financial_direction": contract.financial_direction,
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
                "external_url": document.external_url,
                "download_url": (f"{api_root}/api/v1/contracts/{contract.id}/documents/{document.id}"
                                 if document.storage_key else None),
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
        contract = db.get(Contract, contract_id)
        if not contract or (token.department_id is not None and contract.department_id != token.department_id):
            raise HTTPException(status_code=404, detail="Vertrag nicht gefunden")
        document = db.get(ContractDocument, document_id)
        if not document or document.contract_id != contract.id or not document.storage_key:
            raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
        path = request.app.state.document_storage_dir / document.storage_key
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Datei nicht gefunden")
        headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(document.original_filename, safe='')}"}
        return FileResponse(path, media_type=document.content_type, headers=headers)

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
        departments = db.scalars(select(Department).where(Department.is_active.is_(True))
                                 .order_by(Department.name)).all()
        return html(request, "user_form.html", {**base_context(request, user, csrf),
                    "mode": mode, "values": values, "target": target,
                    "departments": departments, "roles": USER_ROLES, "error": error}, status_code)

    @app.post("/admin/users/new", response_class=HTMLResponse)
    async def create_user(request: Request, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        check_admin(user)
        form = await request.form(max_fields=8)
        require_csrf(request, db, str(form.get("csrf_token", "")))
        try:
            values = validate_user_fields(form, db)
        except ValueError as exc:
            return render_user_form(request, user, csrf, db, "new", form_values(form),
                                    error=str(exc), status_code=422)
        new_user = User(username=values["username"], password_hash=ph.hash(values["password"]),
                        role=values["role"], department_id=values["department_id"],
                        is_active=values["is_active"])
        db.add(new_user)
        try:
            db.commit()
        except IntegrityError:
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
                  "department_id": target.department_id or "", "is_active": target.is_active}
        return render_user_form(request, user, csrf, db, "edit", values, target)

    @app.post("/admin/users/{user_id}/edit", response_class=HTMLResponse)
    async def update_user(request: Request, user_id: int, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        check_admin(user)
        target = db.get(User, user_id)
        if not target:
            raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
        form = await request.form(max_fields=8)
        require_csrf(request, db, str(form.get("csrf_token", "")))
        try:
            values = validate_user_fields(form, db, target)
            if target.id == user.id and (values["role"] != "admin" or not values["is_active"]):
                raise ValueError("Das eigene Administratorkonto kann hier nicht zurückgestuft oder gesperrt werden")
            removes_admin = target.role == "admin" and target.is_active and not (
                values["role"] == "admin" and values["is_active"])
            if removes_admin:
                active_admins = db.scalars(select(User).where(User.role == "admin",
                                                              User.is_active.is_(True))).all()
                if len(active_admins) <= 1:
                    raise ValueError("Der letzte aktive Administrator kann nicht gesperrt oder zurückgestuft werden")
        except ValueError as exc:
            return render_user_form(request, user, csrf, db, "edit", form_values(form), target,
                                    str(exc), 422)
        permissions_changed = (target.role != values["role"] or
                               target.department_id != values["department_id"] or
                               target.is_active != values["is_active"])
        password_changed = bool(values["password"])
        target.role = values["role"]
        target.department_id = values["department_id"]
        target.is_active = values["is_active"]
        if password_changed:
            target.password_hash = ph.hash(values["password"])
        if permissions_changed or password_changed:
            db.execute(delete(LoginSession).where(LoginSession.user_id == target.id))
        db.commit()
        if target.id == user.id and (permissions_changed or password_changed):
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
        q, contract_type = q.strip()[:100], contract_type.strip()[:120]
        contact_person, deputy_contact_person = contact_person.strip()[:160], deputy_contact_person.strip()[:160]
        valid_statuses = {code for code, _label in CONTRACT_STATUSES}
        status = status if status in valid_statuses | {"archived"} else ""
        tax_review_status = tax_review_status if tax_review_status in TAX_REVIEW_LABELS else ""
        stmt = select(Contract).order_by(Contract.updated_at.desc(), Contract.id.desc())
        if user.role == "department":
            stmt = stmt.where(Contract.department_id == user.department_id)
        stmt = stmt.where(Contract.archived_at.is_not(None) if status == "archived" else Contract.archived_at.is_(None))
        if q:
            search_filter = (Contract.designation.contains(q, autoescape=True) |
                             Contract.contract_number.contains(q, autoescape=True) |
                             Contract.contract_partner.contains(q, autoescape=True) |
                             Contract.contact_person.contains(q, autoescape=True) |
                             Contract.deputy_contact_person.contains(q, autoescape=True) |
                             Contract.contract_type.contains(q, autoescape=True) |
                             Contract.tax_review_result.contains(q, autoescape=True) |
                             Contract.department.has(Department.name.contains(q, autoescape=True)))
            matching_statuses = [code for code, label in CONTRACT_STATUSES
                                 if q.casefold() in code.casefold() or q.casefold() in label.casefold()]
            if matching_statuses:
                search_filter = search_filter | Contract.status.in_(matching_statuses)
            matching_tax_statuses = [code for code, label in TAX_REVIEW_STATUSES
                                     if q.casefold() in code.casefold() or q.casefold() in label.casefold()]
            if matching_tax_statuses:
                search_filter = search_filter | Contract.tax_review_status.in_(matching_tax_statuses)
            stmt = stmt.where(search_filter)
        if user.role != "department" and department.isdecimal():
            stmt = stmt.where(Contract.department_id == int(department))
        if contract_type:
            stmt = stmt.where(Contract.contract_type == contract_type)
        if contact_person:
            stmt = stmt.where(Contract.contact_person == contact_person)
        if deputy_contact_person:
            stmt = stmt.where(Contract.deputy_contact_person == deputy_contact_person)
        if status and status != "archived":
            stmt = stmt.where(Contract.status == status)
        if tax_review_status:
            stmt = stmt.where(Contract.tax_review_status == tax_review_status)
        if focus in ("active", "expiring", "review", "approval", "ended"):
            stmt = stmt.where(Contract.archived_at.is_(None))
            if focus == "active":
                stmt = stmt.where(Contract.status == "active")
            elif focus == "review":
                stmt = stmt.where(Contract.status.in_(("draft", "in_progress")))
            elif focus == "approval":
                stmt = stmt.where(Contract.id.in_(select(ContractReview.contract_id).where(
                    ContractReview.status.in_(("open", "in_review")))))
            elif focus == "ended":
                stmt = stmt.where(Contract.status.in_(("terminated", "ended")))
            else:
                dashboard_contracts = db.scalars(select(Contract).where(
                    Contract.archived_at.is_(None),
                    *([Contract.department_id == user.department_id] if user.role == "department" else []))).all()
                _, upcoming = split_deadline_reminders(dashboard_contracts, date.today())
                upcoming_ids = [item["contract"].id for item in upcoming]
                stmt = stmt.where(Contract.id.in_(upcoming_ids))
        contracts_to_export = db.scalars(stmt).all()
        payment_labels = dict(PAYMENT_INTERVALS)
        direction_labels = dict(FINANCIAL_DIRECTIONS)
        tax_labels = dict(TAX_REVIEW_STATUSES)
        status_labels = dict(CONTRACT_STATUSES)
        rows = []
        for contract in contracts_to_export:
            values = {
                "contract_number": contract.contract_number,
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
            rows.append([values[field] for field, _label in EXPORT_COLUMNS])
        content = make_xlsx([label for _field, label in EXPORT_COLUMNS], rows)
        return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": 'attachment; filename="vertragsregister_export.xlsx"'})

    @app.get("/reports", response_class=HTMLResponse)
    def reports(request: Request, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        today = date.today()
        department_filter = ([Contract.department_id == user.department_id]
                             if user.role == "department" else [])
        contracts = db.scalars(select(Contract).where(
            Contract.archived_at.is_(None), *department_filter
        ).order_by(Contract.designation)).all()
        contract_ids = [contract.id for contract in contracts]
        contract_by_id = {contract.id: contract for contract in contracts}
        departments = db.scalars(select(Department).where(
            *([Department.id == user.department_id] if user.role == "department" else [])
        ).order_by(Department.name)).all()
        department_by_id = {department.id: department for department in departments}

        tasks = (db.scalars(select(ContractTask).where(
            ContractTask.contract_id.in_(contract_ids)
        )).all() if contract_ids else [])
        reviews = (db.scalars(select(ContractReview).where(
            ContractReview.contract_id.in_(contract_ids),
            ContractReview.status.in_(("open", "in_review"))
        )).all() if contract_ids else [])
        by_department = {department.id: {
            "department": department, "contract_count": 0,
            "annual_expenses": Decimal("0"), "annual_income": Decimal("0"),
            "contract_value": Decimal("0"), "open_tasks": 0,
            "overdue_tasks": 0, "upcoming_tasks": 0, "open_reviews": 0,
            "overdue_deadlines": 0, "upcoming_deadlines": 0,
        } for department in departments}

        def amount(value):
            try:
                return Decimal(str(value or "0"))
            except (InvalidOperation, ValueError):
                return Decimal("0")

        for contract in contracts:
            row = by_department.get(contract.department_id)
            if row is None:
                continue
            row["contract_count"] += 1
            annual = amount(contract.annual_value)
            if contract.financial_direction == "income":
                row["annual_income"] += annual
            else:
                row["annual_expenses"] += annual
            row["contract_value"] += amount(contract.contract_value)

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
            contract = contract_by_id.get(task.contract_id)
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
        for review in reviews:
            row = by_department.get(contract_by_id[review.contract_id].department_id)
            if row:
                row["open_reviews"] += 1

        annual_expenses = sum((row["annual_expenses"] for row in by_department.values()), Decimal("0"))
        annual_income = sum((row["annual_income"] for row in by_department.values()), Decimal("0"))
        total_contract_value = sum((row["contract_value"] for row in by_department.values()), Decimal("0"))
        open_task_count = sum(row["open_tasks"] for row in by_department.values())
        open_review_count = sum(row["open_reviews"] for row in by_department.values())

        # Rebuild year-end annual expense/income totals from the recorded revisions.
        revisions = (db.scalars(select(Revision).where(
            Revision.contract_id.in_(contract_ids)
        ).order_by(Revision.created_at, Revision.id)).all() if contract_ids else [])
        events = []
        for revision in revisions:
            before, after = revision.before or {}, revision.after or {}
            if revision.action == "created":
                if not after.get("archived_at"):
                    events.append((revision.created_at, after.get("financial_direction") or "expense",
                                   amount(after.get("annual_value"))))
            elif revision.action == "archived":
                if not before.get("archived_at"):
                    events.append((revision.created_at, before.get("financial_direction") or "expense",
                                   -amount(before.get("annual_value"))))
            elif revision.action == "updated":
                before_active, after_active = not before.get("archived_at"), not after.get("archived_at")
                if before_active:
                    events.append((revision.created_at, before.get("financial_direction") or "expense",
                                   -amount(before.get("annual_value"))))
                if after_active:
                    events.append((revision.created_at, after.get("financial_direction") or "expense",
                                   amount(after.get("annual_value"))))
        events.sort(key=lambda event: event[0])
        trend = []
        running = {"expense": Decimal("0"), "income": Decimal("0")}
        event_index = 0
        for year in range(today.year - 4, today.year + 1):
            year_end = datetime(year, 12, 31, 23, 59, 59, 999999)
            while event_index < len(events) and events[event_index][0] <= year_end:
                _at, direction, delta = events[event_index]
                running["income" if direction == "income" else "expense"] += delta
                event_index += 1
            trend.append({"year": year, "expenses": max(running["expense"], Decimal("0")),
                          "income": max(running["income"], Decimal("0"))})
        trend_peak = max((max(item["expenses"], item["income"]) for item in trend), default=Decimal("0"))
        for item in trend:
            item["expense_width"] = int(item["expenses"] / trend_peak * 100) if trend_peak else 0
            item["income_width"] = int(item["income"] / trend_peak * 100) if trend_peak else 0

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
        return html(request, "reports.html", {**base_context(request, user, csrf),
                    "report_rows": list(by_department.values()),
                    "contract_count": len(contracts), "annual_expenses": annual_expenses,
                    "annual_income": annual_income, "total_contract_value": total_contract_value,
                    "open_task_count": open_task_count, "open_review_count": open_review_count,
                    "overdue_items": overdue_items, "upcoming_items": upcoming_items,
                    "trend": trend, "trend_peak": trend_peak,
                    "reminder_window_days": REMINDER_WINDOW_DAYS})

    @app.post("/contracts/import", response_class=HTMLResponse)
    async def import_contracts(request: Request, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        check_write(user)
        form = await request.form(max_files=1, max_fields=2)
        require_csrf(request, db, str(form.get("csrf_token", "")))
        upload = form.get("file")
        if not isinstance(upload, UploadFile) or not upload.filename.lower().endswith(".xlsx"):
            raise HTTPException(status_code=400, detail="Bitte eine .xlsx-Datei auswählen.")
        data = await upload.read(10 * 1024 * 1024 + 1)
        await upload.close()
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Die Excel-Datei darf höchstens 10 MB groß sein.")
        try:
            rows = read_xlsx(data)
        except (ValueError, BadZipFile, OSError, RuntimeError) as exc:
            return html(request, "import_result.html", {**base_context(request, user, csrf),
                        "imported": 0, "errors": [str(exc) if isinstance(exc, ValueError) else "Die Excel-Datei ist beschädigt oder ungültig."],
                        "error_count": 1}, 422)
        departments = {item.name.casefold(): item for item in db.scalars(
            select(Department).where(Department.is_active.is_(True))).all()}
        tax_labels = {label.casefold(): code for code, label in TAX_REVIEW_STATUSES}
        status_labels = {label.casefold(): code for code, label in CONTRACT_STATUSES}
        direction_labels = {label.casefold(): code for code, label in FINANCIAL_DIRECTIONS}
        payment_labels = {label.casefold(): code for code, label in PAYMENT_INTERVALS}
        validated = []
        errors = []
        for row_number, row in rows:
            row = dict(row)
            row["relevant_date"] = excel_date(row.get("relevant_date", ""))
            row["end_date"] = excel_date(row.get("end_date", ""))
            for key in ("notice_period_months", "renewal_period_months"):
                raw = row.get(key, "")
                try:
                    number = Decimal(raw)
                    row[key] = str(int(number)) if number.is_finite() and number == number.to_integral_value() else raw
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
            except ValidationError as exc:
                errors.append(f"Zeile {row_number}: {exc}")
                continue
            validated.append((row_number, values, is_archived))
        existing_keys = {
            (item.designation.casefold(), item.contract_type.casefold(), item.contract_partner.casefold(),
             item.relevant_date, item.department_id)
            for item in db.scalars(select(Contract)).all()
        }
        imported_keys = set()
        for row_number, values, _is_archived in validated:
            key = (values["designation"].casefold(), values["contract_type"].casefold(),
                   values["contract_partner"].casefold(), values["relevant_date"], values["department_id"])
            if key in existing_keys or key in imported_keys:
                errors.append(f"Zeile {row_number}: Dieser Vertrag scheint bereits vorhanden zu sein oder kommt mehrfach in der Datei vor.")
            imported_keys.add(key)
        if errors:
            return html(request, "import_result.html", {**base_context(request, user, csrf),
                        "imported": 0, "errors": errors[:50], "error_count": len(errors)}, 422)
        created = []
        try:
            for _row_number, values, is_archived in validated:
                if values["tax_review_status"] == "completed":
                    values["tax_reviewed_by_id"] = user.id
                    values["tax_reviewed_at"] = now_utc()
                contract = Contract(**values, created_by_id=user.id, updated_by_id=user.id,
                                    archived_at=now_utc() if is_archived else None)
                db.add(contract)
                db.flush()
                if contract.tax_review_status == "completed":
                    contract.tax_reviewed_by = user
                contract.contract_number = f"VR-{contract.created_at.year}-{contract.id:04d}"
                db.add(Revision(contract_id=contract.id, actor_id=user.id, action="created",
                                before=None, after={**snapshot(contract), "source": "excel_import"}))
                created.append(contract)
            db.commit()
        except Exception:
            db.rollback()
            raise
        return redirect(f"/?notice=imported&imported_count={len(created)}")

    @app.get("/", response_class=HTMLResponse)
    def contracts(request: Request, q: str = "", department: str = "",
                  focus: str = "",
                  contract_type: str = "", contact_person: str = "",
                  deputy_contact_person: str = "", status: str = "", tax_review_status: str = "",
                  db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        q = q.strip()[:100]
        contract_type = contract_type.strip()[:120]
        contact_person = contact_person.strip()[:160]
        deputy_contact_person = deputy_contact_person.strip()[:160]
        valid_statuses = {code for code, _label in CONTRACT_STATUSES}
        status = status if status in valid_statuses | {"archived"} else ""
        tax_review_status = tax_review_status if tax_review_status in TAX_REVIEW_LABELS else ""
        stmt = select(Contract).order_by(Contract.updated_at.desc(), Contract.id.desc())
        if user.role == "department":
            stmt = stmt.where(Contract.department_id == user.department_id)
        if status == "archived":
            stmt = stmt.where(Contract.archived_at.is_not(None))
        else:
            stmt = stmt.where(Contract.archived_at.is_(None))
        if q:
            search_filter = (Contract.designation.contains(q, autoescape=True) |
                             Contract.contract_number.contains(q, autoescape=True) |
                             Contract.contract_partner.contains(q, autoescape=True) |
                             Contract.contact_person.contains(q, autoescape=True) |
                             Contract.deputy_contact_person.contains(q, autoescape=True) |
                             Contract.contract_type.contains(q, autoescape=True) |
                             Contract.tax_review_result.contains(q, autoescape=True) |
                             Contract.department.has(Department.name.contains(q, autoescape=True)))
            matching_statuses = [code for code, label in CONTRACT_STATUSES
                                 if q.casefold() in code.casefold() or q.casefold() in label.casefold()]
            if matching_statuses:
                search_filter = search_filter | Contract.status.in_(matching_statuses)
            matching_tax_statuses = [code for code, label in TAX_REVIEW_STATUSES
                                     if q.casefold() in code.casefold() or q.casefold() in label.casefold()]
            if matching_tax_statuses:
                search_filter = search_filter | Contract.tax_review_status.in_(matching_tax_statuses)
            stmt = stmt.where(search_filter)
        if user.role != "department" and department.isdecimal():
            stmt = stmt.where(Contract.department_id == int(department))
        if contract_type:
            stmt = stmt.where(Contract.contract_type == contract_type)
        if contact_person:
            stmt = stmt.where(Contract.contact_person == contact_person)
        if deputy_contact_person:
            stmt = stmt.where(Contract.deputy_contact_person == deputy_contact_person)
        if status and status != "archived":
            stmt = stmt.where(Contract.status == status)
        if tax_review_status:
            stmt = stmt.where(Contract.tax_review_status == tax_review_status)
        focus_labels = {"active": "Laufende Verträge", "expiring": "Bald auslaufende Verträge",
                        "review": "Verträge mit offener Prüfung",
                        "approval": "Verträge mit offenen Freigaben",
                        "ended": "Gekündigte und beendete Verträge"}
        focus = focus if focus in focus_labels else ""
        dashboard_stmt = select(Contract).where(Contract.archived_at.is_(None))
        if user.role == "department":
            dashboard_stmt = dashboard_stmt.where(Contract.department_id == user.department_id)
        dashboard_contracts = db.scalars(dashboard_stmt.order_by(Contract.end_date, Contract.id)).all()
        overdue_reminders, upcoming_reminders = split_deadline_reminders(dashboard_contracts, date.today())
        upcoming_ids = [item["contract"].id for item in upcoming_reminders]
        if focus == "active":
            stmt = stmt.where(Contract.status == "active")
        elif focus == "expiring":
            stmt = stmt.where(Contract.id.in_(upcoming_ids))
        elif focus == "review":
            stmt = stmt.where(Contract.status.in_(("draft", "in_progress")))
        elif focus == "approval":
            stmt = stmt.where(Contract.id.in_(select(ContractReview.contract_id).where(
                ContractReview.status.in_(("open", "in_review")))))
        elif focus == "ended":
            stmt = stmt.where(Contract.status.in_(("terminated", "ended")))
        items = db.scalars(stmt.limit(501)).all()
        focus_counts = {
            "active": sum(contract.status == "active" for contract in dashboard_contracts),
            "expiring": len(upcoming_reminders),
            "review": sum(contract.status in ("draft", "in_progress") for contract in dashboard_contracts),
            "approval": len(db.scalars(select(ContractReview.id).join(Contract).where(
                Contract.archived_at.is_(None), ContractReview.status.in_(("open", "in_review")),
                *([Contract.department_id == user.department_id] if user.role == "department" else []))).all()),
            "ended": sum(contract.status in ("terminated", "ended") for contract in dashboard_contracts),
        }
        departments = db.scalars(select(Department).order_by(Department.name)).all() if user.role != "department" else []
        stored_types = set(db.scalars(select(Contract.contract_type).distinct()).all())
        stored_people = (set(db.scalars(select(Contract.contact_person).distinct()).all()) |
                         set(db.scalars(select(Contract.deputy_contact_person).distinct()).all())) - {""}
        contract_types = list(CONTRACT_TYPES) + sorted(stored_types - set(CONTRACT_TYPES))
        contact_persons = list(CONTACT_PERSONS) + sorted(stored_people - set(CONTACT_PERSONS))
        return html(request, "list.html", {**base_context(request, user, csrf),
                    "contracts": items[:500], "truncated": len(items) > 500,
                    "departments": departments, "q": q, "selected_department": department,
                    "contract_types": contract_types, "selected_contract_type": contract_type,
                    "contact_persons": contact_persons, "selected_contact_person": contact_person,
                    "selected_deputy_contact_person": deputy_contact_person,
                    "selected_status": status,
                    "selected_tax_review_status": tax_review_status,
                    "archived": status == "archived",
                    "focus": focus, "focus_label": focus_labels.get(focus, ""),
                    "focus_counts": focus_counts,
                    "overdue_reminders": overdue_reminders,
                    "upcoming_reminders": upcoming_reminders,
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
    async def save_new(request: Request, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        check_write(user)
        form = await request.form(max_files=MAX_DOCUMENTS_PER_UPLOAD, max_fields=32)
        require_csrf(request, db, str(form.get("csrf_token", "")))
        uploads = [item for item in form.getlist("documents")
                   if isinstance(item, UploadFile) and item.filename]
        departments = db.scalars(select(Department).where(Department.is_active.is_(True)).order_by(Department.name)).all()
        try:
            values = validate_data(form, user, db)
        except ValidationError as exc:
            for upload in uploads:
                await upload.close()
            return html(request, "form.html", {**base_context(request, user, csrf), "mode": "new",
                        "values": form_values(form), "departments": departments, "error": str(exc)}, 422)
        stored_documents = []
        try:
            for upload in uploads:
                stored_documents.append(await store_uploaded_document(upload, request.app.state.document_storage_dir))
            if values["tax_review_status"] == "completed":
                values["tax_reviewed_by_id"] = user.id
                values["tax_reviewed_at"] = now_utc()
            contract = Contract(**values, created_by_id=user.id, updated_by_id=user.id)
            db.add(contract)
            db.flush()
            if contract.tax_review_status == "completed":
                contract.tax_reviewed_by = user
            contract.contract_number = f"VR-{contract.created_at.year}-{contract.id:04d}"
            db.add(Revision(contract_id=contract.id, actor_id=user.id, action="created",
                            before=None, after=snapshot(contract)))
            for stored in stored_documents:
                document = ContractDocument(
                    contract_id=contract.id, uploaded_by_id=user.id,
                    original_filename=stored["filename"], storage_key=stored["storage_key"],
                    content_type=stored["content_type"], size_bytes=stored["size_bytes"])
                db.add(document)
                db.flush()
                db.add(Revision(contract_id=contract.id, actor_id=user.id, action="document_uploaded",
                                before=None, after={"document_id": document.id,
                                                    "filename": stored["filename"],
                                                    "size_bytes": stored["size_bytes"],
                                                    "uploaded_at": document.uploaded_at.isoformat()}))
            db.commit()
        except HTTPException as exc:
            db.rollback()
            for stored in stored_documents:
                stored["path"].unlink(missing_ok=True)
            return html(request, "form.html", {**base_context(request, user, csrf), "mode": "new",
                        "values": form_values(form), "departments": departments,
                        "error": str(exc.detail)}, exc.status_code)
        except Exception:
            db.rollback()
            for stored in stored_documents:
                stored["path"].unlink(missing_ok=True)
            raise
        finally:
            for upload in uploads:
                await upload.close()
        return redirect(f"/contracts/{contract.id}?notice=created")

    @app.get("/contracts/{contract_id}", response_class=HTMLResponse)
    def detail(request: Request, contract_id: int, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        contract = fetch_contract(db, contract_id)
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
                    "contract": contract, "history": history,
                    "documents": documents, "tasks": tasks, "task_assignees": task_assignees,
                    "contract_reviews": contract_reviews,
                    "task_kinds": TASK_KINDS, "task_statuses": TASK_STATUSES,
                    "task_kind_labels": TASK_KIND_LABELS, "task_status_labels": TASK_STATUS_LABELS,
                    "today": date.today(),
                    "status_label": dict(CONTRACT_STATUSES).get(contract.status, contract.status),
                    "next_end_date": calculate_next_end_date(
                        contract.end_date,
                        contract.renewal_period_months if contract.automatic_renewal else None),
                    "notice_deadline": calculate_notice_deadline(
                        calculate_next_end_date(contract.end_date, contract.renewal_period_months)
                        if contract.automatic_renewal else contract.end_date,
                        contract.notice_period_months),
                    "can_edit": can_write(user, contract) and contract.archived_at is None,
                    "can_handle_reviews": user.role in ("admin", "reviewer")})

    @app.post("/contracts/{contract_id}/tasks")
    async def create_contract_task(request: Request, contract_id: int, db: Session = Depends(get_db)):
        user, _csrf = user_csrf(request, db)
        contract = fetch_contract(db, contract_id)
        check_read(user, contract)
        check_write(user, contract)
        if contract.archived_at is not None:
            raise HTTPException(status_code=409, detail="Archivierter Vertrag ist schreibgeschützt")
        form = await request.form(max_fields=8)
        require_csrf(request, db, str(form.get("csrf_token", "")))
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
    async def update_contract_task(request: Request, contract_id: int, task_id: int,
                                   db: Session = Depends(get_db)):
        user, _csrf = user_csrf(request, db)
        contract = fetch_contract(db, contract_id)
        check_read(user, contract)
        check_write(user, contract)
        if contract.archived_at is not None:
            raise HTTPException(status_code=409, detail="Archivierter Vertrag ist schreibgeschützt")
        task = db.get(ContractTask, task_id)
        if not task or task.contract_id != contract.id:
            raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden")
        form = await request.form(max_fields=8)
        require_csrf(request, db, str(form.get("csrf_token", "")))
        try:
            values = validate_task_fields(form, db, contract)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        before = task_snapshot(task)
        for key, value in values.items():
            setattr(task, key, value)
        task.updated_at = now_utc()
        db.flush()
        db.add(Revision(contract_id=contract.id, actor_id=user.id, action="task_updated",
                        before=before, after=task_snapshot(task)))
        db.commit()
        return redirect(f"/contracts/{contract.id}?notice=task_updated")

    @app.post("/contracts/{contract_id}/reviews")
    async def create_contract_review(request: Request, contract_id: int, db: Session = Depends(get_db)):
        user, _csrf = user_csrf(request, db)
        contract = fetch_contract(db, contract_id)
        check_read(user, contract)
        check_write(user, contract)
        if contract.archived_at is not None:
            raise HTTPException(status_code=409, detail="Archivierter Vertrag ist schreibgeschützt")
        form = await request.form(max_fields=6)
        require_csrf(request, db, str(form.get("csrf_token", "")))
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
                                request_text=request_text, status="open", due_date=due_date,
                                created_by_id=user.id, updated_at=now_utc())
        db.add(review)
        db.flush()
        db.add(Revision(contract_id=contract.id, actor_id=user.id, action="review_created",
                        before=None, after=review_snapshot(review)))
        db.commit()
        return redirect(f"/contracts/{contract.id}?notice=review_created")

    @app.post("/contracts/{contract_id}/reviews/{review_id}")
    async def update_contract_review(request: Request, contract_id: int, review_id: int,
                                     db: Session = Depends(get_db)):
        user, _csrf = user_csrf(request, db)
        contract = fetch_contract(db, contract_id)
        check_read(user, contract)
        if user.role not in ("admin", "reviewer"):
            raise HTTPException(status_code=403, detail="Nur die Kämmerei oder Prüfer können Rückmeldungen erfassen")
        review = db.get(ContractReview, review_id)
        if not review or review.contract_id != contract.id:
            raise HTTPException(status_code=404, detail="Prüfvorgang nicht gefunden")
        form = await request.form(max_fields=4)
        require_csrf(request, db, str(form.get("csrf_token", "")))
        status = str(form.get("status", "")).strip()
        result_text = str(form.get("result_text", "")).strip()
        if status not in CONTRACT_REVIEW_STATUS_LABELS:
            raise HTTPException(status_code=400, detail="Bitte einen gültigen Prüfstatus auswählen")
        if len(result_text) > 5000:
            raise HTTPException(status_code=400, detail="Die Rückmeldung darf höchstens 5.000 Zeichen enthalten")
        if status in ("approved", "changes_requested", "rejected") and not result_text:
            raise HTTPException(status_code=400, detail="Für diese Entscheidung ist eine begründete Rückmeldung erforderlich")
        before = review_snapshot(review)
        review.status = status
        review.result_text = result_text
        review.updated_by_id = user.id
        review.updated_at = now_utc()
        db.flush()
        db.add(Revision(contract_id=contract.id, actor_id=user.id, action="review_updated",
                        before=before, after=review_snapshot(review)))
        db.commit()
        return redirect(f"/contracts/{contract.id}?notice=review_updated")

    @app.post("/contracts/{contract_id}/documents")
    async def upload_document(request: Request, contract_id: int, db: Session = Depends(get_db)):
        user, _csrf = user_csrf(request, db)
        contract = fetch_contract(db, contract_id)
        check_read(user, contract)
        check_write(user, contract)
        if contract.archived_at is not None:
            raise HTTPException(status_code=409, detail="Archivierter Vertrag ist schreibgesch?tzt")
        form = await request.form(max_files=MAX_DOCUMENTS_PER_UPLOAD, max_fields=2)
        require_csrf(request, db, str(form.get("csrf_token", "")))
        uploads = [item for item in form.getlist("documents")
                   if isinstance(item, UploadFile) and item.filename]
        if not uploads:
            raise HTTPException(status_code=400, detail="Bitte mindestens eine Datei ausw?hlen")
        stored_documents = []
        try:
            for upload in uploads:
                stored_documents.append(await store_uploaded_document(upload, request.app.state.document_storage_dir))
            for stored in stored_documents:
                document = ContractDocument(
                    contract_id=contract.id, uploaded_by_id=user.id,
                    original_filename=stored["filename"], storage_key=stored["storage_key"],
                    content_type=stored["content_type"], size_bytes=stored["size_bytes"])
                db.add(document)
                db.flush()
                db.add(Revision(contract_id=contract.id, actor_id=user.id, action="document_uploaded",
                                before=None, after={"document_id": document.id,
                                                    "filename": stored["filename"],
                                                    "size_bytes": stored["size_bytes"],
                                                    "uploaded_at": document.uploaded_at.isoformat()}))
            db.commit()
        except Exception:
            db.rollback()
            for stored in stored_documents:
                stored["path"].unlink(missing_ok=True)
            raise
        finally:
            for upload in uploads:
                await upload.close()
        return redirect(f"/contracts/{contract_id}?notice=document_uploaded")

    @app.post("/contracts/{contract_id}/documents/link")
    async def link_external_document(request: Request, contract_id: int, db: Session = Depends(get_db)):
        user, _csrf = user_csrf(request, db)
        contract = fetch_contract(db, contract_id)
        check_read(user, contract)
        check_write(user, contract)
        if contract.archived_at is not None:
            raise HTTPException(status_code=409, detail="Archivierter Vertrag ist schreibgesch?tzt")
        form = await request.form(max_files=0, max_fields=3)
        require_csrf(request, db, str(form.get("csrf_token", "")))
        label = str(form.get("document_name", "")).strip()
        if not label or len(label) > 200:
            raise HTTPException(status_code=400, detail="Bitte eine Bezeichnung mit h?chstens 200 Zeichen angeben")
        external_url = validate_external_document_url(str(form.get("external_url", "")))
        document = ContractDocument(contract_id=contract.id, uploaded_by_id=user.id,
                                    original_filename=label, storage_key=None,
                                    content_type="application/x-dms-link", external_url=external_url,
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
        contract = fetch_contract(db, contract_id)
        check_read(user, contract)
        document = db.get(ContractDocument, document_id)
        if not document or document.contract_id != contract.id or not document.storage_key:
            raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
        path = request.app.state.document_storage_dir / document.storage_key
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Datei nicht gefunden")
        previewable = document.content_type == "application/pdf" or document.content_type.startswith("image/")
        disposition = "inline" if previewable and not download else "attachment"
        headers = {"Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(document.original_filename, safe='')}"}
        return FileResponse(path, media_type=document.content_type, headers=headers)

    @app.get("/contracts/{contract_id}/edit", response_class=HTMLResponse)
    def edit(request: Request, contract_id: int, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        contract = fetch_contract(db, contract_id)
        check_read(user, contract)
        check_write(user, contract)
        if contract.archived_at is not None:
            raise HTTPException(status_code=409, detail="Archivierter Vertrag ist schreibgeschützt")
        departments = db.scalars(select(Department).where(Department.is_active.is_(True)).order_by(Department.name)).all()
        values = snapshot(contract)
        return html(request, "form.html", {**base_context(request, user, csrf), "mode": "edit",
                    "contract": contract, "values": values, "departments": departments})

    @app.post("/contracts/{contract_id}/edit")
    async def save_edit(request: Request, contract_id: int, db: Session = Depends(get_db)):
        user, csrf = user_csrf(request, db)
        contract = fetch_contract(db, contract_id)
        check_read(user, contract)
        check_write(user, contract)
        form = await request.form(max_files=0, max_fields=32)
        require_csrf(request, db, str(form.get("csrf_token", "")))
        if contract.archived_at is not None:
            raise HTTPException(status_code=409, detail="Archivierter Vertrag ist schreibgeschützt")
        departments = db.scalars(select(Department).where(Department.is_active.is_(True)).order_by(Department.name)).all()
        try:
            values = validate_data(form, user, db)
        except ValidationError as exc:
            return html(request, "form.html", {**base_context(request, user, csrf), "mode": "edit",
                        "contract": contract, "values": form_values(form),
                        "departments": departments, "error": str(exc)}, 422)
        try:
            version = int(form.get("version", ""))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Versionsangabe fehlt")
        if version != contract.version:
            raise HTTPException(status_code=409, detail="Datensatz wurde inzwischen geändert. Bitte neu laden.")
        values["tax_reviewed_by_id"] = contract.tax_reviewed_by_id
        values["tax_reviewed_at"] = contract.tax_reviewed_at
        review_completed_now = values["tax_review_status"] == "completed" and (
            contract.tax_review_status != "completed"
            or contract.tax_review_result != values["tax_review_result"])
        if review_completed_now:
            values["tax_reviewed_by_id"] = user.id
            values["tax_reviewed_at"] = now_utc()
        before = snapshot(contract)
        result = db.execute(update(Contract).where(Contract.id == contract_id,
                                                  Contract.version == version,
                                                  Contract.archived_at.is_(None))
                            .values(**values, updated_by_id=user.id, updated_at=now_utc(),
                                    version=Contract.version + 1))
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="Datensatz wurde zwischenzeitlich geändert")
        db.refresh(contract)
        if review_completed_now:
            contract.tax_reviewed_by = user
        db.add(Revision(contract_id=contract.id, actor_id=user.id, action="updated",
                        before=before, after=snapshot(contract)))
        db.commit()
        return redirect(f"/contracts/{contract_id}?notice=updated")

    @app.post("/contracts/{contract_id}/archive")
    async def archive(request: Request, contract_id: int, db: Session = Depends(get_db)):
        user = require_user(request, db)
        contract = fetch_contract(db, contract_id)
        check_read(user, contract)
        check_write(user, contract)
        form = await request.form()
        require_csrf(request, db, str(form.get("csrf_token", "")))
        try:
            version = int(form.get("version", ""))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Versionsangabe fehlt")
        before = snapshot(contract)
        result = db.execute(update(Contract).where(Contract.id == contract_id,
                                                  Contract.version == version,
                                                  Contract.archived_at.is_(None))
                            .values(archived_at=now_utc(), updated_by_id=user.id,
                                    updated_at=now_utc(), version=Contract.version + 1))
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="Datensatz wurde bereits geändert oder archiviert")
        db.refresh(contract)
        db.add(Revision(contract_id=contract.id, actor_id=user.id, action="archived",
                        before=before, after=snapshot(contract)))
        db.commit()
        return redirect(f"/contracts/{contract_id}?notice=archived")

    return app


app = create_app()
