import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import set_company_context
from tests.db.conftest import TwoTenantSeed


def test_document_cannot_reference_another_companys_project(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    """Requirement 7: the composite FK on documents(project_id, company_id)
    -> projects(id, company_id) must reject a document that claims to
    belong to company A while pointing at a project owned by company B --
    even though this insert is attempted with company A's own RLS context
    active, i.e. RLS alone would not have caught this.
    """
    set_company_context(db_session, two_tenants.company_a)

    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(
            text(
                "INSERT INTO documents "
                "(company_id, project_id, uploaded_by, file_name, file_type, "
                " file_size_bytes, storage_key, checksum_sha256) "
                "VALUES (:company_id, :project_id, :uploaded_by, 'evil.pdf', 'pdf', "
                " 1, 'x', 'x')"
            ),
            {
                "company_id": two_tenants.company_a,
                "project_id": two_tenants.project_b,  # belongs to company B
                "uploaded_by": two_tenants.user_a,
            },
        )


def test_document_with_null_project_id_is_unaffected(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    """A company-level document (no project) must still be insertable --
    the composite FK's MATCH SIMPLE semantics skip the check when
    project_id is NULL.
    """
    set_company_context(db_session, two_tenants.company_a)

    doc_id = db_session.execute(
        text(
            "INSERT INTO documents "
            "(company_id, project_id, uploaded_by, file_name, file_type, "
            " file_size_bytes, storage_key, checksum_sha256) "
            "VALUES (:company_id, NULL, :uploaded_by, 'company-level.pdf', 'pdf', "
            " 1, 'x', 'y') RETURNING id"
        ),
        {"company_id": two_tenants.company_a, "uploaded_by": two_tenants.user_a},
    ).scalar_one()

    assert doc_id is not None

