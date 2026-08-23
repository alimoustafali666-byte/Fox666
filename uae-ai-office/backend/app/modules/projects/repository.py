import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.modules.projects.models import Project


def create_project(
    db: Session,
    *,
    company_id: uuid.UUID,
    name: str,
    project_code: str | None,
    description: str | None,
    status: str,
) -> Project:
    project = Project(
        company_id=company_id,
        name=name,
        project_code=project_code,
        description=description,
        status=status,
    )
    db.add(project)
    db.flush()
    return project


def get_project_by_id(db: Session, *, company_id: uuid.UUID, project_id: uuid.UUID) -> Project | None:
    """Explicit company_id filter is defense in depth on top of RLS, not
    a substitute for it -- see the tenant_isolation policy on `projects`.
    A project belonging to a different company doesn't exist as far as
    this query is concerned, which is exactly the IDOR-safe behavior the
    service layer needs (never distinguish "not yours" from "not real").
    """
    return db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == company_id)
    ).scalar_one_or_none()


def list_projects(
    db: Session,
    *,
    company_id: uuid.UUID,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None = None,
    status: str | None = None,
    project_code: str | None = None,
    name_search: str | None = None,
) -> list[Project]:
    query = select(Project).where(Project.company_id == company_id)

    if status is not None:
        query = query.where(Project.status == status)
    if project_code is not None:
        query = query.where(Project.project_code == project_code)
    if name_search is not None:
        query = query.where(Project.name.ilike(f"%{name_search}%"))
    if cursor is not None:
        cursor_created_at, cursor_id = cursor
        query = query.where(
            or_(
                Project.created_at < cursor_created_at,
                and_(Project.created_at == cursor_created_at, Project.id < cursor_id),
            )
        )

    query = query.order_by(Project.created_at.desc(), Project.id.desc()).limit(limit)
    return list(db.execute(query).scalars())


def update_project(db: Session, project: Project, changes: dict[str, Any]) -> Project:
    for field, value in changes.items():
        setattr(project, field, value)
    # No DB-level auto-update trigger exists (a deliberate Phase 1
    # simplification, see Step 2's design notes) -- this is the first
    # module to actually perform updates, so it's set explicitly here.
    project.updated_at = datetime.now(UTC)
    db.flush()
    return project

