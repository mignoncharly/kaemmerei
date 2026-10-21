"""Structured, intentionally small contract inventory."""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base
from app.schema_rules import RULES


def now_utc() -> datetime:
    # All timestamps are stored as UTC without timezone conversion by SQLite.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('admin', 'department', 'reviewer')", name="valid_user_role"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False, deferred=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    can_approve: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)
    department: Mapped[Department | None] = relationship()


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    user: Mapped[User | None] = relationship()


class IntegrationToken(Base):
    __tablename__ = "integration_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, deferred=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    department: Mapped[Department | None] = relationship()
    created_by: Mapped[User] = relationship()


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)


class Contract(Base):
    __tablename__ = "contracts"
    __table_args__ = (
        Index("ix_contracts_department_archived", "department_id", "archived_at"),
        Index("ux_contracts_contract_number", "contract_number", unique=True),
        CheckConstraint(
            "status IN ('draft', 'in_progress', 'active', 'terminated', 'ended')",
            name="valid_contract_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_number: Mapped[str] = mapped_column(String(32), nullable=False, server_default="")
    designation: Mapped[str] = mapped_column(String(200), nullable=False)
    contract_type: Mapped[str] = mapped_column(String(120), nullable=False)
    contract_partner: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    relevant_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notice_period_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    automatic_renewal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    renewal_period_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contract_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    annual_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    financial_direction: Mapped[str | None] = mapped_column(String(12), nullable=True)
    payment_interval: Mapped[str | None] = mapped_column(String(16), nullable=True)
    budget_assignment: Mapped[str] = mapped_column(String(120), nullable=False, default="", server_default="")
    tax_review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_checked", server_default="not_checked")
    tax_review_result: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    tax_reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    tax_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    date_description: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False)
    contact_person: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    deputy_contact_person: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    department: Mapped[Department] = relationship()
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])
    updated_by: Mapped[User] = relationship(foreign_keys=[updated_by_id])
    tax_reviewed_by: Mapped[User | None] = relationship(foreign_keys=[tax_reviewed_by_id])

class Revision(Base):
    __tablename__ = "revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=False, index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)
    actor: Mapped[User] = relationship()


class ContractDocument(Base):
    __tablename__ = "contract_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=False, index=True)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(200), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(40), nullable=True, unique=True)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False, default="application/pdf")
    external_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)
    contract: Mapped[Contract] = relationship()
    uploaded_by: Mapped[User] = relationship()


class ContractTask(Base):
    __tablename__ = "contract_tasks"
    __table_args__ = (
        CheckConstraint("kind IN ('review', 'complete', 'update', 'other')", name="valid_task_kind"),
        CheckConstraint("status IN ('open', 'in_progress', 'done')", name="valid_task_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)
    contract: Mapped[Contract] = relationship()
    assigned_user: Mapped[User | None] = relationship(foreign_keys=[assigned_user_id])
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])


class ContractReview(Base):
    __tablename__ = "contract_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("recipient_teams.id", ondelete="RESTRICT"), nullable=True)
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=False, index=True)
    recipient: Mapped[str] = mapped_column(String(80), nullable=False)
    recipient_detail: Mapped[str] = mapped_column(String(160), nullable=False, default="", server_default="")
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    request_text: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open", server_default="open")
    result_text: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)
    contract: Mapped[Contract] = relationship()
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])
    updated_by: Mapped[User | None] = relationship(foreign_keys=[updated_by_id])


class IdentityGuard(Base):
    __tablename__ = "identity_guard"
    id: Mapped[int] = mapped_column(primary_key=True)
    epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class IdentityAudit(Base):
    __tablename__ = "identity_audit"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    principal: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str] = mapped_column(String(120), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, default='success', server_default='success')
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, default=lambda: str(uuid4()))


class SecurityEvent(Base):
    __tablename__ = 'security_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'))
    token_id: Mapped[int | None] = mapped_column(ForeignKey('integration_tokens.id', ondelete='RESTRICT'))
    principal: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str] = mapped_column(String(120), nullable=False)
    contract_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False)


class ContactIdentity(Base):
    __tablename__ = "contact_identities"
    __table_args__ = (Index("ux_contact_scope_name", "scope_key", "display_name", unique=True),)
    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True)
    scope_key: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class RecipientTeam(Base):
    __tablename__ = "recipient_teams"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class RecipientMembership(Base):
    __tablename__ = "recipient_memberships"
    team_id: Mapped[int] = mapped_column(ForeignKey("recipient_teams.id", ondelete="RESTRICT"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)


# Keep ORM constraint declarations identical to forward migration invariants.
for _table, _rules in RULES.items():
    for _name, _expression in _rules.items():
        if not any(c.name == _name for c in Base.metadata.tables[_table].constraints):
            Base.metadata.tables[_table].append_constraint(CheckConstraint(_expression, name=_name))
