import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.session import set_company_context
from app.modules.audit_log.models import AuditLog
from app.modules.projects import service
from app.modules.projects.models import Project
from app.modules.projects.schemas import ProjectCreate
from tests.projects.helpers import auth_header, signup


def _create(client: TestClient, token: str, **kwargs) -> dict:
    payload = {"name": "Project"} | kwargs
    response = client.post("/v1/projects", json=payload, headers=auth_header(token))
    assert response.status_code == 201
    return response.json()


def _actions_for(db_session: Session, company_id: uuid.UUID) -> list[str]:
    set_company_context(db_session, company_id)
    return list(
        db_session.execute(
            select(AuditLog.action).order_by(AuditLog.created_at.asc())
        ).scalars()
    )


# 34. project.create audit event is written
def test_project_create_writes_audit_event(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "audit-create@example.com")
    company_id = uuid.UUID(claims["company_id"])

    _create(client, token, name="Audited Project")

    assert "project.create" in _actions_for(db_session, company_id)


# 35. project.update audit event is written
def test_project_update_writes_audit_event(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "audit-update@example.com")
    company_id = uuid.UUID(claims["company_id"])
    project = _create(client, token, name="Original")

    client.patch(f"/v1/projects/{project['id']}", json={"name": "Changed"}, headers=auth_header(token))

    assert "project.update" in _actions_for(db_session, company_id)


# 36. project.delete audit event is written
def test_project_delete_writes_audit_event(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "audit-delete@example.com")
    company_id = uuid.UUID(claims["company_id"])
    project = _create(client, token, name="To Cancel")

    client.delete(f"/v1/projects/{project['id']}", headers=auth_header(token))

    assert "project.delete" in _actions_for(db_session, company_id)


# 38. audit metadata contains no sensitive/unnecessary request dump
def test_audit_metadata_contains_only_safe_fields(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "audit-safe-metadata@example.com")
    company_id = uuid.UUID(claims["company_id"])
    project = _create(client, token, name="Original", description="A" * 500, project_code="CODE-X")

    client.patch(
        f"/v1/projects/{project['id']}",
        json={"description": "B" * 500, "name": "Renamed"},
        headers=auth_header(token),
    )

    set_company_context(db_session, company_id)
    entry = db_session.execute(
        select(AuditLog).where(AuditLog.action == "project.update")
    ).scalar_one()

    assert entry.metadata_["changed_fields"] == ["description", "name"]
    # description's actual text must never appear in audit metadata --
    # only that it changed, tracked via changed_fields above.
    assert "A" * 500 not in str(entry.metadata_)
    assert "B" * 500 not in str(entry.metadata_)
    assert entry.metadata_["before"] == {"name": "Original"}
    assert entry.metadata_["after"] == {"name": "Renamed"}
    # no raw request object, headers, or auth material of any kind
    metadata_text = str(entry.metadata_)
    for forbidden in ("authorization", "cookie", "password", "token"):
        assert forbidden not in metadata_text.lower()


# 37. audit failure rolls back required project mutation
def test_create_project_rolls_back_if_audit_write_fails(
    db_session: Session, monkeypatch
) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("simulated audit write failure")

    monkeypatch.setattr(service, "record_audit_event", boom)

    company_id = db_session.execute(
        text("INSERT INTO companies (name) VALUES ('Audit Rollback Co') RETURNING id")
    ).scalar_one()
    user_id = db_session.execute(
        text(
            "INSERT INTO users (email, password_hash) VALUES ('audit-rollback@example.com', 'x') RETURNING id"
        )
    ).scalar_one()
    set_company_context(db_session, company_id)

    raised = False
    try:
        service.create_project(
            db_session,
            company_id=company_id,
            actor_user_id=user_id,
            data=ProjectCreate(name="Should Not Persist"),
        )
    except RuntimeError:
        raised = True
        db_session.rollback()

    assert raised, "a failed audit write must not let project creation silently succeed"

    set_company_context(db_session, company_id)
    project = db_session.execute(
        select(Project).where(Project.name == "Should Not Persist")
    ).scalar_one_or_none()
    assert project is None

