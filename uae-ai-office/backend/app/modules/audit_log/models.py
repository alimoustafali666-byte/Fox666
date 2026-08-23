import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.db.base import Base


class InetAddress(TypeDecorator):
    """Postgres INET column that round-trips as a plain Python `str`,
    matching this model's `Mapped[str | None]` annotation. psycopg3's
    default INET adapter returns `ipaddress.IPv4Address`/`IPv6Address`
    objects on SELECT, not `str` -- without this, any code reading
    AuditLog.ip_address (the API router's Pydantic serialization,
    notably) gets an object type it never asked for and doesn't accept.
    Binding (INSERT/UPDATE) already receives a plain string from
    app.core.request_ip.get_client_ip, which INET accepts natively, so
    only the read side needs converting.
    """

    impl = INET
    cache_ok = True

    def process_result_value(self, value: object | None, dialect: object) -> str | None:
        return None if value is None else str(value)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # No ON DELETE CASCADE (see migration 0009): audit history must not be
    # silently destroyed as a side effect of deleting the company it
    # belongs to.
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id")
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str]
    resource_type: Mapped[str]
    # Intentionally not a foreign key: resource_type varies (project,
    # document, company_member, ...), so resource_id is polymorphic and
    # can't point at a single referenced table.
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(InetAddress, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

