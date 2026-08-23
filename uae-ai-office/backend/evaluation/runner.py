"""The Step 11.5 evaluation harness engine. Orchestrates: a throwaway
scratch database (never the shared dev DB) -> migrations -> a real
FastAPI TestClient driving the actual production endpoints (signup,
project/document upload, process, index, conversations, ask) -> one full
retrieval+ask pass per evaluation case, capturing both raw retrieval
diagnostics (so a retrieval failure is distinguishable from a generation
failure) and the end-to-end API result -> teardown.

Provider selection is entirely credential-driven (never invented): if
ANTHROPIC_API_KEY / EMBEDDING_API_KEY are present in the environment,
the real Anthropic/Voyage providers are used and the run is labeled
LIVE; otherwise Fake{Embedding,LLM}Provider are used and the run is
labeled BLOCKED_BY_CREDENTIALS. A BLOCKED_BY_CREDENTIALS run still
exercises the full harness end-to-end (proving it's ready to run live
the moment credentials are supplied) but its accuracy numbers reflect
the deterministic fake providers, NOT real model/embedding quality --
report.py labels this distinction prominently rather than letting a
harness-validation run masquerade as a real accuracy measurement.
"""

import os
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from evaluation import (
    _bootstrap,  # noqa: F401 -- sets required env vars before any app.* import below
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
ADMIN_DATABASE_URL = "postgresql+psycopg://uae_app:uae_app@localhost:5432/postgres"


def create_scratch_database() -> str:
    name = f"uae_ai_office_eval_{uuid.uuid4().hex[:12]}"
    engine = create_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        engine.dispose()
    return name


def drop_scratch_database(name: str) -> None:
    engine = create_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": name},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
    finally:
        engine.dispose()


def run_migrations(database_url: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={"PATH": "/usr/bin:/bin", "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Evaluation scratch-DB migration failed:\n{result.stderr}")


@contextmanager
def scratch_database(*, keep: bool = False) -> Iterator[str]:
    name = create_scratch_database()
    url = f"postgresql+psycopg://uae_app:uae_app@localhost:5432/{name}"
    try:
        run_migrations(url)
        yield url
    finally:
        if not keep:
            drop_scratch_database(name)
        else:
            print(f"[evaluation] keeping scratch database: {name}", file=sys.stderr)


@dataclass
class ProviderStatus:
    embedding_provider: str
    embedding_model: str
    embedding_status: str  # "LIVE" or "BLOCKED_BY_CREDENTIALS"
    llm_provider: str
    llm_model: str
    llm_status: str


def configure_providers():
    """Credential-driven provider selection -- never invents a key. Must
    run after _bootstrap and after the scratch DB's get_db override is in
    place, but before any embedding/LLM call. Returns the ProviderStatus
    the report needs plus the live FakeLLMProvider instance when in fake
    mode (so the harness can inspect `.calls`).
    """
    from app.core.config import settings
    from app.core.embeddings import factory as embedding_factory
    from app.core.llm import factory as llm_factory
    from app.core.llm.fake_provider import FakeLLMProvider
    from app.core.storage import factory as storage_factory

    # Object storage is out of scope for this evaluation (Step 8 already
    # covers it) -- always FakeStorageProvider, exactly like the pytest
    # suite's autouse fixture, so no S3/MinIO credentials are ever needed
    # just to upload the synthetic fixtures.
    settings.storage_provider = "fake"
    storage_factory.reset_storage_provider_cache()

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    voyage_key = os.environ.get("EMBEDDING_API_KEY")

    if voyage_key:
        settings.embedding_provider = "voyage"
        settings.embedding_api_key = voyage_key
        embedding_status = "LIVE"
    else:
        settings.embedding_provider = "fake"
        embedding_status = "BLOCKED_BY_CREDENTIALS"
    embedding_factory.reset_embedding_provider_cache()

    if anthropic_key:
        settings.llm_provider = "anthropic"
        settings.anthropic_api_key = anthropic_key
        llm_status = "LIVE"
    else:
        settings.llm_provider = "fake"
        llm_status = "BLOCKED_BY_CREDENTIALS"
    llm_factory.reset_llm_provider_cache()

    embedding_provider = embedding_factory.get_embedding_provider()
    llm_provider = llm_factory.get_llm_provider()
    fake_llm = llm_provider if isinstance(llm_provider, FakeLLMProvider) else None

    status = ProviderStatus(
        embedding_provider=settings.embedding_provider,
        embedding_model=embedding_provider.model_identifier,
        embedding_status=embedding_status,
        llm_provider=settings.llm_provider,
        llm_model=llm_provider.model_identifier if hasattr(llm_provider, "model_identifier") else settings.claude_model,
        llm_status=llm_status,
    )
    return status, fake_llm


@dataclass
class HarnessContext:
    client: object
    db: Session
    token: str
    company_id: uuid.UUID
    documents_by_key: dict[str, dict] = field(default_factory=dict)
    projects_by_key: dict[str, str] = field(default_factory=dict)


def build_test_client(database_url: str, db_session: Session):
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import app

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def setup_harness(client, db: Session) -> HarnessContext:
    from evaluation.fixtures.documents import build_fixture_set
    from tests.documents.helpers import auth_header, signup

    token, claims = signup(
        client, f"eval-{uuid.uuid4().hex[:8]}@example.com", company_name="Evaluation Co"
    )
    company_id = uuid.UUID(claims["company_id"])

    projects_by_key: dict[str, str] = {}
    for key, name in [("villa", "Al Barsha Villa Renovation"), ("office", "Deira Office Fit-Out")]:
        response = client.post("/v1/projects", json={"name": name}, headers=auth_header(token))
        if response.status_code != 201:
            raise RuntimeError(f"Failed to create project {key}: {response.text}")
        projects_by_key[key] = response.json()["id"]

    documents_by_key: dict[str, dict] = {}
    for fixture in build_fixture_set():
        upload = client.post(
            "/v1/documents",
            headers=auth_header(token),
            data={"document_type": fixture.document_type, "project_id": projects_by_key[fixture.project_key]},
            files={"file": (fixture.filename, fixture.content, "application/octet-stream")},
        )
        if upload.status_code != 201:
            raise RuntimeError(f"Upload failed for {fixture.key}: {upload.text}")
        document = upload.json()

        processed = client.post(f"/v1/documents/{document['id']}/process", headers=auth_header(token))
        if processed.status_code != 200:
            raise RuntimeError(f"Processing failed for {fixture.key}: {processed.text}")

        indexed = client.post(f"/v1/documents/{document['id']}/index", headers=auth_header(token))
        if indexed.status_code != 200:
            raise RuntimeError(f"Indexing failed for {fixture.key}: {indexed.text}")

        documents_by_key[fixture.key] = indexed.json()

    return HarnessContext(
        client=client, db=db, token=token, company_id=company_id,
        documents_by_key=documents_by_key, projects_by_key=projects_by_key,
    )


def resolve_expected_chunk_ids(ctx: HarnessContext, case) -> list[uuid.UUID]:
    from app.modules.documents.models import DocumentChunk

    document_ids = [uuid.UUID(ctx.documents_by_key[k]["id"]) for k in case.expected_document_keys]
    if not document_ids:
        return []
    stmt = select(DocumentChunk.id).where(DocumentChunk.document_id.in_(document_ids))
    if case.expected_page_number is not None:
        stmt = stmt.where(DocumentChunk.page_number == case.expected_page_number)
    if case.expected_sheet_name is not None:
        stmt = stmt.where(DocumentChunk.sheet_name == case.expected_sheet_name)
    return list(ctx.db.execute(stmt).scalars())


def get_chunk_content(db: Session, chunk_id: uuid.UUID) -> str:
    from app.modules.documents.models import DocumentChunk

    row = db.execute(select(DocumentChunk.content).where(DocumentChunk.id == chunk_id)).scalar_one_or_none()
    return row or ""


def run_one_case(ctx: HarnessContext, case, *, config_label: str, conversation_id: str | None) -> tuple:
    from app.core.config import settings
    from app.core.embeddings.factory import get_embedding_provider
    from evaluation import retrieval_diagnostics
    from evaluation.metrics import contains_normalized
    from evaluation.types import CaseResult, RetrievedChunkDiagnostic
    from tests.documents.helpers import auth_header

    document_id = (
        uuid.UUID(ctx.documents_by_key[case.document_filter_key]["id"]) if case.document_filter_key else None
    )
    project_id = uuid.UUID(ctx.projects_by_key[case.project_filter_key]) if case.project_filter_key else None

    result = CaseResult(
        case_id=case.id, category=case.category, question=case.question, config_label=config_label,
        diagnostic_only=case.diagnostic_only, expected_sufficient=case.expected_sufficient,
        expected_answer_contains=list(case.expected_answer_contains),
        expected_answer_not_contains=list(case.expected_answer_not_contains),
        expected_document_keys=list(case.expected_document_keys),
        expected_document_ids=[uuid.UUID(ctx.documents_by_key[k]["id"]) for k in case.expected_document_keys],
    )
    result.expected_chunk_ids = resolve_expected_chunk_ids(ctx, case)

    document_key_by_id = {uuid.UUID(v["id"]): k for k, v in ctx.documents_by_key.items()}

    embedding_provider = get_embedding_provider()
    t0 = time.monotonic()
    query_vector = embedding_provider.embed_query(case.question)
    result.embedding_latency_ms = (time.monotonic() - t0) * 1000

    t1 = time.monotonic()
    candidates = retrieval_diagnostics.raw_ranked_candidates(
        ctx.db, company_id=ctx.company_id, query_vector=query_vector,
        embedding_model=embedding_provider.model_identifier, limit=20,
        document_id=document_id, project_id=project_id,
    )
    result.postgres_retrieval_latency_ms = (time.monotonic() - t1) * 1000

    threshold = settings.retrieval_similarity_threshold
    for rank, (chunk, score) in enumerate(candidates, start=1):
        result.retrieved.append(
            RetrievedChunkDiagnostic(
                chunk_id=chunk.id, document_id=chunk.document_id,
                document_key=document_key_by_id.get(chunk.document_id),
                rank=rank, score=score, above_threshold=score >= threshold,
            )
        )

    if conversation_id is None:
        conv = ctx.client.post("/v1/conversations", json={}, headers=auth_header(ctx.token))
        if conv.status_code != 201:
            result.error = f"conversation create failed: {conv.text[:300]}"
            return result, None
        conversation_id = conv.json()["id"]

    body: dict = {"question": case.question}
    if document_id is not None:
        body["document_id"] = str(document_id)
    if project_id is not None:
        body["project_id"] = str(project_id)

    t2 = time.monotonic()
    ask_response = ctx.client.post(
        f"/v1/conversations/{conversation_id}/messages", json=body, headers=auth_header(ctx.token)
    )
    result.total_latency_ms = (time.monotonic() - t2) * 1000
    result.http_status = ask_response.status_code

    if ask_response.status_code != 201:
        result.error = ask_response.text[:500]
        return result, conversation_id

    payload = ask_response.json()
    result.actual_sufficient = payload["is_sufficient"]
    result.actual_answer = payload["content"]

    citation_document_ids = []
    citation_chunk_ids = []
    for citation in payload["citations"]:
        citation_document_ids.append(uuid.UUID(citation["document_id"]))
        chunk_id = uuid.UUID(citation["document_chunk_id"])
        citation_chunk_ids.append(chunk_id)
        chunk_content = get_chunk_content(ctx.db, chunk_id)
        supports = (
            any(contains_normalized(chunk_content, exp) for exp in case.expected_answer_contains)
            if case.expected_answer_contains else True
        )
        result.citation_supports_answer.append(supports)
    result.actual_citation_document_ids = citation_document_ids
    result.actual_citation_chunk_ids = citation_chunk_ids

    # Token usage / model identifier -- not exposed via the API response
    # by design (Step 11 keeps them internal cost data); the harness
    # queries the persisted Message row directly, exactly like
    # tests/conversations/test_ask_persistence_and_metadata.py does.
    from app.modules.conversations.models import Message

    message_row = ctx.db.execute(
        select(Message).where(Message.id == uuid.UUID(payload["id"]))
    ).scalar_one()
    result.input_tokens = message_row.input_tokens
    result.output_tokens = message_row.output_tokens
    result.llm_called = message_row.model_identifier is not None

    return result, conversation_id


@dataclass
class RunOutput:
    case_results: list
    provider_status: ProviderStatus
    company_id: uuid.UUID
    documents_by_key: dict[str, dict]
    config_label: str
    threshold: float
    top_k: int


def run_full_evaluation(*, keep_db: bool = False) -> RunOutput:
    from app.core.config import settings
    from evaluation.dataset import CASES
    from evaluation.metrics import score_case

    with scratch_database(keep=keep_db) as database_url:
        engine = create_engine(database_url, pool_pre_ping=True)
        try:
            connection = engine.connect()
            # join_transaction_mode="create_savepoint" mirrors every
            # pytest db_session fixture in this codebase: the connection
            # opens ONE real transaction up front, and every db.commit()
            # the app performs inside a request only releases/re-creates
            # a SAVEPOINT within it rather than truly committing. This
            # matters here specifically because RLS context
            # (SET LOCAL app.current_company_id/app.current_user_id) is
            # scoped to the real transaction -- a genuine COMMIT would
            # reset it, which is exactly what happened before this fix:
            # the very first POST /v1/projects call committed, cleared
            # the RLS context, and the router's own follow-up read of the
            # just-created row (refreshing its expired ORM attributes)
            # came back empty under RLS, raising ObjectDeletedError.
            outer_transaction = connection.begin()
            db = Session(bind=connection, join_transaction_mode="create_savepoint")
            try:
                client = build_test_client(database_url, db)
                provider_status, _fake_llm = configure_providers()
                ctx = setup_harness(client, db)
                db.commit()

                config_label = (
                    f"threshold={settings.retrieval_similarity_threshold},"
                    f"top_k={settings.retrieval_top_k_default}"
                )

                case_results = []
                conversation_ids: dict[str, str] = {}
                for case in CASES:
                    conversation_id = None
                    if case.is_followup_of:
                        conversation_id = conversation_ids.get(case.is_followup_of)
                    result, used_conversation_id = run_one_case(
                        ctx, case, config_label=config_label, conversation_id=conversation_id
                    )
                    db.commit()
                    conversation_ids[case.id] = used_conversation_id
                    case_results.append(score_case(result))

                return RunOutput(
                    case_results=case_results, provider_status=provider_status,
                    company_id=ctx.company_id, documents_by_key=ctx.documents_by_key,
                    config_label=config_label, threshold=settings.retrieval_similarity_threshold,
                    top_k=settings.retrieval_top_k_default,
                )
            finally:
                db.close()
                outer_transaction.rollback()
                connection.close()
        finally:
            engine.dispose()

