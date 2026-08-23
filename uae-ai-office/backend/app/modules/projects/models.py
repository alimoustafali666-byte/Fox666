import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Single source of truth, reused by both the DB enum below and
# app.modules.projects.schemas' Pydantic validation.
PROJECT_STATUSES: tuple[str, ...] = ("planning", "active", "on_hold", "completed", "cancelled")

project_status = ENUM(
    *PROJECT_STATUSES,
    name="project_status",
    create_type=False,  # created explicitly in the migration
)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        # project_code is optional; NULLs are not compared equal by Postgres,
        # so any number of projects with no code coexist, while two projects
        # in the same company cannot share a non-null code.
        UniqueConstraint("company_id", "project_code", name="uq_projects_company_code"),
        # Referenced by documents' composite FK so a document can never
        # point at a project owned by a different company (see documents
        # migration / model).
        UniqueConstraint("id", "company_id", name="uq_projects_id_company"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    name: Mapped[str]
    project_code: Mapped[str | None] = mapped_column(nullable=True)
    description: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(project_status, server_default="planning")
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

