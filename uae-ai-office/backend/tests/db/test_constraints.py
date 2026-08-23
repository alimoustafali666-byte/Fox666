import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.db.session import set_company_context
from tests.db.conftest import TwoTenantSeed


def _insert_project(db_session: Session, company_id, code) -> None:
    db_session.execute(
        text("INSERT INTO projects (company_id, name, project_code) VALUES (:c, 'P', :code)"),
        {"c": company_id, "code": code},
    )


def test_duplicate_project_code_within_company_is_rejected(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    _insert_project(db_session, two_tenants.company_a, "PRJ-100")

    with pytest.raises(IntegrityError), db_session.begin_nested():
        _insert_project(db_session, two_tenants.company_a, "PRJ-100")


def test_same_project_code_allowed_across_different_companies(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    _insert_project(db_session, two_tenants.company_a, "SHARED-CODE")

    set_company_context(db_session, two_tenants.company_b)
    _insert_project(db_session, two_tenants.company_b, "SHARED-CODE")  # must not raise

    db_session.flush()


def test_null_project_code_is_allowed_multiple_times(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)

    _insert_project(db_session, two_tenants.company_a, None)
    _insert_project(db_session, two_tenants.company_a, None)  # must not raise

    db_session.flush()


def test_document_soft_delete_marks_row_without_removing_it(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)

    db_session.execute(
        text("UPDATE documents SET deleted_at = now() WHERE id = :id"),
        {"id": two_tenants.document_a},
    )

    all_rows = db_session.execute(text("SELECT id FROM documents")).all()
    active_rows = db_session.execute(
        text("SELECT id FROM documents WHERE deleted_at IS NULL")
    ).all()

    assert two_tenants.document_a in {r[0] for r in all_rows}, "row must still physically exist"
    assert two_tenants.document_a not in {r[0] for r in active_rows}, (
        "a deleted_at-filtered query must exclude the soft-deleted row"
    )


def test_company_name_is_required(db_session: Session) -> None:
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(text("INSERT INTO companies (timezone) VALUES ('Asia/Dubai')"))


def test_invalid_company_role_is_rejected(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)

    with pytest.raises(DBAPIError), db_session.begin_nested():
        db_session.execute(
            text(
                "INSERT INTO company_members (company_id, user_id, role) "
                "VALUES (:c, :u, 'superadmin')"
            ),
            {"c": two_tenants.company_a, "u": two_tenants.user_a},
        )


def test_invalid_document_type_is_rejected(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)

    with pytest.raises(DBAPIError), db_session.begin_nested():
        db_session.execute(
            text(
                "INSERT INTO documents "
                "(company_id, uploaded_by, file_name, file_type, file_size_bytes, "
                " storage_key, checksum_sha256, document_type) "
                "VALUES (:c, :u, 'x.pdf', 'pdf', 1, 'x', 'x', 'not_a_real_type')"
            ),
            {"c": two_tenants.company_a, "u": two_tenants.user_a},
        )


def test_invalid_project_status_is_rejected(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)

    with pytest.raises(DBAPIError), db_session.begin_nested():
        db_session.execute(
            text(
                "INSERT INTO projects (company_id, name, status) "
                "VALUES (:c, 'P', 'not_a_real_status')"
            ),
            {"c": two_tenants.company_a},
        )


def test_document_type_defaults_to_other(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)

    document_type = db_session.execute(
        text("SELECT document_type FROM documents WHERE id = :id"),
        {"id": two_tenants.document_a},
    ).scalar_one()

    assert document_type == "other"


def test_project_status_defaults_to_planning(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)

    status = db_session.execute(
        text("SELECT status FROM projects WHERE id = :id"), {"id": two_tenants.project_a}
    ).scalar_one()

    assert status == "planning"

