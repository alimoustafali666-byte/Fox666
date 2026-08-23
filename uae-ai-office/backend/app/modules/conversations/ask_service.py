"""Ask Your Business -- the Step 11 grounded Q&A orchestrator. Structurally
mirrors app.modules.documents.indexing_orchestrator: mark/persist a small
step, commit, do pure in-memory work (retrieval + the LLM call +
validation), then atomically persist the result.

CRITICAL ARCHITECTURAL RULE: this module is the ONLY thing that decides
what "grounded" means. Claude is never the retrieval engine (it only ever
sees the document_context this module selects and hands it, via
app.modules.documents.retrieval_service) and Claude's own claimed
citations are never trusted directly -- every citation returned here has
been independently re-validated against this request's own retrieved
chunks before being persisted or returned; see _validate_citations.

DOCUMENT CONTENT IS DATA, NOT INSTRUCTIONS. retrieval_results[*].content
is untrusted text extracted from the company's own documents; this
module passes it to the LLM provider as document_context only -- it is
never interpreted, executed, or treated as an instruction here either.
"""

import time
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.embeddings.exceptions import EmbeddingError
from app.core.llm.exceptions import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMError,
    LLMMalformedOutputError,
    LLMOperationError,
    LLMUnavailable,
)
from app.core.llm.factory import get_llm_provider
from app.core.llm.provider import (
    DocumentContextItem,
    GroundedAnswerCitation,
    GroundedAnswerRequest,
    GroundedAnswerResult,
    HistoryTurn,
)
from app.modules.audit_log.service import record_audit_event
from app.modules.conversations import repository
from app.modules.conversations.exceptions import (
    AskUnavailableError,
    BlankQuestionError,
    QuestionTooLongError,
)
from app.modules.conversations.models import Conversation, MessageCitation
from app.modules.documents import retrieval_service
from app.modules.documents.models import Document, DocumentChunk
from app.modules.documents.retrieval_service import RetrievalResult

INSUFFICIENT_INFORMATION_TEXT = "I don't have enough information in the available documents."

_API_ERROR_BY_LLM_ERROR_CODE: dict[str, type] = {
    "llm_provider_unavailable": AskUnavailableError,
    "llm_provider_authentication_failed": AskUnavailableError,
    "llm_provider_misconfigured": AskUnavailableError,
    "llm_operation_failed": AskUnavailableError,
}


@dataclass
class CitationSource:
    document_chunk_id: uuid.UUID
    document_id: uuid.UUID
    file_name: str
    document_type: str
    project_id: uuid.UUID | None
    page_number: int | None
    sheet_name: str | None
    section_name: str | None
    source_location: dict | None


@dataclass
class AskResult:
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    is_sufficient: bool | None
    model_identifier: str | None
    created_at: datetime
    citations: list[CitationSource]


def ask_question(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    conversation: Conversation,
    question: str,
    document_id: uuid.UUID | None,
    project_id: uuid.UUID | None,
    document_type: str | None,
    ip_address: str | None,
) -> AskResult:
    question = question.strip()
    if not question:
        raise BlankQuestionError("Question must not be blank.")
    if len(question) > settings.ask_max_question_length:
        raise QuestionTooLongError(
            f"Question must not exceed {settings.ask_max_question_length} characters."
        )

    history = _build_history(db, company_id=company_id, conversation_id=conversation.id)

    repository.create_message(
        db,
        id=uuid.uuid4(),
        company_id=company_id,
        conversation_id=conversation.id,
        role="user",
        content=question,
    )
    repository.touch_conversation(db, conversation)
    db.commit()

    started_at = time.monotonic()
    try:
        retrieval_results = retrieval_service.search_by_query_text(
            db,
            company_id=company_id,
            query=question,
            top_k=settings.retrieval_top_k_default,
            document_id=document_id,
            project_id=project_id,
            document_type=document_type,
        )
    except EmbeddingError as exc:
        duration_ms = int((time.monotonic() - started_at) * 1000)
        record_audit_event(
            db,
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="ai.provider_failure",
            resource_type="conversation",
            resource_id=conversation.id,
            metadata={
                "conversation_id": str(conversation.id),
                "failure_category": "retrieval_unavailable",
                "duration_ms": duration_ms,
            },
            ip_address=ip_address,
        )
        db.commit()
        raise AskUnavailableError("Ask Your Business is temporarily unavailable.") from exc

    if not retrieval_results:
        assistant_message = repository.create_message(
            db,
            id=uuid.uuid4(),
            company_id=company_id,
            conversation_id=conversation.id,
            role="assistant",
            content=INSUFFICIENT_INFORMATION_TEXT,
            is_sufficient=False,
        )
        repository.touch_conversation(db, conversation)
        record_audit_event(
            db,
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="ai.question_insufficient",
            resource_type="conversation",
            resource_id=conversation.id,
            metadata={
                "conversation_id": str(conversation.id),
                "message_id": str(assistant_message.id),
                "retrieved_chunk_count": 0,
            },
            ip_address=ip_address,
        )
        db.commit()
        return _to_result(assistant_message=assistant_message, citations=[])

    result = _generate_validated_answer(question=question, history=history, retrieval_results=retrieval_results)

    if result is None:
        assistant_message = repository.create_message(
            db,
            id=uuid.uuid4(),
            company_id=company_id,
            conversation_id=conversation.id,
            role="assistant",
            content=INSUFFICIENT_INFORMATION_TEXT,
            is_sufficient=False,
        )
        repository.touch_conversation(db, conversation)
        record_audit_event(
            db,
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="ai.question_insufficient",
            resource_type="conversation",
            resource_id=conversation.id,
            metadata={
                "conversation_id": str(conversation.id),
                "message_id": str(assistant_message.id),
                "retrieved_chunk_count": len(retrieval_results),
                "reason": "citation_validation_failed",
            },
            ip_address=ip_address,
        )
        db.commit()
        return _to_result(assistant_message=assistant_message, citations=[])

    llm_result, valid_chunk_ids = result
    duration_ms = int((time.monotonic() - started_at) * 1000)

    assistant_message = repository.create_message(
        db,
        id=uuid.uuid4(),
        company_id=company_id,
        conversation_id=conversation.id,
        role="assistant",
        content=llm_result.answer,
        is_sufficient=llm_result.sufficient,
        model_identifier=llm_result.model_identifier,
        input_tokens=llm_result.input_tokens,
        output_tokens=llm_result.output_tokens,
    )
    repository.create_message_citations(
        db, company_id=company_id, message_id=assistant_message.id, chunk_ids=valid_chunk_ids
    )
    repository.touch_conversation(db, conversation)
    record_audit_event(
        db,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="ai.question_completed",
        resource_type="conversation",
        resource_id=conversation.id,
        metadata={
            "conversation_id": str(conversation.id),
            "message_id": str(assistant_message.id),
            "model_identifier": llm_result.model_identifier,
            "retrieved_chunk_count": len(retrieval_results),
            "citation_count": len(valid_chunk_ids),
            # Not "input_tokens"/"output_tokens": the audit sanitizer's
            # forbidden-key-substring check (app.modules.audit_log.sanitizer,
            # Step 5) blocks any key containing "token" on purpose, to catch
            # an accidentally-logged credential/session token -- a real
            # token *count* is unrelated but still matches the substring.
            # The authoritative token counts are already on the persisted
            # Message row itself (input_tokens/output_tokens); these two
            # audit fields are redundant operational context, not the
            # source of truth, so renaming them costs nothing.
            "input_usage_count": llm_result.input_tokens,
            "output_usage_count": llm_result.output_tokens,
            "duration_ms": duration_ms,
        },
        ip_address=ip_address,
    )
    db.commit()

    citations = _load_citation_sources(
        db, company_id=company_id, retrieval_results=retrieval_results, chunk_ids=valid_chunk_ids
    )
    return _to_result(assistant_message=assistant_message, citations=citations)


def _build_history(db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID) -> list[HistoryTurn]:
    if settings.ask_max_history_turns <= 0:
        return []
    rows = repository.list_recent_messages_for_history(
        db, company_id=company_id, conversation_id=conversation_id, max_turns=settings.ask_max_history_turns
    )
    return [HistoryTurn(role=row.role, content=row.content) for row in rows]


def _generate_validated_answer(
    *, question: str, history: list[HistoryTurn], retrieval_results: list[RetrievalResult]
) -> tuple[GroundedAnswerResult, list[uuid.UUID]] | None:
    """Calls the LLM provider, validating structured output and citations,
    with at most `settings.ask_max_citation_retries` controlled corrective
    retries -- never an open loop. Returns (llm_result, valid_chunk_ids)
    on success, or None if every attempt was exhausted without a
    trustworthy result (the caller treats that as a safe
    insufficient/validation-failure response, never a fabricated answer).
    """
    provider = get_llm_provider()
    refs: dict[str, RetrievalResult] = {str(i + 1): r for i, r in enumerate(retrieval_results)}
    document_context = [
        DocumentContextItem(ref=ref, content=r.content) for ref, r in refs.items()
    ]

    corrective_note: str | None = None
    max_attempts = settings.ask_max_citation_retries + 1

    for attempt in range(max_attempts):
        request = GroundedAnswerRequest(
            question=question,
            document_context=document_context,
            history=history,
            corrective_note=corrective_note,
        )
        try:
            llm_result = provider.generate_grounded_answer(request)
        except LLMMalformedOutputError:
            if attempt + 1 >= max_attempts:
                return None
            corrective_note = (
                "Your previous response did not match the required structured schema. "
                "Respond again using only the required JSON fields: answer, sufficient, citations."
            )
            continue
        except (LLMAuthenticationError, LLMConfigurationError, LLMUnavailable, LLMOperationError) as exc:
            api_error_cls = _API_ERROR_BY_LLM_ERROR_CODE.get(exc.error_code, AskUnavailableError)
            raise api_error_cls("Ask Your Business is temporarily unavailable.") from exc
        except LLMError as exc:  # last-resort safety net for any unmapped LLMError subclass
            raise AskUnavailableError("Ask Your Business is temporarily unavailable.") from exc

        valid_results, had_invalid_ref = _validate_citations(llm_result.citations, refs)
        invalid = had_invalid_ref or (llm_result.sufficient and not valid_results)

        if invalid:
            if attempt + 1 >= max_attempts:
                return None
            corrective_note = (
                "One or more citations you returned did not match a reference label actually "
                "given to you in DOCUMENT CONTEXT, or you claimed sufficient=true without any "
                "valid citation. Re-answer using only the exact ref labels shown in DOCUMENT "
                "CONTEXT, and set sufficient=false if you cannot support your answer with them."
            )
            continue

        valid_chunk_ids = _dedupe_preserving_order([r.chunk_id for r in valid_results])
        return llm_result, valid_chunk_ids

    return None


def _validate_citations(
    citations: list[GroundedAnswerCitation], refs: dict[str, RetrievalResult]
) -> tuple[list[RetrievalResult], bool]:
    """Never trusts a citation ref returned by the model. A ref is valid
    only if it corresponds exactly to a chunk that was actually included
    in THIS request's retrieved context (`refs`, built directly from this
    call's own retrieval_service results) -- which is itself already
    guaranteed to belong to the active company and to a non-deleted,
    accessible document, since retrieval_service enforces both. Any ref
    the model invents that isn't a key in `refs` is fabricated and is
    reported via the second return value, never silently accepted.
    """
    valid: list[RetrievalResult] = []
    had_invalid = False
    for citation in citations:
        result = refs.get(citation.ref)
        if result is None:
            had_invalid = True
            continue
        valid.append(result)
    return valid, had_invalid


def _dedupe_preserving_order(chunk_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    seen: set[uuid.UUID] = set()
    ordered: list[uuid.UUID] = []
    for chunk_id in chunk_ids:
        if chunk_id not in seen:
            seen.add(chunk_id)
            ordered.append(chunk_id)
    return ordered


def _load_citation_sources(
    db: Session,
    *,
    company_id: uuid.UUID,
    retrieval_results: list[RetrievalResult],
    chunk_ids: list[uuid.UUID],
) -> list[CitationSource]:
    """Builds the user-facing citation payload (file_name/document_type/
    project_id alongside the page/sheet/section metadata already carried
    by RetrievalResult) -- never a storage_key, embedding, or signed URL.
    Looks documents up fresh, scoped to this company and excluding
    soft-deleted rows, rather than trusting anything cached from the
    retrieval call.
    """
    by_chunk_id = {r.chunk_id: r for r in retrieval_results}
    document_ids = {by_chunk_id[cid].document_id for cid in chunk_ids if cid in by_chunk_id}
    if not document_ids:
        return []

    documents = {
        d.id: d
        for d in db.execute(
            select(Document).where(
                Document.company_id == company_id,
                Document.id.in_(document_ids),
                Document.deleted_at.is_(None),
            )
        ).scalars()
    }

    sources: list[CitationSource] = []
    for chunk_id in chunk_ids:
        result = by_chunk_id.get(chunk_id)
        if result is None:
            continue
        document = documents.get(result.document_id)
        if document is None:
            # Deleted between retrieval and persistence -- exclude rather
            # than surface a now-inaccessible document's metadata.
            continue
        sources.append(
            CitationSource(
                document_chunk_id=result.chunk_id,
                document_id=result.document_id,
                file_name=document.file_name,
                document_type=document.document_type,
                project_id=document.project_id,
                page_number=result.page_number,
                sheet_name=result.sheet_name,
                section_name=result.section_name,
                source_location=result.source_location,
            )
        )
    return sources


def _to_result(*, assistant_message, citations: list[CitationSource]) -> AskResult:
    return AskResult(
        message_id=assistant_message.id,
        conversation_id=assistant_message.conversation_id,
        role=assistant_message.role,
        content=assistant_message.content,
        is_sufficient=assistant_message.is_sufficient,
        model_identifier=assistant_message.model_identifier,
        created_at=assistant_message.created_at,
        citations=citations,
    )


def load_citation_sources_for_messages(
    db: Session, *, company_id: uuid.UUID, message_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[CitationSource]]:
    """Loads persisted citations for one or more already-existing messages
    (used by GET .../messages) -- unlike _load_citation_sources (used
    right after a fresh ask_question call, from in-memory retrieval
    results), this reads message_citations/document_chunks/documents
    directly. A soft-deleted document's citation is silently excluded --
    it remains recorded in message_citations for audit/traceability, but
    is never surfaced as a usable "source" once its document is gone.
    """
    if not message_ids:
        return {}

    rows = db.execute(
        select(MessageCitation, DocumentChunk, Document)
        .join(DocumentChunk, DocumentChunk.id == MessageCitation.document_chunk_id)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            MessageCitation.company_id == company_id,
            MessageCitation.message_id.in_(message_ids),
            Document.deleted_at.is_(None),
        )
        .order_by(MessageCitation.message_id, MessageCitation.citation_index.asc())
    ).all()

    grouped: dict[uuid.UUID, list[CitationSource]] = {}
    for citation, chunk, document in rows:
        grouped.setdefault(citation.message_id, []).append(
            CitationSource(
                document_chunk_id=chunk.id,
                document_id=document.id,
                file_name=document.file_name,
                document_type=document.document_type,
                project_id=document.project_id,
                page_number=chunk.page_number,
                sheet_name=chunk.sheet_name,
                section_name=chunk.section_name,
                source_location=chunk.source_location,
            )
        )
    return grouped

