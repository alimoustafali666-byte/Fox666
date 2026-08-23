import io
import tempfile
import tracemalloc
import uuid
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage.factory import get_storage_provider
from app.db.session import set_company_context
from app.modules.audit_log.models import AuditLog
from app.modules.documents import repository, service
from app.modules.documents.models import Document
from app.modules.documents.upload_stream import measure_and_checksum
from tests.documents.helpers import PDF_BYTES, signup, upload_file


@dataclass
class _FakeUploadFile:
    """Minimal stand-in for fastapi.UploadFile -- service.upload_document
    only ever touches .filename and .file, so this is enough to call it
    directly (bypassing the HTTP layer) for tests that need to catch a
    simulated failure explicitly, the same way tests/projects/test_audit.py
    calls service.create_project directly for its audit-rollback test.
    """

    filename: str
    file: io.BytesIO


def _company_documents(db_session: Session, company_id: uuid.UUID) -> list[Document]:
    set_company_context(db_session, company_id)
    return list(db_session.execute(select(Document)).scalars())


def _company_audit_actions(db_session: Session, company_id: uuid.UUID) -> list[str]:
    set_company_context(db_session, company_id)
    return list(db_session.execute(select(AuditLog.action)).scalars())


# 52. DB failure after successful storage triggers compensating storage delete
def test_db_failure_after_storage_success_triggers_compensating_delete(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Calls service.upload_document directly (not through TestClient):
    TestClient's default raise_server_exceptions=True re-raises an
    unhandled exception into the test rather than turning it into an
    HTTP response, so an explicit direct call -- the same technique
    tests/projects/test_audit.py uses for its audit-rollback test -- is
    what lets this test actually catch and assert on the failure.
    """
    _, claims = signup(client, "consistency-db-failure@example.com")
    company_id = uuid.UUID(claims["company_id"])
    user_id = uuid.UUID(claims["sub"])

    def boom(*args, **kwargs):
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(repository, "create_document", boom)

    set_company_context(db_session, company_id)
    raised = False
    try:
        service.upload_document(
            db_session,
            company_id=company_id,
            actor_user_id=user_id,
            project_id=None,
            document_type="contract",
            upload_file=_FakeUploadFile(filename="doc.pdf", file=io.BytesIO(PDF_BYTES)),
        )
    except RuntimeError:
        raised = True
        db_session.rollback()

    assert raised
    assert _company_documents(db_session, company_id) == []
    provider = get_storage_provider()
    assert provider._objects == {}  # compensating delete removed the uploaded object


# 53. audit failure after successful storage triggers rollback + compensating delete
def test_audit_failure_after_storage_success_triggers_rollback_and_compensating_delete(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, claims = signup(client, "consistency-audit-failure@example.com")
    company_id = uuid.UUID(claims["company_id"])
    user_id = uuid.UUID(claims["sub"])

    def boom(*args, **kwargs):
        raise RuntimeError("simulated audit write failure")

    monkeypatch.setattr(service, "record_audit_event", boom)

    set_company_context(db_session, company_id)
    raised = False
    try:
        service.upload_document(
            db_session,
            company_id=company_id,
            actor_user_id=user_id,
            project_id=None,
            document_type="contract",
            upload_file=_FakeUploadFile(filename="doc.pdf", file=io.BytesIO(PDF_BYTES)),
        )
    except RuntimeError:
        raised = True
        db_session.rollback()

    assert raised
    assert _company_documents(db_session, company_id) == []
    provider = get_storage_provider()
    assert provider._objects == {}


# 54. storage upload failure creates no document DB row
def test_storage_upload_failure_creates_no_document_row(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, claims = signup(client, "consistency-storage-failure@example.com")
    company_id = uuid.UUID(claims["company_id"])

    provider = get_storage_provider()

    def boom(*args, **kwargs):
        from app.core.storage.exceptions import StorageUnavailable

        raise StorageUnavailable("simulated storage outage")

    monkeypatch.setattr(provider, "upload", boom)

    response = upload_file(client, token, filename="doc.pdf", content=PDF_BYTES)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "storage_unavailable"
    assert _company_documents(db_session, company_id) == []


# 55. failed upload does not produce a successful upload audit
def test_failed_upload_does_not_produce_a_successful_upload_audit(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, claims = signup(client, "consistency-no-false-audit@example.com")
    company_id = uuid.UUID(claims["company_id"])

    provider = get_storage_provider()

    def boom(*args, **kwargs):
        from app.core.storage.exceptions import StorageUnavailable

        raise StorageUnavailable("simulated storage outage")

    monkeypatch.setattr(provider, "upload", boom)

    upload_file(client, token, filename="doc.pdf", content=PDF_BYTES)

    assert "document.upload" not in _company_audit_actions(db_session, company_id)


# 56. file processing does not create uncontrolled memory growth
def test_hashing_a_large_file_does_not_load_it_into_memory_as_one_buffer() -> None:
    """measure_and_checksum reads in small fixed-size chunks from an
    already disk-spooled file -- peak additional memory allocated by the
    function itself should be a small, bounded multiple of the chunk
    size, not proportional to the (~20MB) file being processed.
    """
    file_size = 20 * 1024 * 1024
    with tempfile.SpooledTemporaryFile(max_size=0) as spooled:  # max_size=0: always disk-backed
        spooled.write(b"\x00" * file_size)
        spooled.seek(0)

        tracemalloc.start()
        try:
            size, _ = measure_and_checksum(spooled, max_bytes=settings.storage_max_upload_bytes)
            _current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

    assert size == file_size
    # Well under the file size -- proves this pass is chunked, not one
    # full-file read into a single in-memory object.
    assert peak < 5 * 1024 * 1024

