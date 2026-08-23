import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.audit_log.service import record_audit_event
from app.modules.projects import repository
from app.modules.projects.exceptions import ProjectCodeAlreadyExistsError, ProjectNotFoundError
from app.modules.projects.models import Project
from app.modules.projects.schemas import ProjectCreate, ProjectUpdate

# Fields whose actual value is safe and useful enough to put in audit
# metadata. `description` is deliberately excluded: it can be long,
# free-text, and not particularly useful in a short audit trail entry --
# see the module docstring in audit_log/service.py and Step 6's brief on
# not dumping the full request into metadata. Its *name* still appears in
# changed_fields, so "description was changed" is still visible.
_AUDIT_SAFE_FIELDS = {"name", "project_code", "status"}


def create_project(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    data: ProjectCreate,
    ip_address: str | None = None,
) -> Project:
    try:
        project = repository.create_project(
            db,
            company_id=company_id,
            name=data.name,
            project_code=data.project_code,
            description=data.description,
            status=data.status,
        )
        # Same transaction as the state change it describes: if this
        # raises, the project creation above rolls back too.
        record_audit_event(
            db,
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="project.create",
            resource_type="project",
            resource_id=project.id,
            metadata={"name": project.name, "status": project.status},
            ip_address=ip_address,
        )
    except IntegrityError:
        db.rollback()
        raise ProjectCodeAlreadyExistsError(
            "A project with this code already exists in your company."
        ) from None

    db.commit()
    return project


def get_project(db: Session, *, company_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    project = repository.get_project_by_id(db, company_id=company_id, project_id=project_id)
    if project is None:
        raise ProjectNotFoundError("Project not found.")
    return project


def list_projects(
    db: Session,
    *,
    company_id: uuid.UUID,
    limit: int,
    cursor: tuple | None,
    status: str | None,
    project_code: str | None,
    name_search: str | None,
) -> list[Project]:
    return repository.list_projects(
        db,
        company_id=company_id,
        limit=limit,
        cursor=cursor,
        status=status,
        project_code=project_code,
        name_search=name_search,
    )


def update_project(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    project_id: uuid.UUID,
    data: ProjectUpdate,
    ip_address: str | None = None,
) -> Project:
    project = repository.get_project_by_id(db, company_id=company_id, project_id=project_id)
    if project is None:
        raise ProjectNotFoundError("Project not found.")

    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return project  # nothing to do, nothing to audit

    before = {field: getattr(project, field) for field in changes if field in _AUDIT_SAFE_FIELDS}
    after = {field: changes[field] for field in changes if field in _AUDIT_SAFE_FIELDS}

    try:
        repository.update_project(db, project, changes)
        record_audit_event(
            db,
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="project.update",
            resource_type="project",
            resource_id=project.id,
            metadata={
                "changed_fields": sorted(changes.keys()),
                **({"before": before} if before else {}),
                **({"after": after} if after else {}),
            },
            ip_address=ip_address,
        )
    except IntegrityError:
        db.rollback()
        raise ProjectCodeAlreadyExistsError(
            "A project with this code already exists in your company."
        ) from None

    db.commit()
    return project


def delete_project(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    project_id: uuid.UUID,
    ip_address: str | None = None,
) -> Project:
    """"Delete" means archive: the row is never physically removed, and
    the FK from documents (added when that module lands) is never
    cascade-triggered by this. Idempotent -- cancelling an
    already-cancelled project is a no-op, not an error, and doesn't add
    a redundant audit entry.
    """
    project = repository.get_project_by_id(db, company_id=company_id, project_id=project_id)
    if project is None:
        raise ProjectNotFoundError("Project not found.")

    if project.status == "cancelled":
        return project

    previous_status = project.status
    repository.update_project(db, project, {"status": "cancelled"})
    record_audit_event(
        db,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="project.delete",
        resource_type="project",
        resource_id=project.id,
        metadata={"previous_status": previous_status, "new_status": "cancelled"},
        ip_address=ip_address,
    )

    db.commit()
    return project

