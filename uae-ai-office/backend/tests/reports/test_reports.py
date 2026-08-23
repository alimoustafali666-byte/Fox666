"""Step 20 -- central reporting system. Covers: report generation per
domain (reusing each domain's own RLS/RBAC-scoped service, never a
broader query), all four export formats, RBAC gating (audit_log is
owner/admin only; support_tickets and collaboration are always
self-scoped, even for owner/admin -- matching those domains' own
existing design), cross-company isolation, and adversarial/forged-input
handling.
"""

import io
import uuid

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import set_company_context
from app.modules.auth.models import User
from app.modules.tenancy.models import CompanyMember
from tests.documents.helpers import PDF_BYTES
from tests.documents.helpers import upload_file as upload_document_file


def _signup(client: TestClient, email: str, company_name: str = "Reports Test Co") -> tuple[str, dict]:
    response = client.post(
        "/v1/auth/signup",
        json={"email": email, "password": "correct horse battery staple", "full_name": "Owner User", "company_name": company_name},
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    return token, claims


def _seed_member(db_session: Session, *, company_id: uuid.UUID, email: str, role: str) -> tuple[str, uuid.UUID]:
    user = User(email=email, password_hash=hash_password("irrelevant-password-value"), full_name="Seeded User")
    db_session.add(user)
    db_session.flush()
    set_company_context(db_session, company_id)
    db_session.add(CompanyMember(company_id=company_id, user_id=user.id, role=role))
    db_session.flush()
    return create_access_token(user_id=user.id, company_id=company_id, role=role), user.id


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_project(client: TestClient, token: str, name: str = "QA Tower") -> dict:
    resp = client.post("/v1/projects", json={"name": name}, headers=_auth(token))
    assert resp.status_code == 201
    return resp.json()


def _create_task(client: TestClient, token: str, title: str, **extra) -> dict:
    resp = client.post("/v1/tasks", json={"title": title, **extra}, headers=_auth(token))
    assert resp.status_code == 201
    return resp.json()


# --- Report type listing ---


def test_report_types_hides_audit_log_from_member(client: TestClient, db_session: Session):
    owner_token, claims = _signup(client, "owner1@example.com")
    company_id = uuid.UUID(claims["company_id"])
    member_token, _ = _seed_member(db_session, company_id=company_id, email="member1@example.com", role="member")

    owner_types = {t["type"] for t in client.get("/v1/reports/types", headers=_auth(owner_token)).json()}
    member_types = {t["type"] for t in client.get("/v1/reports/types", headers=_auth(member_token)).json()}

    assert "audit_log" in owner_types
    assert "audit_log" not in member_types
    assert "projects" in member_types and "tasks" in member_types


# --- Projects report ---


def test_projects_report_preview_and_all_export_formats(client: TestClient):
    token, _ = _signup(client, "owner2@example.com")
    _create_project(client, token, "QA Tower Fit-out")

    preview = client.get("/v1/reports/projects/preview", headers=_auth(token))
    assert preview.status_code == 200
    body = preview.json()
    assert body["meta"]["row_count"] == 1
    assert body["rows"][0]["name"] == "QA Tower Fit-out"
    assert body["meta"]["reference_number"].startswith("RPT-PRJ-")

    expected_content_types = {
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
    }
    for fmt, expected_ct in expected_content_types.items():
        resp = client.get(f"/v1/reports/projects?format={fmt}", headers=_auth(token))
        assert resp.status_code == 200, f"{fmt} failed: {resp.text}"
        assert resp.headers["content-type"].startswith(expected_ct)
        assert "attachment" in resp.headers["content-disposition"]
        assert len(resp.content) > 0


def test_projects_report_status_filter(client: TestClient):
    token, _ = _signup(client, "owner3@example.com")
    p1 = _create_project(client, token, "Active One")
    p2 = _create_project(client, token, "On Hold One")
    client.patch(f"/v1/projects/{p2['id']}", json={"status": "on_hold"}, headers=_auth(token))

    resp = client.get("/v1/reports/projects/preview?status=on_hold", headers=_auth(token))
    assert resp.status_code == 200
    names = {row["name"] for row in resp.json()["rows"]}
    assert names == {"On Hold One"}
    del p1


# --- Tasks report visibility ---


def test_tasks_report_member_sees_only_own_tasks(client: TestClient, db_session: Session):
    owner_token, claims = _signup(client, "owner4@example.com")
    company_id = uuid.UUID(claims["company_id"])
    member_token, member_id = _seed_member(db_session, company_id=company_id, email="member4@example.com", role="member")

    _create_task(client, owner_token, "Owner's own task")
    client.post(
        "/v1/tasks", json={"title": "Assigned to member", "assigned_to": str(member_id)}, headers=_auth(owner_token)
    )

    member_preview = client.get("/v1/reports/tasks/preview", headers=_auth(member_token))
    assert member_preview.status_code == 200
    titles = {row["title"] for row in member_preview.json()["rows"]}
    assert titles == {"Assigned to member"}

    owner_preview = client.get("/v1/reports/tasks/preview", headers=_auth(owner_token))
    owner_titles = {row["title"] for row in owner_preview.json()["rows"]}
    assert "Owner's own task" in owner_titles
    assert "Assigned to member" in owner_titles


# --- Documents report ---


def test_documents_report_includes_project_name(client: TestClient):
    token, _ = _signup(client, "owner5@example.com")
    project = _create_project(client, token, "Doc Project")
    upload_document_file(
        client, token, filename="contract.pdf", content=PDF_BYTES, document_type="contract", project_id=project["id"]
    )

    resp = client.get("/v1/reports/documents/preview", headers=_auth(token))
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["file_name"] == "contract.pdf"
    assert rows[0]["project"] == "Doc Project"


# --- Audit log report RBAC ---


def test_audit_log_report_forbidden_for_member(client: TestClient, db_session: Session):
    owner_token, claims = _signup(client, "owner6@example.com")
    company_id = uuid.UUID(claims["company_id"])
    member_token, _ = _seed_member(db_session, company_id=company_id, email="member6@example.com", role="member")

    resp = client.get("/v1/reports/audit_log/preview", headers=_auth(member_token))
    assert resp.status_code == 403

    owner_resp = client.get("/v1/reports/audit_log/preview", headers=_auth(owner_token))
    assert owner_resp.status_code == 200


def test_audit_log_report_download_forbidden_for_member(client: TestClient, db_session: Session):
    _, claims = _signup(client, "owner6b@example.com")
    company_id = uuid.UUID(claims["company_id"])
    member_token, _ = _seed_member(db_session, company_id=company_id, email="member6b@example.com", role="member")

    resp = client.get("/v1/reports/audit_log?format=csv", headers=_auth(member_token))
    assert resp.status_code == 403


# --- Support tickets report: always self-scoped, even for the owner ---


def test_support_tickets_report_is_self_scoped_even_for_owner(client: TestClient, db_session: Session):
    owner_token, claims = _signup(client, "owner7@example.com")
    company_id = uuid.UUID(claims["company_id"])
    member_token, _ = _seed_member(db_session, company_id=company_id, email="member7@example.com", role="member")

    client.post(
        "/v1/support/tickets",
        json={"category": "other", "subject": "Member's issue", "description": "Something broke."},
        headers=_auth(member_token),
    )

    owner_preview = client.get("/v1/reports/support_tickets/preview", headers=_auth(owner_token))
    assert owner_preview.status_code == 200
    assert owner_preview.json()["meta"]["row_count"] == 0

    member_preview = client.get("/v1/reports/support_tickets/preview", headers=_auth(member_token))
    assert member_preview.json()["meta"]["row_count"] == 1


# --- Daily brief report ---


def test_daily_brief_report_with_no_brief_is_empty(client: TestClient):
    token, _ = _signup(client, "owner8@example.com")
    resp = client.get("/v1/reports/daily_brief/preview", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["meta"]["row_count"] == 0


# --- Collaboration report ---


def test_collaboration_report_lists_own_conversations(client: TestClient, db_session: Session):
    owner_token, claims = _signup(client, "owner9@example.com")
    company_id = uuid.UUID(claims["company_id"])
    _, member_id = _seed_member(db_session, company_id=company_id, email="member9@example.com", role="member")

    client.post(
        "/v1/collaboration/conversations/direct",
        json={"other_user_id": str(member_id)},
        headers=_auth(owner_token),
    )

    resp = client.get("/v1/reports/collaboration/preview", headers=_auth(owner_token))
    assert resp.status_code == 200
    assert resp.json()["meta"]["row_count"] >= 1


# --- Dashboard summary role scoping ---


def test_dashboard_summary_role_scoping(client: TestClient, db_session: Session):
    owner_token, claims = _signup(client, "owner10@example.com")
    company_id = uuid.UUID(claims["company_id"])
    member_token, _ = _seed_member(db_session, company_id=company_id, email="member10@example.com", role="member")
    manager_token, _ = _seed_member(db_session, company_id=company_id, email="manager10@example.com", role="manager")

    member_summary = client.get("/v1/reports/dashboard-summary", headers=_auth(member_token)).json()
    assert member_summary["company_tasks"] is None
    assert member_summary["recent_activity"] is None

    manager_summary = client.get("/v1/reports/dashboard-summary", headers=_auth(manager_token)).json()
    assert manager_summary["company_tasks"] is not None
    assert manager_summary["recent_activity"] is None  # manager isn't owner/admin

    owner_summary = client.get("/v1/reports/dashboard-summary", headers=_auth(owner_token)).json()
    assert owner_summary["company_tasks"] is not None
    assert owner_summary["recent_activity"] is not None


# --- Security / adversarial ---


def test_unknown_report_type_returns_404(client: TestClient):
    token, _ = _signup(client, "owner11@example.com")
    resp = client.get("/v1/reports/not_a_real_report/preview", headers=_auth(token))
    assert resp.status_code == 404


def test_unsupported_export_format_returns_400(client: TestClient):
    token, _ = _signup(client, "owner12@example.com")
    resp = client.get("/v1/reports/projects?format=exe", headers=_auth(token))
    assert resp.status_code == 400


def test_direct_endpoint_access_without_authentication(client: TestClient):
    resp = client.get("/v1/reports/projects/preview")
    assert resp.status_code == 401
    resp = client.get("/v1/reports/projects?format=csv")
    assert resp.status_code == 401
    resp = client.get("/v1/reports/dashboard-summary")
    assert resp.status_code == 401


def test_cross_company_report_isolation(client: TestClient):
    token_a, _ = _signup(client, "ownerA@example.com", company_name="Company A")
    token_b, _ = _signup(client, "ownerB@example.com", company_name="Company B")

    _create_project(client, token_a, "Company A Secret Project")

    b_preview = client.get("/v1/reports/projects/preview", headers=_auth(token_b))
    assert b_preview.status_code == 200
    assert b_preview.json()["meta"]["row_count"] == 0
    assert b_preview.json()["meta"]["company_name"] == "Company B"


def test_forged_project_id_filter_returns_empty_not_leaked_data(client: TestClient):
    """A project_id belonging to a DIFFERENT company, passed as a report
    filter, must never leak that company's documents -- the underlying
    documents_service.list_documents call is still scoped to the
    caller's own company_id regardless of which project_id is asked
    for."""
    token_a, _ = _signup(client, "ownerA2@example.com", company_name="Company A2")
    token_b, _ = _signup(client, "ownerB2@example.com", company_name="Company B2")

    project_a = _create_project(client, token_a, "A2 Project")
    upload_document_file(
        client, token_a, filename="secret.pdf", content=PDF_BYTES, document_type="contract", project_id=project_a["id"]
    )

    resp = client.get(f"/v1/reports/documents/preview?project_id={project_a['id']}", headers=_auth(token_b))
    assert resp.status_code == 200
    assert resp.json()["meta"]["row_count"] == 0


def test_company_name_with_special_characters_produces_safe_filename(client: TestClient):
    """A company name containing quote/header-breaking characters (it's
    user-editable via PATCH /companies/current) must never corrupt the
    Content-Disposition header of a report download."""
    token, _ = _signup(client, "owner13@example.com", company_name='Weird "Co\r\nX-Injected: yes')
    resp = client.get("/v1/reports/projects?format=csv", headers=_auth(token))
    assert resp.status_code == 200
    disposition = resp.headers["content-disposition"]
    assert "\r" not in disposition
    assert "\n" not in disposition
    assert '"' in disposition  # only the wrapping quotes we add ourselves
    assert disposition.count('"') == 2


def test_reference_number_is_unique_per_generation(client: TestClient):
    token, _ = _signup(client, "owner14@example.com")
    first = client.get("/v1/reports/projects/preview", headers=_auth(token)).json()
    second = client.get("/v1/reports/projects/preview", headers=_auth(token)).json()
    assert first["meta"]["reference_number"] != second["meta"]["reference_number"]


def test_arabic_locale_report_returns_arabic_labels(client: TestClient):
    token, _ = _signup(client, "owner15@example.com")
    _create_project(client, token, "مشروع تجريبي")
    resp = client.get("/v1/reports/projects/preview?locale=ar", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["title"] == "تقرير المشاريع"
    assert body["columns"][0]["label"] == "الاسم"


def test_invalid_locale_falls_back_to_english(client: TestClient):
    token, _ = _signup(client, "owner16@example.com")
    resp = client.get("/v1/reports/projects/preview?locale=fr", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["meta"]["title"] == "Projects Report"


def test_pdf_report_is_a_well_formed_pdf(client: TestClient):
    token, _ = _signup(client, "owner17@example.com")
    _create_project(client, token, "PDF Check Project")
    resp = client.get("/v1/reports/projects?format=pdf", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF-")
    assert b"%%EOF" in resp.content[-64:] or b"EOF" in resp.content[-1024:]


def test_xlsx_report_is_a_valid_workbook(client: TestClient):
    import openpyxl

    token, _ = _signup(client, "owner18@example.com")
    _create_project(client, token, "XLSX Check Project")
    resp = client.get("/v1/reports/projects?format=xlsx", headers=_auth(token))
    assert resp.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(resp.content))
    assert wb.active is not None


def test_member_cannot_override_assigned_to_filter_to_see_others_tasks(client: TestClient, db_session: Session):
    """A member's tasks report is always forced to assigned_to=self at
    the service layer -- passing a forged assigned_to query param for
    someone else must be silently ignored, never honored."""
    owner_token, claims = _signup(client, "owner19@example.com")
    company_id = uuid.UUID(claims["company_id"])
    member_token, member_id = _seed_member(db_session, company_id=company_id, email="member19@example.com", role="member")

    client.post(
        "/v1/tasks", json={"title": "Owner's private task", "assigned_to": None}, headers=_auth(owner_token)
    )

    owner_user_id = uuid.UUID(claims["sub"])
    resp = client.get(
        f"/v1/reports/tasks/preview?assigned_to={owner_user_id}", headers=_auth(member_token)
    )
    assert resp.status_code == 200
    titles = {row["title"] for row in resp.json()["rows"]}
    assert "Owner's private task" not in titles
    del member_id


def test_collaboration_report_excludes_conversations_the_caller_is_not_in(client: TestClient, db_session: Session):
    owner_token, claims = _signup(client, "owner20@example.com")
    company_id = uuid.UUID(claims["company_id"])
    _, member_a_id = _seed_member(db_session, company_id=company_id, email="membera20@example.com", role="member")
    member_b_token, _ = _seed_member(db_session, company_id=company_id, email="memberb20@example.com", role="member")

    client.post(
        "/v1/collaboration/conversations/direct",
        json={"other_user_id": str(member_a_id)},
        headers=_auth(owner_token),
    )

    resp = client.get("/v1/reports/collaboration/preview", headers=_auth(member_b_token))
    assert resp.status_code == 200
    assert resp.json()["meta"]["row_count"] == 0


def test_extra_company_id_in_update_body_is_ignored(client: TestClient):
    """CompanyUpdateRequest has no company_id field at all -- proves a
    client can't smuggle one in to redirect the update at a different
    company; Pydantic silently drops unknown fields by default."""
    token_a, _ = _signup(client, "ownerA3@example.com", company_name="Company A3")
    token_b, claims_b = _signup(client, "ownerB3@example.com", company_name="Company B3")
    company_b_id = claims_b["company_id"]

    resp = client.patch(
        "/v1/companies/current",
        json={"name": "Still A3 Only", "company_id": company_b_id},
        headers=_auth(token_a),
    )
    assert resp.status_code == 200

    b_current = client.get("/v1/companies/current", headers=_auth(token_b)).json()
    assert b_current["company"]["name"] == "Company B3"

