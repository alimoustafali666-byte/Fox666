"""Daily Management Brief -- the Step 12 on-demand generation orchestrator.
Structurally mirrors app.modules.conversations.ask_service: gather bounded
context -> call the LLMProvider -> independently re-validate every
citation before persisting -> at most one corrective retry -> persist
atomically -> audit.

CRITICAL ARCHITECTURAL RULE (same as Step 11's Ask Your Business): this
module decides what's grounded, not Claude. Every generated item's
`source_ref` is re-validated against the documents actually provided in
THIS run before being persisted; an unvalidated ref is never trusted.

DOCUMENT CONTENT IS DATA, NOT INSTRUCTIONS. Every document's content
gathered here is untrusted text extracted from the company's own
documents, handed to the LLM provider as inert context only -- same
boundary as ask_service.py.

On-demand only (Step 12 approved scope): no scheduler, no cron, no
background job/worker. Every call here runs synchronously within the
triggering HTTP request, exactly like Step 9/10's processing/indexing.
"""

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.core.config import settings
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
    BriefCarryForwardItem,
    BriefDocumentContextItem,
    BriefGeneratedItem,
    BriefGenerationRequest,
    BriefGenerationResult,
)
from app.modules.audit_log.service import record_audit_event
from app.modules.briefs import repository
from app.modules.briefs.exceptions import BriefGenerationUnavailableError
from app.modules.briefs.models import BRIEF_ITEM_CATEGORIES, BriefItem, DailyBrief
from app.modules.documents import repository as documents_repository
from app.modules.documents.models import Document

NO_NEW_INFORMATION_SUMMARY = "No new documents or open items since the last brief."

_API_ERROR_BY_LLM_ERROR_CODE: dict[str, type] = {
    "llm_provider_unavailable": BriefGenerationUnavailableError,
    "llm_provider_authentication_failed": BriefGenerationUnavailableError,
    "llm_provider_misconfigured": BriefGenerationUnavailableError,
    "llm_operation_failed": BriefGenerationUnavailableError,
}


@dataclass
class BriefResult:
    brief_id: uuid.UUID
    company_id: uuid.UUID
    brief_date: date
    summary: str
    generated_at: datetime
    generated_by: uuid.UUID
    items: list[BriefItem]


def generate_brief(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    ip_address: str | None,
) -> BriefResult:
    today = datetime.now(UTC).date()
    existing_brief = repository.get_daily_brief_by_date(db, company_id=company_id, brief_date=today)

    previous_brief = repository.get_previous_daily_brief(db, company_id=company_id, before_date=today)
    since = previous_brief.generated_at if previous_brief else None

    documents = repository.list_documents_since(
        db, company_id=company_id, since=since, limit=settings.brief_max_documents_per_run
    )
    carry_forward_rows = repository.list_recent_open_items(
        db, company_id=company_id, before_date=today,
        lookback_briefs=settings.brief_lookback_briefs,
        max_items=settings.brief_max_carry_forward_items,
    )

    started_at = time.monotonic()

    if not documents and not carry_forward_rows:
        return _persist_and_audit(
            db, company_id=company_id, actor_user_id=actor_user_id, ip_address=ip_address,
            brief_date=today, summary=NO_NEW_INFORMATION_SUMMARY, item_rows=[],
            existing_brief=existing_brief, new_document_count=0, carry_forward_count=0,
            llm_called=False, model_identifier=None, input_tokens=None, output_tokens=None,
            started_at=started_at,
        )

    document_refs, document_context = _build_document_context(db, company_id=company_id, documents=documents)
    carry_forward_items, document_refs = _build_carry_forward(carry_forward_rows, document_refs)

    generated = _generate_validated_brief(
        document_context=document_context, carry_forward_items=carry_forward_items,
        valid_refs=set(document_refs.keys()),
    )

    if generated is None:
        return _persist_and_audit(
            db, company_id=company_id, actor_user_id=actor_user_id, ip_address=ip_address,
            brief_date=today, summary=NO_NEW_INFORMATION_SUMMARY, item_rows=[],
            existing_brief=existing_brief, new_document_count=len(documents),
            carry_forward_count=len(carry_forward_rows), llm_called=True,
            model_identifier=None, input_tokens=None, output_tokens=None, started_at=started_at,
            validation_failed=True,
        )

    brief_result, valid_items = generated
    item_rows = [
        {
            "category": item.category,
            "text": item.text,
            "priority": item.priority,
            "source_document_id": document_refs.get(item.source_ref) if item.source_ref else None,
        }
        for item in valid_items
    ]

    return _persist_and_audit(
        db, company_id=company_id, actor_user_id=actor_user_id, ip_address=ip_address,
        brief_date=today, summary=brief_result.summary, item_rows=item_rows,
        existing_brief=existing_brief, new_document_count=len(documents),
        carry_forward_count=len(carry_forward_rows), llm_called=True,
        model_identifier=brief_result.model_identifier, input_tokens=brief_result.input_tokens,
        output_tokens=brief_result.output_tokens, started_at=started_at,
    )


def _build_document_context(
    db: Session, *, company_id: uuid.UUID, documents: list[Document],
) -> tuple[dict[str, uuid.UUID], list[BriefDocumentContextItem]]:
    refs: dict[str, uuid.UUID] = {}
    context: list[BriefDocumentContextItem] = []
    for index, document in enumerate(documents, start=1):
        ref = str(index)
        refs[ref] = document.id
        chunks = documents_repository.list_document_chunks(
            db, company_id=company_id, document_id=document.id
        )
        content = "\n".join(chunk.content for chunk in chunks)[: settings.brief_max_chars_per_document]
        context.append(BriefDocumentContextItem(ref=ref, content=f"{document.file_name}\n{content}"))
    return refs, context


def _build_carry_forward(
    carry_forward_rows: list[BriefItem], document_refs: dict[str, uuid.UUID],
) -> tuple[list[BriefCarryForwardItem], dict[str, uuid.UUID]]:
    """Assigns a ref to each distinct carried-forward item's original
    source document too (reusing an existing ref if that document is
    already a "new" document in this run), so the model may legitimately
    re-cite an old item's original source without that old document's
    full content being re-sent.
    """
    refs = dict(document_refs)
    next_index = len(refs) + 1
    items: list[BriefCarryForwardItem] = []

    for row in carry_forward_rows:
        source_ref: str | None = None
        if row.source_document_id is not None:
            existing_ref = next(
                (ref for ref, doc_id in refs.items() if doc_id == row.source_document_id), None
            )
            if existing_ref is not None:
                source_ref = existing_ref
            else:
                source_ref = str(next_index)
                refs[source_ref] = row.source_document_id
                next_index += 1
        items.append(
            BriefCarryForwardItem(
                category=row.category, text=row.text, priority=row.priority, source_ref=source_ref,
            )
        )

    return items, refs


def _generate_validated_brief(
    *,
    document_context: list[BriefDocumentContextItem],
    carry_forward_items: list[BriefCarryForwardItem],
    valid_refs: set[str],
) -> tuple[BriefGenerationResult, list[BriefGeneratedItem]] | None:
    """Calls the LLM provider, validating structured output and every
    item's source_ref, with at most `settings.brief_max_citation_retries`
    controlled corrective retries -- never an open loop. Returns
    (BriefGenerationResult, valid_items) on success, or None if every
    attempt was exhausted without a trustworthy result.
    """
    provider = get_llm_provider()
    corrective_note: str | None = None
    max_attempts = settings.brief_max_citation_retries + 1

    for attempt in range(max_attempts):
        request = BriefGenerationRequest(
            new_documents=document_context, carry_forward_items=carry_forward_items,
            corrective_note=corrective_note,
        )
        try:
            result = provider.generate_daily_brief(request)
        except LLMMalformedOutputError:
            if attempt + 1 >= max_attempts:
                return None
            corrective_note = (
                "Your previous response did not match the required structured schema. "
                "Respond again using only the required JSON fields: summary, items "
                "(each with category, text, priority, source_ref)."
            )
            continue
        except (LLMAuthenticationError, LLMConfigurationError, LLMUnavailable, LLMOperationError) as exc:
            api_error_cls = _API_ERROR_BY_LLM_ERROR_CODE.get(exc.error_code, BriefGenerationUnavailableError)
            raise api_error_cls("Daily brief generation is temporarily unavailable.") from exc
        except LLMError as exc:  # last-resort safety net for any unmapped LLMError subclass
            raise BriefGenerationUnavailableError("Daily brief generation is temporarily unavailable.") from exc

        valid_items, had_invalid = _validate_items(result.items, valid_refs)

        if had_invalid:
            if attempt + 1 >= max_attempts:
                return None
            corrective_note = (
                "One or more items you returned had a source_ref that did not match a "
                "reference label actually given to you, or an invalid category. Re-answer "
                "using only the exact ref labels and the four allowed categories."
            )
            continue

        return result, valid_items

    return None


def _validate_items(
    items: list[BriefGeneratedItem], valid_refs: set[str]
) -> tuple[list[BriefGeneratedItem], bool]:
    """Never trusts an item's source_ref or category as returned by the
    model. A ref is valid only if it corresponds exactly to a document
    actually provided in THIS run (new document or a carry-forward item's
    original source) -- which is itself already guaranteed to belong to
    the active company, since both are resolved from company-scoped
    repository queries. An invalid category or a ref the model invents
    that isn't a key in `valid_refs` makes the WHOLE batch invalid (never
    silently drop just the bad item and keep the rest -- a batch is one
    structured response, not independently-verifiable line items the way
    Q&A citations are), reported via the second return value.
    """
    valid = []
    had_invalid = False
    for item in items:
        if item.category not in BRIEF_ITEM_CATEGORIES:
            had_invalid = True
            continue
        if item.source_ref is not None and item.source_ref not in valid_refs:
            had_invalid = True
            continue
        if not (1 <= item.priority <= 3):
            had_invalid = True
            continue
        valid.append(item)
    return valid, had_invalid


def _persist_and_audit(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    ip_address: str | None,
    brief_date: date,
    summary: str,
    item_rows: list[dict],
    existing_brief: DailyBrief | None,
    new_document_count: int,
    carry_forward_count: int,
    llm_called: bool,
    model_identifier: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    started_at: float,
    validation_failed: bool = False,
) -> BriefResult:
    is_regeneration = existing_brief is not None

    if is_regeneration:
        repository.delete_brief_items(db, company_id=company_id, brief_id=existing_brief.id)
        existing_brief.summary = summary
        # Set explicitly in Python (real wall-clock time), not left to the
        # column's `now()` server_default -- Postgres freezes now() to the
        # start of the enclosing transaction, so a regenerate-then-list
        # sequence within one transaction would otherwise see a stale
        # generated_at. Same fix as Step 11's Message.created_at.
        existing_brief.generated_at = datetime.now(UTC)
        db.flush()
        brief = existing_brief
    else:
        brief = repository.create_daily_brief(
            db, id=uuid.uuid4(), company_id=company_id, generated_by=actor_user_id,
            brief_date=brief_date, summary=summary,
        )

    items = repository.create_brief_items(
        db, company_id=company_id, brief_id=brief.id, items=item_rows
    )

    duration_ms = int((time.monotonic() - started_at) * 1000)
    metadata = {
        "brief_id": str(brief.id),
        "new_document_count": new_document_count,
        "carry_forward_count": carry_forward_count,
        "item_count": len(items),
        "llm_called": llm_called,
        "model_identifier": model_identifier,
        "input_usage_count": input_tokens,
        "output_usage_count": output_tokens,
        "duration_ms": duration_ms,
        "validation_failed": validation_failed,
    }
    record_audit_event(
        db, company_id=company_id, actor_user_id=actor_user_id,
        action="brief.regenerated" if is_regeneration else "brief.generated",
        resource_type="daily_brief", resource_id=brief.id, metadata=metadata, ip_address=ip_address,
    )
    db.commit()

    return BriefResult(
        brief_id=brief.id, company_id=company_id, brief_date=brief.brief_date, summary=brief.summary,
        generated_at=brief.generated_at, generated_by=brief.generated_by, items=items,
    )

