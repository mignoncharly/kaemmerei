"""Object-level authorization and form parsing, independent of HTTP templates."""
from datetime import date
from decimal import Decimal, InvalidOperation
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import ContactIdentity, Contract, Department, User
from app.options import CONTRACT_STATUSES, FINANCIAL_DIRECTIONS, PAYMENT_INTERVALS, TAX_REVIEW_STATUSES


class ValidationError(Exception):
    pass


def active_access(user: User) -> bool:
    """Department membership only grants access while that department is active."""
    return user.is_active and user.role in ('admin', 'reviewer', 'department') and (user.role != "department" or (
        user.department is not None and user.department.is_active))


def can_read(user: User, contract: Contract) -> bool:
    return active_access(user) and (user.role in ("admin", "reviewer") or (
        user.role == "department" and user.department_id == contract.department_id))


def can_write(user: User, contract: Contract | None = None) -> bool:
    if not active_access(user):
        return False
    if user.role == "admin":
        return True
    if user.role != "department" or user.department_id is None:
        return False
    return contract is None or contract.department_id == user.department_id


def validate_data(form, user: User, db: Session, existing: Contract | None = None) -> dict:
    def text(name: str, limit: int, required: bool = False) -> str:
        value = str(form.get(name, "") or "").strip()
        if len(value) > limit:
            raise ValidationError(f"{name}: hÃ¶chstens {limit} Zeichen erlaubt")
        if required and not value:
            raise ValidationError(f"{name}: Pflichtfeld")
        return value

    designation = text("designation", 200, True)
    contract_type = text("contract_type", 120, True)
    contract_partner = text("contract_partner", 200)
    date_description = text("date_description", 80)
    contact_person = text("contact_person", 160, True)
    deputy_contact_person = text("deputy_contact_person", 160)
    status = text("status", 20) or (existing.status if existing else "draft")
    if status not in {code for code, _label in CONTRACT_STATUSES}:
        raise ValidationError("Bitte einen gÃ¼ltigen Vertragsstatus auswÃ¤hlen")
    try:
        relevant_date = date.fromisoformat(text("relevant_date", 10, True))
    except ValueError as exc:
        raise ValidationError("Bitte ein gÃ¼ltiges Vertragsbeginn-Datum angeben") from exc
    end_date_text = text("end_date", 10)
    try:
        end_date = date.fromisoformat(end_date_text) if end_date_text else None
    except ValueError as exc:
        raise ValidationError("Bitte ein gÃ¼ltiges Vertragsende angeben") from exc
    if end_date and end_date < relevant_date:
        raise ValidationError("Das Vertragsende darf nicht vor dem Vertragsbeginn liegen")
    notice_period_text = text("notice_period_months", 3)
    try:
        notice_period_months = int(notice_period_text) if notice_period_text else None
    except ValueError as exc:
        raise ValidationError("Die KÃ¼ndigungsfrist muss in ganzen Monaten angegeben werden") from exc
    if notice_period_months is not None and not 0 <= notice_period_months <= 120:
        raise ValidationError("Die KÃ¼ndigungsfrist muss zwischen 0 und 120 Monaten liegen")
    automatic_renewal = str(form.get("automatic_renewal", "")) == "1"
    renewal_period_text = text("renewal_period_months", 3)
    try:
        renewal_period_months = int(renewal_period_text) if renewal_period_text else None
    except ValueError as exc:
        raise ValidationError("Der Verlängerungszeitraum muss in ganzen Monaten angegeben werden") from exc
    if renewal_period_months is not None and not 1 <= renewal_period_months <= 120:
        raise ValidationError("Der Verlängerungszeitraum muss zwischen 1 und 120 Monaten liegen")
    if automatic_renewal and not end_date:
        raise ValidationError("Für eine automatische Verlängerung muss ein Vertragsende angegeben werden")
    if automatic_renewal and renewal_period_months is None:
        raise ValidationError("Bitte den Zeitraum der automatischen Verlängerung angeben")
    if not automatic_renewal:
        renewal_period_months = None
    annual_value_text = text("annual_value", 24).replace(",", ".")
    try:
        annual_value = Decimal(annual_value_text).quantize(Decimal("0.01")) if annual_value_text else None
    except InvalidOperation as exc:
        raise ValidationError("Bitte einen gÃ¼ltigen Jahreswert in Euro angeben") from exc
    if annual_value is not None and (not annual_value.is_finite() or annual_value < 0 or annual_value > Decimal("9999999999.99")):
        raise ValidationError("Der Jahreswert muss zwischen 0 und 9.999.999.999,99 Euro liegen")
    contract_value_text = text("contract_value", 24).replace(",", ".")
    try:
        contract_value = Decimal(contract_value_text).quantize(Decimal("0.01")) if contract_value_text else None
    except InvalidOperation as exc:
        raise ValidationError("Bitte einen gültigen Gesamtvertragswert in Euro angeben") from exc
    if contract_value is not None and (not contract_value.is_finite() or contract_value < 0 or contract_value > Decimal("9999999999.99")):
        raise ValidationError("Der Gesamtvertragswert muss zwischen 0 und 9.999.999.999,99 Euro liegen")
    financial_direction = text("financial_direction", 12)
    if financial_direction and financial_direction not in {code for code, _label in FINANCIAL_DIRECTIONS}:
        raise ValidationError("Bitte Einnahme oder Ausgabe auswählen")
    payment_interval = text("payment_interval", 16)
    if payment_interval and payment_interval not in {code for code, _label in PAYMENT_INTERVALS}:
        raise ValidationError("Bitte ein gültiges Zahlungsintervall auswählen")
    budget_assignment = text("budget_assignment", 120)
    tax_review_status = text("tax_review_status", 20) or "not_checked"
    if tax_review_status not in {code for code, _label in TAX_REVIEW_STATUSES}:
        raise ValidationError("Bitte einen gültigen §-2b-Prüfstatus auswählen")
    tax_review_result = text("tax_review_result", 3000)
    if tax_review_status == "completed" and not tax_review_result:
        raise ValidationError("Für eine abgeschlossene §-2b-Prüfung bitte das Prüfergebnis dokumentieren")
    if user.role == "department":
        if not user.department_id:
            raise ValidationError("Kein Fachbereich zugeordnet")
        department_id = user.department_id  # Never trust posted department for Fachbereich.
    elif user.role == "admin":
        try:
            department_id = int(text("department_id", 12, True))
        except ValueError as exc:
            raise ValidationError("Bitte Fachbereich auswÃ¤hlen") from exc
    else:
        raise ValidationError("Keine Schreibberechtigung")
    department = db.scalar(select(Department).where(Department.id == department_id, Department.is_active.is_(True)))
    if not department:
        raise ValidationError("Fachbereich existiert nicht oder ist gesperrt")
    for field, value in (('contact_person', contact_person), ('deputy_contact_person', deputy_contact_person)):
        if not value:
            continue
        identities = db.scalars(select(ContactIdentity).where(
            ContactIdentity.display_name == value,
            (ContactIdentity.department_id == department_id) | ContactIdentity.department_id.is_(None))).all()
        if identities and not any(identity.is_active for identity in identities):
            if existing is None or existing.department_id != department_id or getattr(existing, field) != value:
                raise ValidationError('Deaktivierte Kontakte dürfen nicht neu zugeordnet werden')
    return dict(designation=designation, contract_type=contract_type,
                contract_partner=contract_partner, relevant_date=relevant_date,
                end_date=end_date, notice_period_months=notice_period_months,
                automatic_renewal=automatic_renewal, renewal_period_months=renewal_period_months,
                contract_value=contract_value, annual_value=annual_value,
                financial_direction=financial_direction or None,
                payment_interval=payment_interval or None,
                budget_assignment=budget_assignment,
                tax_review_status=tax_review_status, tax_review_result=tax_review_result,
                tax_reviewed_by_id=None, tax_reviewed_at=None,
                date_description=date_description,
                department_id=department_id, contact_person=contact_person,
                deputy_contact_person=deputy_contact_person, status=status)


def snapshot(contract: Contract) -> dict:
    return dict(contract_number=contract.contract_number,
                designation=contract.designation, contract_type=contract.contract_type,
                contract_partner=contract.contract_partner,
                relevant_date=contract.relevant_date.isoformat(),
                end_date=contract.end_date.isoformat() if contract.end_date else "",
                notice_period_months=contract.notice_period_months if contract.notice_period_months is not None else "",
                automatic_renewal=contract.automatic_renewal,
                renewal_period_months=contract.renewal_period_months if contract.renewal_period_months is not None else "",
                contract_value=format(contract.contract_value, "f") if contract.contract_value is not None else "",
                annual_value=format(contract.annual_value, "f") if contract.annual_value is not None else "",
                financial_direction=contract.financial_direction or "",
                payment_interval=contract.payment_interval or "",
                budget_assignment=contract.budget_assignment,
                tax_review_status=contract.tax_review_status,
                tax_review_result=contract.tax_review_result,
                tax_reviewed_by=contract.tax_reviewed_by.username if contract.tax_reviewed_by else "",
                tax_reviewed_at=contract.tax_reviewed_at.isoformat() if contract.tax_reviewed_at else "",
                date_description=contract.date_description, department_id=contract.department_id,
                contact_person=contract.contact_person,
                deputy_contact_person=contract.deputy_contact_person,
                status=contract.status,
                archived_at=contract.archived_at.isoformat() if contract.archived_at else None,
                version=contract.version, content_revision=contract.content_revision,
                approval_provenance=contract.approval_provenance, tax_provenance=contract.tax_provenance)
